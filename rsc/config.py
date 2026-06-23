from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .exceptions import ConfigurationError

OPENROUTER_DEFAULT_MODEL = "z-ai/glm-5.2"
OPENAI_DEFAULT_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class RSCConfig:
    llm_provider: str = "openrouter"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    openai_use_responses_api: bool = True
    openai_text_verbosity: str = "medium"
    openai_reasoning_effort: str = "medium"
    openai_reasoning_summary: str = "auto"
    openai_store: bool = True
    openai_include: tuple[str, ...] = (
        "reasoning.encrypted_content",
        "web_search_call.action.sources",
    )
    openrouter_api_key: str | None = None
    openrouter_provider_zdr: bool = False
    openrouter_provider_only: tuple[str, ...] = ()
    openrouter_app_title: str = "Recursive Scaffolded Cognition"
    loop_model: str = OPENROUTER_DEFAULT_MODEL
    eval_model: str = OPENROUTER_DEFAULT_MODEL
    max_turns: int = 3
    max_depth: int = 3
    pass_threshold: float = 1.0
    n_candidates: int = 3
    verifier_enabled: bool = False
    synthesizer_enabled: bool = False
    state_dir: Path = Path("./state")
    log_level: str = "INFO"
    log_dir: Path = Path("./rsc/logs")
    max_input_tokens_per_call: int = 200000
    max_output_tokens_per_call: int = 65536
    max_total_tokens_per_session: int = 2000000
    embedder_enabled: bool = False
    embedder_model: str = "text-embedding-3-large"
    embedder_dimensions: int = 3072
    local_search_enabled: bool = False
    local_search_top_k: int = 5
    local_search_min_score: float = 0.15
    search_endpoint: str | None = None
    search_method: str = "POST"
    search_max_results: int = 5
    search_max_concurrency: int = 2
    search_query_count: int = 3
    search_provider: str = "firecrawl"
    firecrawl_api_key: str | None = None
    firecrawl_search_endpoint: str = "https://api.firecrawl.dev/v2/search"
    firecrawl_max_age_ms: int = 172800000
    skill_library_paths: tuple[Path, ...] = ()
    skill_top_k: int = 3
    role_search_enabled: bool = False
    role_search_max_queries: int = 3
    role_search_max_results: int = 5
    role_search_max_calls_per_turn: int = 2
    role_search_max_total_records: int = 50
    role_search_temperature: float = 0.65
    role_search_max_tokens: int = 1024
    role_search_max_query_words: int = 11
    role_search_query_model: str | None = (
        None  # fast model for query gen; None = use loop_model
    )
    llm_context_window_tokens: int = 1_000_000
    llm_output_tokens: int = 65_536
    context_budget_ratio: float = 0.8
    context_search_summary_target_tokens: int = 500
    context_domain_knowledge_target_tokens: int = 2000
    context_history_summary_threshold: int = 1000
    context_learned_rules_threshold: int = 15

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_api_key: bool = True,
        dotenv_path: str | Path | None = ".env",
    ) -> "RSCConfig":
        env = _merged_env(dotenv_path) if environ is None else environ
        llm_provider = env.get("LLM_PROVIDER", cls.llm_provider)
        openai_api_key = env.get("OPENAI_API_KEY")
        openrouter_api_key = env.get("OPENROUTER_API_KEY")
        config = cls(
            llm_provider=llm_provider,
            openai_base_url=env.get("OPENAI_BASE_URL", cls.openai_base_url),
            openai_api_key=openai_api_key,
            openai_use_responses_api=_env_bool(
                env, "OPENAI_USE_RESPONSES_API", cls.openai_use_responses_api
            ),
            openai_text_verbosity=env.get(
                "OPENAI_TEXT_VERBOSITY", cls.openai_text_verbosity
            ),
            openai_reasoning_effort=env.get(
                "OPENAI_REASONING_EFFORT", cls.openai_reasoning_effort
            ),
            openai_reasoning_summary=env.get(
                "OPENAI_REASONING_SUMMARY", cls.openai_reasoning_summary
            ),
            openai_store=_env_bool(env, "OPENAI_STORE", cls.openai_store),
            openai_include=_env_tuple(env.get("OPENAI_INCLUDE"), cls.openai_include),
            openrouter_api_key=openrouter_api_key,
            openrouter_provider_zdr=_env_bool(
                env, "OPENROUTER_PROVIDER_ZDR", cls.openrouter_provider_zdr
            ),
            openrouter_provider_only=_openrouter_provider_only(
                env.get("OPENROUTER_PROVIDER_ONLY")
            ),
            openrouter_app_title=env.get(
                "OPENROUTER_APP_TITLE", cls.openrouter_app_title
            ),
            loop_model=env.get(
                "LOOP_MODEL",
                (
                    OPENROUTER_DEFAULT_MODEL
                    if llm_provider == "openrouter"
                    else OPENAI_DEFAULT_MODEL
                ),
            ),
            eval_model=env.get(
                "EVAL_MODEL",
                (
                    OPENROUTER_DEFAULT_MODEL
                    if llm_provider == "openrouter"
                    else OPENAI_DEFAULT_MODEL
                ),
            ),
            max_turns=_env_int(env, "MAX_TURNS", cls.max_turns),
            max_depth=_env_int(env, "MAX_DEPTH", cls.max_depth),
            pass_threshold=_env_float(env, "PASS_THRESHOLD", cls.pass_threshold),
            n_candidates=_env_int(env, "N_CANDIDATES", cls.n_candidates),
            verifier_enabled=_env_bool(env, "VERIFIER_ENABLED", cls.verifier_enabled),
            synthesizer_enabled=_env_bool(
                env, "SYNTHESIZER_ENABLED", cls.synthesizer_enabled
            ),
            state_dir=Path(env.get("STATE_DIR", str(cls.state_dir))),
            log_level=env.get("LOG_LEVEL", cls.log_level),
            log_dir=Path(env.get("LOG_DIR", str(cls.log_dir))),
            max_input_tokens_per_call=_env_int(
                env, "MAX_INPUT_TOKENS_PER_CALL", cls.max_input_tokens_per_call
            ),
            max_output_tokens_per_call=_env_int(
                env, "MAX_OUTPUT_TOKENS_PER_CALL", cls.max_output_tokens_per_call
            ),
            max_total_tokens_per_session=_env_int(
                env, "MAX_TOTAL_TOKENS_PER_SESSION", cls.max_total_tokens_per_session
            ),
            embedder_enabled=_env_bool(env, "EMBEDDER_ENABLED", cls.embedder_enabled),
            embedder_model=env.get("EMBEDDER_MODEL", cls.embedder_model),
            embedder_dimensions=_env_int(
                env, "EMBEDDER_DIMENSIONS", cls.embedder_dimensions
            ),
            local_search_enabled=_env_bool(
                env, "LOCAL_SEARCH_ENABLED", cls.local_search_enabled
            ),
            local_search_top_k=_env_int(
                env, "LOCAL_SEARCH_TOP_K", cls.local_search_top_k
            ),
            local_search_min_score=_env_float(
                env, "LOCAL_SEARCH_MIN_SCORE", cls.local_search_min_score
            ),
            search_endpoint=env.get("SEARCH_ENDPOINT"),
            search_method=env.get("SEARCH_METHOD", cls.search_method),
            search_max_results=_env_int(
                env, "SEARCH_MAX_RESULTS", cls.search_max_results
            ),
            search_max_concurrency=_env_int(
                env, "SEARCH_MAX_CONCURRENCY", cls.search_max_concurrency
            ),
            search_query_count=_env_int(
                env, "SEARCH_QUERY_COUNT", cls.search_query_count
            ),
            search_provider=env.get("SEARCH_PROVIDER", cls.search_provider),
            firecrawl_api_key=env.get("FIRECRAWL_API_KEY"),
            firecrawl_search_endpoint=env.get(
                "FIRECRAWL_SEARCH_ENDPOINT", cls.firecrawl_search_endpoint
            ),
            firecrawl_max_age_ms=_env_int(
                env, "FIRECRAWL_MAX_AGE_MS", cls.firecrawl_max_age_ms
            ),
            skill_library_paths=_env_paths(env.get("SKILL_LIBRARY_PATHS")),
            skill_top_k=_env_int(env, "SKILL_TOP_K", cls.skill_top_k),
            role_search_enabled=_env_bool(
                env, "ROLE_SEARCH_ENABLED", cls.role_search_enabled
            ),
            role_search_max_queries=_env_int(
                env, "ROLE_SEARCH_MAX_QUERIES", cls.role_search_max_queries
            ),
            role_search_max_results=_env_int(
                env, "ROLE_SEARCH_MAX_RESULTS", cls.role_search_max_results
            ),
            role_search_max_calls_per_turn=_env_int(
                env,
                "ROLE_SEARCH_MAX_CALLS_PER_TURN",
                cls.role_search_max_calls_per_turn,
            ),
            role_search_max_total_records=_env_int(
                env, "ROLE_SEARCH_MAX_TOTAL_RECORDS", cls.role_search_max_total_records
            ),
            role_search_temperature=_env_float(
                env, "ROLE_SEARCH_TEMPERATURE", cls.role_search_temperature
            ),
            role_search_max_tokens=_env_int(
                env, "ROLE_SEARCH_MAX_TOKENS", cls.role_search_max_tokens
            ),
            role_search_max_query_words=_env_int(
                env, "ROLE_SEARCH_MAX_QUERY_WORDS", cls.role_search_max_query_words
            ),
            role_search_query_model=env.get(
                "ROLE_SEARCH_QUERY_MODEL", cls.role_search_query_model
            ),
            llm_context_window_tokens=_env_int(
                env, "LLM_CONTEXT_WINDOW_TOKENS", cls.llm_context_window_tokens
            ),
            llm_output_tokens=_env_int(env, "LLM_OUTPUT_TOKENS", cls.llm_output_tokens),
            context_budget_ratio=_env_float(
                env, "CONTEXT_BUDGET_RATIO", cls.context_budget_ratio
            ),
            context_search_summary_target_tokens=_env_int(
                env,
                "CONTEXT_SEARCH_SUMMARY_TARGET_TOKENS",
                cls.context_search_summary_target_tokens,
            ),
            context_domain_knowledge_target_tokens=_env_int(
                env,
                "CONTEXT_DOMAIN_KNOWLEDGE_TARGET_TOKENS",
                cls.context_domain_knowledge_target_tokens,
            ),
            context_history_summary_threshold=_env_int(
                env,
                "CONTEXT_HISTORY_SUMMARY_THRESHOLD",
                cls.context_history_summary_threshold,
            ),
            context_learned_rules_threshold=_env_int(
                env,
                "CONTEXT_LEARNED_RULES_THRESHOLD",
                cls.context_learned_rules_threshold,
            ),
        )
        config.validate(require_api_key=require_api_key)
        return config

    def validate(self, *, require_api_key: bool = False) -> None:
        if self.llm_provider not in {"openai", "openrouter"}:
            raise ConfigurationError("LLM_PROVIDER must be openai or openrouter")
        if self.openai_text_verbosity not in {"low", "medium", "high"}:
            raise ConfigurationError(
                "OPENAI_TEXT_VERBOSITY must be low, medium, or high"
            )
        if self.openai_reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ConfigurationError(
                "OPENAI_REASONING_EFFORT must be minimal, low, medium, or high"
            )
        if (
            require_api_key
            and self.llm_provider == "openai"
            and not self.openai_api_key
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
            )
        if (
            require_api_key
            and self.llm_provider == "openrouter"
            and not self.openrouter_api_key
        ):
            raise ConfigurationError(
                "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter"
            )
        if not 1 <= self.max_turns <= 3:
            raise ConfigurationError("MAX_TURNS must be in [1, 3]")
        if not 0 <= self.max_depth <= 10:
            raise ConfigurationError("MAX_DEPTH must be in [0, 10]")
        if not 0.0 <= self.pass_threshold <= 1.0:
            raise ConfigurationError("PASS_THRESHOLD must be in [0.0, 1.0]")
        if not 2 <= self.n_candidates <= 5:
            raise ConfigurationError("N_CANDIDATES must be in [2, 5]")
        if self.max_input_tokens_per_call <= 0:
            raise ConfigurationError("MAX_INPUT_TOKENS_PER_CALL must be positive")
        if self.max_output_tokens_per_call <= 0:
            raise ConfigurationError("MAX_OUTPUT_TOKENS_PER_CALL must be positive")
        if self.max_total_tokens_per_session <= 0:
            raise ConfigurationError("MAX_TOTAL_TOKENS_PER_SESSION must be positive")
        if self.search_method.upper() not in {"GET", "POST"}:
            raise ConfigurationError("SEARCH_METHOD must be GET or POST")
        if self.search_max_results <= 0:
            raise ConfigurationError("SEARCH_MAX_RESULTS must be positive")
        if not 2 <= self.search_max_concurrency <= 50:
            raise ConfigurationError("SEARCH_MAX_CONCURRENCY must be in [2, 50]")
        if not 1 <= self.search_query_count <= 5:
            raise ConfigurationError("SEARCH_QUERY_COUNT must be in [1, 5]")
        if self.search_provider not in {"firecrawl", "http", "none"}:
            raise ConfigurationError("SEARCH_PROVIDER must be firecrawl, http, or none")
        if self.firecrawl_max_age_ms < 0:
            raise ConfigurationError("FIRECRAWL_MAX_AGE_MS must be non-negative")
        if not 1 <= self.skill_top_k <= 10:
            raise ConfigurationError("SKILL_TOP_K must be in [1, 10]")
        if not 1 <= self.role_search_max_queries <= 5:
            raise ConfigurationError("ROLE_SEARCH_MAX_QUERIES must be in [1, 5]")
        if self.role_search_max_results <= 0:
            raise ConfigurationError("ROLE_SEARCH_MAX_RESULTS must be positive")
        if not 1 <= self.role_search_max_calls_per_turn <= 5:
            raise ConfigurationError("ROLE_SEARCH_MAX_CALLS_PER_TURN must be in [1, 5]")
        if self.role_search_max_total_records < 0:
            raise ConfigurationError(
                "ROLE_SEARCH_MAX_TOTAL_RECORDS must be non-negative"
            )
        if not 0.0 <= self.role_search_temperature <= 2.0:
            raise ConfigurationError("ROLE_SEARCH_TEMPERATURE must be in [0.0, 2.0]")
        if self.role_search_max_tokens <= 0:
            raise ConfigurationError("ROLE_SEARCH_MAX_TOKENS must be positive")
        if not 3 <= self.role_search_max_query_words <= 60:
            raise ConfigurationError("ROLE_SEARCH_MAX_QUERY_WORDS must be in [3, 60]")
        if self.llm_context_window_tokens <= 0:
            raise ConfigurationError("LLM_CONTEXT_WINDOW_TOKENS must be positive")
        if self.llm_output_tokens <= 0:
            raise ConfigurationError("LLM_OUTPUT_TOKENS must be positive")
        if not 0.5 <= self.context_budget_ratio <= 0.95:
            raise ConfigurationError("CONTEXT_BUDGET_RATIO must be in [0.5, 0.95]")
        if self.context_search_summary_target_tokens <= 0:
            raise ConfigurationError(
                "CONTEXT_SEARCH_SUMMARY_TARGET_TOKENS must be positive"
            )
        if self.context_domain_knowledge_target_tokens <= 0:
            raise ConfigurationError(
                "CONTEXT_DOMAIN_KNOWLEDGE_TARGET_TOKENS must be positive"
            )
        if self.context_history_summary_threshold <= 0:
            raise ConfigurationError(
                "CONTEXT_HISTORY_SUMMARY_THRESHOLD must be positive"
            )
        if self.context_learned_rules_threshold <= 0:
            raise ConfigurationError("CONTEXT_LEARNED_RULES_THRESHOLD must be positive")


