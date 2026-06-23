from __future__ import annotations

import os
from pathlib import Path

import pytest

from rsc.artifact_protocol import ArtifactParser
from rsc.config import RSCConfig
from rsc.contracts import LoopStatus, RubricCriterion
from rsc.evaluator import Evaluator
from rsc.loop_orchestrator import LoopOrchestrator
from rsc.openrouter_adapter import OpenRouterClientAdapter, openrouter_provider_options
from rsc.prompt_assembler import PromptAssembler
from rsc.role_agent import RoleAgent
from rsc.search_provider import FirecrawlSearchProvider
from rsc.skill_runtime import build_skill_router, capabilities_from_config
from rsc.state_loader import StateLoader
from rsc.state_manager import StateManager

pytestmark = pytest.mark.live


class RecordingSearchProvider:
    name = "firecrawl-live"

    def __init__(self, inner: FirecrawlSearchProvider) -> None:
        self.inner = inner
        self.calls: list[tuple[str, int]] = []
        self.last_markdown = ""

    def search(self, query: str, *, max_results: int = 5) -> str:
        self.calls.append((query, max_results))
        self.last_markdown = self.inner.search(query, max_results=max_results)
        return self.last_markdown


def test_live_openrouter_firecrawl_full_pipeline(tmp_path: Path) -> None:
    if not _env_flag("RSC_LIVE_TESTS"):
        pytest.skip(
            "Set RSC_LIVE_TESTS=1 to run live OpenRouter + Firecrawl pipeline test"
        )

    pytest.importorskip("openrouter")
    config = RSCConfig.from_env(require_api_key=False)
    missing = []
    if not config.openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not config.firecrawl_api_key:
        missing.append("FIRECRAWL_API_KEY")
    if missing:
        pytest.skip(f"Missing live credentials: {', '.join(missing)}")

    state_dir = _write_live_state(tmp_path / "state")
    skill_root = _write_live_skill_library(tmp_path / "skill-library")
    model = os.getenv("RSC_LIVE_OPENROUTER_MODEL") or (
        config.loop_model if config.llm_provider == "openrouter" else "z-ai/glm-5.2"
    )
    client = OpenRouterClientAdapter(
        api_key=config.openrouter_api_key,
        model=model,
        provider=openrouter_provider_options(
            zdr=config.openrouter_provider_zdr,
            only=config.openrouter_provider_only,
        ),
        x_open_router_title=config.openrouter_app_title,
    )
    search_provider = RecordingSearchProvider(
        FirecrawlSearchProvider(
            api_key=config.firecrawl_api_key,
            endpoint=config.firecrawl_search_endpoint,
            max_age_ms=config.firecrawl_max_age_ms,
            max_concurrency=2,
        )
    )
    prompt_assembler = PromptAssembler(model, max_input_tokens_per_call=8000)
    try:
        role_agent = RoleAgent(
            client=client,
            model=model,
            prompt_assembler=prompt_assembler,
            artifact_parser=ArtifactParser(),
            max_output_tokens=700,
        )
        evaluator = Evaluator(client, model, prompt_assembler)
        orchestrator = LoopOrchestrator(
            client=client,
            model=model,
            state_loader=StateLoader(state_dir),
            state_manager=StateManager(state_dir, client=client),
            role_agent=role_agent,
            evaluator=evaluator,
            prompt_assembler=prompt_assembler,
            search_over_inference=None,
            search_provider=search_provider,
            search_max_results=1,
            skill_router=build_skill_router(
                [skill_root],
                available_capabilities=capabilities_from_config(config),
            ),
            skill_top_k=1,
            max_turns=1,
            max_depth=0,
            max_total_tokens_per_session=60000,
        )
        task = (
            "Use current web context to answer in one concise sentence: "
            "what is Firecrawl used for by AI applications?"
        )
        result = orchestrator.run(
            task=task,
            rubric=[
                RubricCriterion(
                    label="answer",
                    description="The final answer is nonempty and addresses the question.",
                ),
                RubricCriterion(
                    label="grounded",
                    description="The answer uses the injected web search context.",
                ),
            ],
            skill_name="live-routing",
            session_id="live-openrouter-firecrawl",
        )
    finally:
        client.close()

    assert search_provider.calls == [(task, 1)]
    assert search_provider.last_markdown.strip()
    assert result.status in {LoopStatus.PASSED, LoopStatus.EXHAUSTED}
    assert result.turns_used == 1
    assert result.total_tokens_input > 0
    assert result.total_tokens_output > 0
    assert result.final_output.strip()
    assert result.turns[0].verdict is not None
    assert all(
        result.turns[0].role_outputs[role].strip()
        for role in ["planner", "critic", "verifier", "reviser", "synthesizer"]
    )


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        value = _dotenv_value(name)
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _dotenv_value(name: str) -> str | None:
    path = Path(".env")
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return None


def _write_live_state(path: Path) -> Path:
    (path / "skills").mkdir(parents=True)
    (path / "claude.md").write_text(
        "---\n"
        "values_and_principles: Use supplied search context and be concise.\n"
        "constraints:\n"
        "  - Do not invent sources.\n"
        "conduct_rules:\n"
        "  - Answer only the requested question.\n"
        "---\n",
        encoding="utf-8",
    )
    (path / "memory.md").write_text(
        "---\nhistory_summary: ''\nongoing_context: ''\ndistilled_rules: []\n---\n",
        encoding="utf-8",
    )
    (path / "memory_ledger.json").write_text(
        '{"schema_version": "1.0", "entries": []}', encoding="utf-8"
    )
    (path / "skills" / "live-routing.md").write_text(
        "---\n"
        "name: live-routing\n"
        "task_specific_rules:\n"
        "  - Use the Firecrawl search result when planning.\n"
        "domain_knowledge: Live integration pipeline validation.\n"
        "conventions: []\n"
        "templates: {}\n"
        "---\n",
        encoding="utf-8",
    )
    return path


def _write_live_skill_library(path: Path) -> Path:
    skill_dir = path / "live-routing"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Live Routing\n\n"
        "Use web search context, verify the answer is concise, and keep the final "
        "response grounded in the retrieved markdown.",
        encoding="utf-8",
    )
    return path
