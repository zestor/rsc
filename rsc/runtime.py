from __future__ import annotations

from openai import OpenAI

from .artifact_protocol import ArtifactParser
from .chat_store import ChatStore
from .config import RSCConfig
from .context_manager import ContextManager
from .evaluator import Evaluator
from .local_search_provider import LocalSearchProvider
from .loop_orchestrator import LoopOrchestrator
from .observability import configure_daily_file_logging, get_logger, log_event
from .openai_responses_adapter import OpenAIResponsesClientAdapter
from .openrouter_adapter import OpenRouterClientAdapter, openrouter_provider_options
from .prompt_assembler import PromptAssembler
from .role_agent import RoleAgent
from .role_search_planner import RoleSearchPlanner
from .search_inference import SearchOverInference
from .search_provider import FirecrawlSearchProvider, HTTPMarkdownSearchProvider
from .skill_runtime import build_skill_router, capabilities_from_config
from .state_loader import StateLoader
from .state_manager import StateManager
from .vector_index import VectorIndex


def build_client(config: RSCConfig):
    if config.llm_provider == "openrouter":
        return OpenRouterClientAdapter(
            api_key=config.openrouter_api_key or "",
            model=config.loop_model,
            provider=openrouter_provider_options(
                zdr=config.openrouter_provider_zdr,
                only=config.openrouter_provider_only,
            ),
            x_open_router_title=config.openrouter_app_title,
        )
    openai_client = OpenAI(
        base_url=config.openai_base_url,
        api_key=config.openai_api_key,
    )
    if not config.openai_use_responses_api:
        return openai_client
    return OpenAIResponsesClientAdapter(
        openai_client,
        text_verbosity=config.openai_text_verbosity,
        reasoning_effort=config.openai_reasoning_effort,
        reasoning_summary=config.openai_reasoning_summary,
        store=config.openai_store,
        include=list(config.openai_include),
    )


def build_search_provider(config: RSCConfig):
    if config.search_provider == "firecrawl":
        return FirecrawlSearchProvider(
            api_key=config.firecrawl_api_key,
            endpoint=config.firecrawl_search_endpoint,
            max_age_ms=config.firecrawl_max_age_ms,
            max_concurrency=config.search_max_concurrency,
        )
    if config.search_provider == "http" and config.search_endpoint:
        return HTTPMarkdownSearchProvider(
            endpoint=config.search_endpoint,
            method=config.search_method,
            max_concurrency=config.search_max_concurrency,
        )
    return None