def _merged_env(dotenv_path: str | Path | None) -> dict[str, str]:
    env = dict(os.environ)
    if dotenv_path is None:
        return env
    for path in _dotenv_candidates(dotenv_path):
        if path.exists():
            for key, value in _read_dotenv(path).items():
                env.setdefault(key, value)
    return env


def _dotenv_candidates(dotenv_path: str | Path) -> tuple[Path, ...]:
    path = Path(dotenv_path)
    if path.is_absolute():
        return (path,)
    project_path = Path(__file__).resolve().parents[1] / path
    cwd_path = Path.cwd() / path
    if cwd_path == project_path:
        return (cwd_path,)
    return (cwd_path, project_path)


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _openrouter_provider_only(value: str | None) -> tuple[str, ...]:
    if value is None or not value.strip():
        return ()
    providers = []
    for raw_provider in value.split(","):
        provider = raw_provider.strip()
        if not provider:
            continue
        providers.append(provider)
    return tuple(providers)


def _env_tuple(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_paths(value: str | None) -> tuple[Path, ...]:
    if value is None or not value.strip():
        return ()
    normalized = value.replace(os.pathsep, ",")
    return tuple(
        Path(item.strip()).expanduser()
        for item in normalized.split(",")
        if item.strip()
    )


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(env.get(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a float") from exc


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")