def _build_embedding_client(config: RSCConfig):
    """Build an OpenAI-compatible client for embeddings.

    For OpenRouter: uses OpenAI SDK pointed at OpenRouter's base URL
    (which exposes /v1/embeddings). For OpenAI: reuses the existing client.
    Returns None if no valid client can be built.
    """
    _logger = get_logger("runtime")
    if config.llm_provider == "openrouter":
        if not config.openrouter_api_key:
            log_event(
                _logger,
                "embedding_client.skip",
                session_id="",
                depth=0,
                reason="no_openrouter_key",
            )
            return None
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=config.openrouter_api_key,
            )
            log_event(
                _logger,
                "embedding_client.created",
                session_id="",
                depth=0,
                provider="openrouter",
                model=config.embedder_model,
            )
            return client
        except Exception as exc:
            log_event(
                _logger,
                "embedding_client.error",
                session_id="",
                depth=0,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            return None
    if config.llm_provider == "openai":
        if not config.openai_api_key:
            log_event(
                _logger,
                "embedding_client.skip",
                session_id="",
                depth=0,
                reason="no_openai_key",
            )
            return None
        client = OpenAI(
            base_url=config.openai_base_url,
            api_key=config.openai_api_key,
        )
        log_event(
            _logger,
            "embedding_client.created",
            session_id="",
            depth=0,
            provider="openai",
            model=config.embedder_model,
        )
        return client
    return None


def build_orchestrator(config: RSCConfig) -> LoopOrchestrator:
    configure_daily_file_logging(config.log_dir, level=config.log_level)
    client = build_client(config)
    prompt_assembler = PromptAssembler(
        config.loop_model,
        config.max_input_tokens_per_call,
        learned_rules_threshold=config.context_learned_rules_threshold,
    )
    context_manager = ContextManager(
        prompt_assembler=prompt_assembler,
        client=client,
        model=config.loop_model,
        context_window_tokens=config.llm_context_window_tokens,
        output_tokens=config.llm_output_tokens,
        budget_ratio=config.context_budget_ratio,
        search_summary_target_tokens=config.context_search_summary_target_tokens,
        domain_knowledge_target_tokens=config.context_domain_knowledge_target_tokens,
        history_summary_threshold=config.context_history_summary_threshold,
        learned_rules_threshold=config.context_learned_rules_threshold,
    )
    role_agent = RoleAgent(
        client=client,
        model=config.loop_model,
        prompt_assembler=prompt_assembler,
        artifact_parser=ArtifactParser(),
        max_output_tokens=config.max_output_tokens_per_call,
        context_manager=context_manager,
    )
    evaluator = Evaluator(
        client,
        config.eval_model,
        prompt_assembler,
        context_manager=context_manager,
    )
    search_provider = build_search_provider(config)

    # Local cross-chat content search
    local_search_provider = None
    chat_store = ChatStore(config.state_dir)
    if config.local_search_enabled:
        vectors_dir = config.state_dir / "chat_content" / "vectors"
        vector_index = VectorIndex(base_dir=vectors_dir)
        # Load existing chunks into the index if not already loaded
        if not vector_index.is_loaded:
            all_chunks = chat_store.load_all_chunks()
            if all_chunks:
                vector_index.rebuild_from_chunks(all_chunks)
        local_search_provider = LocalSearchProvider(
            vector_index=vector_index,
            min_score=config.local_search_min_score,
        )

    role_search_planner = RoleSearchPlanner(
        search_provider=search_provider,
        client=client,
        model=config.role_search_query_model or config.loop_model,
        max_queries_per_call=config.role_search_max_queries,
        max_results_per_query=config.role_search_max_results,
        max_concurrency=config.search_max_concurrency,
        temperature=config.role_search_temperature,
        max_tokens=config.role_search_max_tokens,
        max_query_words=config.role_search_max_query_words,
        enabled=config.role_search_enabled,
        local_search_provider=local_search_provider,
    )
    return LoopOrchestrator(
        client=client,
        model=config.loop_model,
        state_loader=StateLoader(config.state_dir),
        state_manager=StateManager(
            config.state_dir,
            client=client,
            embedder_enabled=config.embedder_enabled,
            embedder_model=config.embedder_model,
        ),
        role_agent=role_agent,
        evaluator=evaluator,
        prompt_assembler=prompt_assembler,
        search_over_inference=SearchOverInference(
            role_agent, evaluator, config.n_candidates
        ),
        search_provider=search_provider,
        search_max_results=config.search_max_results,
        search_query_count=config.search_query_count,
        skill_router=build_skill_router(
            config.skill_library_paths,
            available_capabilities=capabilities_from_config(config),
            embedding_client=client if config.embedder_enabled else None,
            embedding_model=config.embedder_model,
        ),
        skill_top_k=config.skill_top_k,
        max_turns=config.max_turns,
        max_depth=config.max_depth,
        pass_threshold=config.pass_threshold,
        max_total_tokens_per_session=config.max_total_tokens_per_session,
        role_search_planner=role_search_planner,
        role_search_max_calls_per_turn=config.role_search_max_calls_per_turn,
        role_search_max_total_records=config.role_search_max_total_records,
        chat_store=chat_store,
        verifier_enabled=config.verifier_enabled,
        synthesizer_enabled=config.synthesizer_enabled,
    )
