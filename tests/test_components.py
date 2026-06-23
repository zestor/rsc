from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

import pytest

from rsc.artifact_protocol import ArtifactParser
from rsc.config import RSCConfig, _dotenv_candidates, _env_paths, _merged_env
from rsc.contracts import (
    ArtifactState,
    ComposedState,
    EvalVerdict,
    LoopTurnRecord,
    MemoryEntry,
    MemoryStage,
    RoleInput,
    RoleOutput,
    RoleType,
    SelectedSkill,
    SkillReadiness,
)
from rsc.evaluator import Evaluator
from rsc.loop_orchestrator import LoopOrchestrator
from rsc.exceptions import ArtifactParseError, ConfigurationError, StateLoadError
from rsc.openai_responses_adapter import OpenAIResponsesClientAdapter
from rsc.openrouter_adapter import OpenRouterClientAdapter, openrouter_provider_options
from rsc.role_agent import RoleAgent
from rsc.retry import RetryPolicy, is_retryable_exception, retry_call
from rsc.prompt_assembler import DIVERSITY_INJECTION_TEXT, PromptAssembler
from rsc.search_inference import SearchOverInference
from rsc.search_provider import (
    FirecrawlSearchProvider,
    FunctionSearchProvider,
    HTTPMarkdownSearchProvider,
    SearchProviderError,
    strip_unwanted_media_tags,
)
from rsc.skill_runtime import (
    CapabilityBroker,
    HybridSkillRouter,
    ReferenceLoader,
    SkillDiscovery,
    build_skill_router,
    capabilities_from_config,
    cosine_similarity,
    hashing_vectorize,
)
from rsc.state_loader import StateLoader
from rsc.state_manager import StateManager
from rsc.observability import (
    DailyJSONFileHandler,
    JSONFormatter,
    configure_daily_file_logging,
    get_logger,
    log_event,
    text_summary,
)

from tests.conftest import FakeLLMClient, FakeStreamChoice, FakeStreamChunk, FakeDelta
from tests.test_loop_orchestrator import QueueEvaluator, composed_state, rubric


def role_input(
    role: RoleType = RoleType.PLANNER, prior: str | None = None
) -> RoleInput:
    return RoleInput(
        task="task",
        rubric=rubric(),
        role=role,
        prior_output=prior,
        composed_state=composed_state(),
        turn=1,
        session_id="s",
    )


def test_artifact_parser_extracts_decisions_and_injects_results():
    text = (
        'before <!--ARTIFACT:START id="x" recurse="true" -->payload<!--ARTIFACT:END id="x" --> '
        "<!--DECISION: ship it -->"
    )
    parser = ArtifactParser()
    artifacts = parser.extract(text, RoleType.REVISER, 2)
    assert artifacts[0].artifact_id == "x"
    assert artifacts[0].can_invoke_model is True
    assert parser.extract_decisions(text) == ["ship it"]
    assert "## Recursive Result: x\ndone" in parser.inject_recursive_result(
        text, "x", "done"
    )


def test_artifact_parser_rejects_duplicate_ids():
    text = (
        '<!--ARTIFACT:START id="x" recurse="false" -->one<!--ARTIFACT:END id="x" -->'
        '<!--ARTIFACT:START id="x" recurse="false" -->two<!--ARTIFACT:END id="x" -->'
    )
    with pytest.raises(ArtifactParseError):
        ArtifactParser().extract(text, RoleType.PLANNER, 1)


def test_function_search_provider_requires_markdown_string():
    provider = FunctionSearchProvider(
        lambda query, max_results: f"# {query} {max_results}"
    )
    assert provider.search("q", max_results=3) == "# q 3"
    bad_provider = FunctionSearchProvider(
        lambda query, max_results: {"not": "markdown"}
    )
    with pytest.raises(SearchProviderError):
        bad_provider.search("q")


def test_http_markdown_search_provider_get_and_post(monkeypatch):
    seen: list[request.Request] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"# markdown"

    def fake_urlopen(req, timeout):
        del timeout
        seen.append(req)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    get_provider = HTTPMarkdownSearchProvider(
        "https://search.example/search", method="GET"
    )
    assert get_provider.search("hello world") == "# markdown"
    assert "hello+world" in seen[-1].full_url
    post_provider = HTTPMarkdownSearchProvider(
        "https://search.example/search", method="POST"
    )
    assert post_provider.search("hello") == "# markdown"
    assert seen[-1].get_method() == "POST"
    with pytest.raises(SearchProviderError):
        HTTPMarkdownSearchProvider(
            "https://search.example/search", method="PUT"
        ).search("x")


def test_firecrawl_search_provider_posts_documented_payload(monkeypatch):
    seen: list[request.Request] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "success": True,
                    "data": {
                        "web": [
                            {
                                "url": "https://example.com",
                                "title": "Example",
                                "description": "Description",
                                "position": 1,
                                "markdown": "# Example markdown",
                            }
                        ]
                    },
                }
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        del timeout
        seen.append(req)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    markdown = FirecrawlSearchProvider(api_key="secret", max_age_ms=123).search(
        "current facts", max_results=20
    )
    request_payload = json.loads(seen[0].data.decode("utf-8"))
    assert seen[0].headers["Authorization"] == "Bearer secret"
    assert request_payload["query"] == "current facts"
    assert request_payload["sources"] == ["web"]
    assert request_payload["limit"] == 20
    assert request_payload["scrapeOptions"]["formats"] == ["markdown"]
    assert request_payload["scrapeOptions"]["maxAge"] == 123
    assert "# Example markdown" in markdown


def test_strip_unwanted_media_tags_removes_html_and_markdown_images():
    raw = (
        "# Title\n\n"
        '<img src="https://example.com/big.jpg" alt="Thumbnail" />\n'
        '<video controls><source src="clip.mp4"/></video>\n'
        '<iframe src="https://embed.example.com"></iframe>\n'
        "<script>alert('x')</script>\n"
        "<style>body { color: red; }</style>\n"
        "![alt text](https://example.com/pic.png)\n"
        "Normal text stays.\n"
    )
    cleaned = strip_unwanted_media_tags(raw)
    assert "<img" not in cleaned
    assert "<video" not in cleaned
    assert "<iframe" not in cleaned
    assert "<script" not in cleaned
    assert "<style" not in cleaned
    assert "![alt text]" not in cleaned
    assert "Normal text stays." in cleaned
    assert "# Title" in cleaned


def test_firecrawl_search_provider_strips_media_tags_from_markdown(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "success": True,
                    "data": {
                        "web": [
                            {
                                "url": "https://example.com",
                                "title": "Example",
                                "description": "Description",
                                "position": 1,
                                "markdown": (
                                    "# Example\n\n"
                                    '<img src="https://example.com/huge.jpg" alt="Thumbnail (1920x1080)" />\n\n'
                                    "This is a detailed article about Python programming. "
                                    "It covers many important topics and best practices. "
                                    "The third sentence provides additional context.\n\n"
                                    "![thumb](https://example.com/pic.png)\n\n"
                                    '<iframe src="https://embed.example.com"></iframe>\n'
                                ),
                            }
                        ]
                    },
                }
            ).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: FakeResponse())
    markdown = FirecrawlSearchProvider(api_key="secret").search("test", max_results=5)
    assert "<img" not in markdown
    assert "<iframe" not in markdown
    assert "![thumb]" not in markdown
    assert "detailed article about Python" in markdown
    assert "# Example" in markdown


def test_firecrawl_search_provider_handles_errors(monkeypatch):
    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"success": false, "error": "bad"}'

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: EmptyResponse())
    with pytest.raises(SearchProviderError):
        FirecrawlSearchProvider().search("q")


def test_firecrawl_search_provider_limits_concurrent_requests(monkeypatch):
    active = 0
    max_seen = 0
    entered_count = 0
    lock = threading.Lock()
    first_two_entered = threading.Event()
    release_requests = threading.Event()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"success": true, "data": {"web": []}}'

    def fake_urlopen(req, timeout):
        del req, timeout
        nonlocal active, max_seen, entered_count
        with lock:
            active += 1
            entered_count += 1
            max_seen = max(max_seen, active)
            if entered_count == 2:
                first_two_entered.set()
        release_requests.wait(timeout=2)
        with lock:
            active -= 1
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = FirecrawlSearchProvider(max_concurrency=2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(provider.search, f"query {index}") for index in range(4)
        ]
        assert first_two_entered.wait(timeout=2)
        with lock:
            assert entered_count == 2
            assert max_seen == 2
        release_requests.set()
        assert all("# Web Search Results" in future.result() for future in futures)

    with pytest.raises(SearchProviderError):
        FirecrawlSearchProvider(max_concurrency=51)


def test_retry_call_uses_five_staggered_retries():
    attempts = 0
    delays: list[float] = []

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts <= 5:
            raise TimeoutError("temporary")
        return "ok"

    result = retry_call(
        operation,
        policy=RetryPolicy(max_retries=5, base_delay_seconds=5),
        sleep=delays.append,
    )
    assert result == "ok"
    assert attempts == 6
    assert delays == [5, 10, 15, 20, 25]


def test_retry_call_stops_on_non_retryable_error():
    calls = 0

    class BadRequestError(Exception):
        pass

    def operation():
        nonlocal calls
        calls += 1
        raise BadRequestError("bad")

    with pytest.raises(BadRequestError):
        retry_call(operation, sleep=lambda delay: None)
    assert calls == 1
    assert is_retryable_exception(TimeoutError("x")) is True
    assert is_retryable_exception(BadRequestError("x")) is False


def test_http_search_provider_retries_urlopen(monkeypatch):
    calls = 0

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"# ok"

    def fake_urlopen(req, timeout):
        del req, timeout
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise TimeoutError("temporary")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    provider = HTTPMarkdownSearchProvider("https://search.example/search")
    assert provider.search("q") == "# ok"
    assert calls == 3


def test_prompt_assembler_role_templates_and_scores():
    assembler = PromptAssembler("not-a-real-model-name")
    planner = role_input(RoleType.PLANNER)
    planner.inject_diversity = True
    assert DIVERSITY_INJECTION_TEXT in assembler.build_role_user_message(planner)
    assert "PLANNER OUTPUT:\nplan" in assembler.build_role_user_message(
        role_input(RoleType.CRITIC, "plan")
    )
    assert "PLANNER OUTPUT:\nplan" in assembler.build_role_user_message(
        role_input(RoleType.VERIFIER, "plan")
    )
    assert (
        assembler.build_role_user_message(role_input(RoleType.REVISER, "prior"))
        == "prior\n\nRUBRIC:\n1. [complete] Finish the task"
    )
    assert (
        assembler.build_role_user_message(
            role_input(RoleType.SYNTHESIZER, "prior\nRUBRIC:\nalready")
        )
        == "prior\nRUBRIC:\nalready"
    )
    system, user = assembler.build_evaluator_messages("task", rubric(), "out")
    assert "strict, independent" in system
    assert "SUBMITTED OUTPUT:\nout" in user
    distill_system, distill_user = assembler.build_distill_messages(
        "task",
        [
            LoopTurnRecord(
                turn=1, verdict=EvalVerdict(passed=False, score=0.5, critique="c")
            )
        ],
    )
    assert "extracting long-term" in distill_system
    assert "Turn 1: score=0.5, critique=c" in distill_user
    compress_system, compress_user = assembler.build_compress_messages(
        {"fail": ["bad"]}
    )
    assert "compressing old memory" in compress_system
    assert "## fail\n- bad" == compress_user
    table = "| ITEM | VERDICT | REASON |\n|---|---|---|\n| a | PASS | ok |\n| b | FAIL | no |\n| c | UNCERTAIN | maybe |"
    assert assembler.verifier_output_score(table) == 0.3333
    assert assembler.verifier_output_score("| too | short |\n| a | MAYBE | no |") == 0.0
    assert assembler.verifier_output_score("not a table") == 0.0


def test_prompt_assembler_truncates_domain_knowledge_tail():
    state = composed_state()
    state.skill.domain_knowledge = "domain " * 800
    assembler = PromptAssembler("gpt-4o", max_input_tokens_per_call=250)
    prompt = assembler.build_role_system_prompt(
        RoleInput(
            task="task",
            rubric=rubric(),
            role=RoleType.PLANNER,
            composed_state=state,
            turn=1,
            session_id="s",
        )
    )
    assert "You are the PLANNER agent" in prompt


def test_prompt_assembler_renders_selected_skills():
    state = composed_state()
    state.artifact.selected_skills = [
        SelectedSkill(
            skill_id="coding.python",
            name="Python Coding",
            score=0.91,
            lexical_score=0.8,
            readiness=SkillReadiness.READY,
            reason="matched python",
            source_file="skills/coding/SKILL.md",
            content_excerpt="Use pytest and small changes.",
            references_loaded=["skills/coding/references/testing.md"],
        )
    ]
    system = PromptAssembler("gpt-5.5").build_role_system_prompt(
        RoleInput(
            task="fix python tests",
            rubric=rubric(),
            role=RoleType.PLANNER,
            composed_state=state,
            turn=1,
            session_id="s",
        )
    )
    assert "## SELECTED SKILLS" in system
    assert "Skill 1: coding.python" in system
    assert "Use pytest and small changes." in system


def test_skill_discovery_router_loads_references_and_ranks(tmp_path: Path):
    skill_root = tmp_path / "skills"
    coding = skill_root / "coding" / "python"
    refs = coding / "references"
    refs.mkdir(parents=True)
    (refs / "testing.md").write_text(
        "Always run pytest after code edits.", encoding="utf-8"
    )
    (coding / "SKILL.md").write_text(
        "# Python Coding\n\nUse Python, pytest, and repository evidence.\n\nSee [testing](references/testing.md).",
        encoding="utf-8",
    )
    (skill_root / "marketing").mkdir()
    (skill_root / "marketing" / "SKILL.md").write_text(
        "# Marketing\n\nPlan campaigns and brand voice.", encoding="utf-8"
    )
    documents = SkillDiscovery([skill_root]).discover()
    assert {document.skill_id for document in documents} == {
        "coding.python",
        "marketing",
    }
    router = HybridSkillRouter(documents)
    result = router.route("fix the Python pytest failure", top_k=2)
    assert result.discovered_count == 2
    assert result.selected[0].skill_id == "coding.python"
    assert result.selected[0].readiness == SkillReadiness.READY
    assert result.selected[0].references_loaded[0].endswith("testing.md")
    assert "Always run pytest" in result.selected[0].content_excerpt


def test_skill_capability_resolver_marks_blocked_and_degraded(tmp_path: Path):
    skill_root = tmp_path / "skills"
    blocked = skill_root / "sales"
    blocked.mkdir(parents=True)
    (blocked / "SKILL.md").write_text(
        "# Sales Connector\n\nRequires an API key credential and external connector.",
        encoding="utf-8",
    )
    skill = SkillDiscovery([skill_root]).discover()[0]
    report = CapabilityBroker(available={"python"}).resolve(skill)
    assert report.readiness == SkillReadiness.BLOCKED
    assert "credentials" in report.missing
    degraded_report = CapabilityBroker(available={"credentials"}).resolve(skill)
    assert degraded_report.readiness == SkillReadiness.DEGRADED
    assert "external_connector" in degraded_report.degraded


def test_hashing_vector_cosine_and_skill_router_builder(tmp_path: Path):
    left = hashing_vectorize("python tests")
    right = hashing_vectorize("python tests")
    assert cosine_similarity(left, right) == pytest.approx(1.0)
    assert build_skill_router([tmp_path / "missing"]) is None
    config = RSCConfig.from_env(
        {
            "OPENAI_API_KEY": "key",
            "SEARCH_PROVIDER": "none",
            "SKILL_LIBRARY_PATHS": str(tmp_path / "missing"),
        },
        require_api_key=False,
    )
    assert "web_search" not in capabilities_from_config(config)
    assert config.skill_library_paths == (tmp_path / "missing",)


def test_skill_router_uses_embeddings_and_handles_embedding_failures(tmp_path: Path):
    skill_root = tmp_path / "skills"
    (skill_root / "coding").mkdir(parents=True)
    (skill_root / "coding" / "SKILL.md").write_text(
        "# Coding\n\nImplement Python code and tests.", encoding="utf-8"
    )
    (skill_root / "sales").mkdir()
    (skill_root / "sales" / "SKILL.md").write_text(
        "# Sales\n\nPrepare account research.", encoding="utf-8"
    )
    documents = SkillDiscovery([skill_root]).discover()
    client = FakeLLMClient(embedding_vectors=[[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    router = HybridSkillRouter(documents, embedding_client=client)
    result = router.route("write python code", top_k=1)
    assert result.selected[0].semantic_score > 0.0

    class FailingEmbeddings:
        def create(self, **kwargs):
            del kwargs
            raise RuntimeError("embedding down")

    class FailingClient:
        embeddings = FailingEmbeddings()

    fallback_router = HybridSkillRouter(documents, embedding_client=FailingClient())
    fallback_result = fallback_router.route("write python code", top_k=1)
    assert fallback_result.selected[0].semantic_score == 0.0


def test_build_skill_router_returns_router_for_existing_root(tmp_path: Path):
    skill_root = tmp_path / "skills"
    (skill_root / "data").mkdir(parents=True)
    (skill_root / "data" / "SKILL.md").write_text(
        "# Data\n\nAnalyze SQL data.", encoding="utf-8"
    )
    router = build_skill_router([skill_root])
    assert router is not None
    assert router.route("sql analysis", top_k=1).selected[0].skill_id == "data"


def test_reference_loader_ignores_remote_missing_and_parent_links(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "coding"
    skill_dir.mkdir(parents=True)
    (skill_dir / "local.md").write_text("local", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "# Coding\n\n[local](local.md) [remote](https://example.com) [parent](../x.md) [missing](missing.md)",
        encoding="utf-8",
    )
    skill = SkillDiscovery([skill_root]).discover()[0]
    loaded = ReferenceLoader().load(skill)
    assert [Path(reference.path).name for reference in loaded] == ["local.md"]


def test_openai_responses_adapter_maps_chat_shape_to_current_api():
    class ResponseUsage:
        input_tokens = 11
        output_tokens = 7

    class Response:
        output_text = "done"
        usage = ResponseUsage()

    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return Response()

    class Client:
        def __init__(self) -> None:
            self.responses = Responses()
            self.embeddings = object()

    client = Client()
    adapter = OpenAIResponsesClientAdapter(client)
    completion = adapter.chat.completions.create(
        model="gpt-5.5",
        messages=[
            {"role": "system", "content": "sample system prompt"},
            {"role": "user", "content": "sample user message"},
        ],
        response_format={"type": "json_object"},
        max_tokens=123,
    )
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5.5"
    assert call["input"][0]["role"] == "developer"
    assert call["input"][0]["content"][0]["type"] == "input_text"
    assert call["text"] == {"format": {"type": "json_object"}, "verbosity": "medium"}
    assert call["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert call["tools"] == []
    assert call["store"] is True
    assert "reasoning.encrypted_content" in call["include"]
    assert call["max_output_tokens"] == 123
    assert completion.choices[0].message.content == "done"
    assert completion.usage.prompt_tokens == 11
    assert completion.usage.completion_tokens == 7


def test_openai_responses_adapter_extracts_nested_output_and_default_usage():
    class Content:
        text = "nested"

    class Output:
        content = [Content()]

    class Response:
        output = [Output()]

    class Responses:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return Response()

    class Client:
        def __init__(self) -> None:
            self.responses = Responses()
            self.embeddings = object()

    client = Client()
    adapter = OpenAIResponsesClientAdapter(client, include=[])
    completion = adapter.chat.completions.create(
        model="gpt-5.5",
        messages=[{"role": "user", "content": "hello"}],
    )
    assert client.responses.calls[0]["text"]["format"] == {"type": "text"}
    assert completion.choices[0].message.content == "nested"
    assert completion.usage.prompt_tokens == 0
    assert completion.usage.completion_tokens == 0


def test_state_loader_loads_front_matter_rendered_memory_and_missing(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    (tmp_path / "claude.md").write_text("---\nvalues_and_principles: base\n---\nbody")
    (tmp_path / "memory.md").write_text(
        "# Memory State\n\n## Distilled Rules\n- one\n\n## Ongoing Context\nctx\n\n## History Summary\nhist\n"
    )
    (tmp_path / "skills" / "coding.md").write_text(
        "---\ntask_specific_rules:\n  - typed\n---\n"
    )
    loaded = StateLoader(tmp_path).load("coding", ArtifactState(session_id="s"))
    assert "Supplemental Constitution Notes" in loaded.claude.values_and_principles
    assert loaded.memory.distilled_rules == ["one"]
    assert loaded.memory.ongoing_context == "ctx"
    assert loaded.skill.name == "coding"
    missing = StateLoader(tmp_path).load("missing", ArtifactState(session_id="s"))
    assert missing.skill.name == "missing"


def test_state_loader_rejects_bad_yaml(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    (tmp_path / "claude.md").write_text("---\n[unclosed\n---\n")
    with pytest.raises(StateLoadError):
        StateLoader(tmp_path).load("default", ArtifactState())
    assert StateLoader._parse_front_matter("plain") == ({}, "plain")
    assert StateLoader._parse_front_matter("---\nno close") == ({}, "---\nno close")
    with pytest.raises(StateLoadError):
        StateLoader._parse_front_matter("---\n- list\n---\n")


def test_state_loader_missing_files_return_empty_layers(tmp_path: Path):
    loaded = StateLoader(tmp_path).load("default", ArtifactState())
    assert loaded.claude.constraints == []
    assert loaded.memory.distilled_rules == []
    assert loaded.skill.name == "default"


def test_state_manager_updates_saves_and_compresses(state_dir: Path):
    client = FakeLLMClient(["compressed summary"])
    manager = StateManager(state_dir, client=client, max_ledger_entries=1)
    artifact = manager.update_artifact_state(
        ArtifactState(session_id="s"),
        RoleOutput(
            role=RoleType.PLANNER,
            content="plan <!--DECISION: choose x -->",
            tokens_used_input=2,
            tokens_used_output=3,
            elapsed_seconds=0.5,
        ),
        1,
    )
    assert artifact.current_plan.startswith("plan")
    assert artifact.decisions == ["choose x"]
    assert artifact.metrics["tokens_input_cumulative"] == 2
    manager.save_artifact_state(artifact)
    assert (
        json.loads((state_dir / "artifact_state.json").read_text())["current_turn"] == 1
    )
    manager.append_memory_entry(
        MemoryEntry(task_hint="t", stage=MemoryStage.FAIL, content="f", session_id="s")
    )
    manager.append_memory_entry(
        MemoryEntry(
            task_hint="t", stage=MemoryStage.INVESTIGATE, content="i", session_id="s"
        )
    )
    ledger = json.loads((state_dir / "memory_ledger.json").read_text())
    assert ledger["entries"][-1]["stage"] == MemoryStage.COMPRESSED_SUMMARY.value


def test_state_manager_alternate_lock_and_empty_ledger_paths(state_dir: Path):
    manager = StateManager(state_dir)
    (state_dir / "memory_ledger.json").write_text("")
    assert manager._read_ledger() == {"schema_version": "1.0", "entries": []}
    manager._lock_backend = "portalocker"
    manager._atomic_write_text(state_dir / "alt.txt", "ok")
    assert (state_dir / "alt.txt").read_text() == "ok"


def test_state_manager_compress_no_selected_entries(state_dir: Path):
    client = FakeLLMClient(["unused"])
    manager = StateManager(state_dir, client=client)
    summary = MemoryEntry(
        task_hint="t",
        stage=MemoryStage.COMPRESSED_SUMMARY,
        content="summary",
        session_id="s",
    )
    (state_dir / "memory_ledger.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "entries": [summary.model_dump(mode="json")]}
        )
    )
    manager.compress_memory()
    assert client.call_log == []


def test_state_manager_atomic_write_cleans_temp_on_failure(
    state_dir: Path, monkeypatch
):
    manager = StateManager(state_dir)

    def fail_replace(source, target):
        del source, target
        raise OSError("replace failed")

    monkeypatch.setattr("os.replace", fail_replace)
    with pytest.raises(OSError):
        manager._write_text_unlocked(state_dir / "broken.txt", "x")
    assert not list(state_dir.glob("tmp*"))


def test_state_manager_requires_client_for_distill_and_compress(state_dir: Path):
    manager = StateManager(state_dir)
    with pytest.raises(ConfigurationError):
        manager.distill_to_memory("task", [])
    with pytest.raises(ConfigurationError):
        manager.compress_memory()
    manager.embedder_enabled = True
    with pytest.raises(ConfigurationError):
        manager._is_semantic_duplicate("x", ["y"])
    assert manager._session_id([]) == "session"


def test_state_manager_distill_handles_malformed_json(state_dir: Path):
    client = FakeLLMClient(["not json"])
    manager = StateManager(state_dir, client=client)
    assert manager.distill_to_memory("task", [], client) == []


def test_state_manager_semantic_embedding_deduplicates_rules(state_dir: Path):
    client = FakeLLMClient(
        ['{"rules": ["same idea", "different idea"]}'],
        embedding_vectors=[
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
        ],
    )
    manager = StateManager(state_dir, client=client, embedder_enabled=True)
    manager.append_memory_entry(
        MemoryEntry(
            task_hint="t",
            stage=MemoryStage.DISTILL,
            content="existing idea",
            session_id="s",
        )
    )
    assert manager.distill_to_memory("task", [], client) == ["different idea"]
    embedding_calls = [call for call in client.call_log if "input" in call]
    assert embedding_calls[0]["model"] == "text-embedding-3-large"


def test_cosine_similarity_handles_zero_vectors():
    assert StateManager._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert StateManager._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_config_from_env_validates_values():
    config = RSCConfig.from_env(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "key",
            "MAX_TURNS": "2",
            "MAX_DEPTH": "1",
            "PASS_THRESHOLD": "0.5",
            "N_CANDIDATES": "4",
            "STATE_DIR": "/tmp/rsc-state",
            "EMBEDDER_ENABLED": "true",
            "SEARCH_MAX_CONCURRENCY": "2",
        }
    )
    assert config.openai_api_key == "key"
    assert config.loop_model == "gpt-5.5"
    assert config.eval_model == "gpt-5.5"
    assert config.log_dir == Path("./rsc/logs")
    assert config.max_input_tokens_per_call == 200000
    assert config.max_output_tokens_per_call == 65536
    assert config.max_total_tokens_per_session == 2000000
    assert config.max_turns == 2
    assert config.embedder_enabled is True
    assert config.search_max_concurrency == 2
    assert config.search_query_count == 3
    default_config = RSCConfig.from_env({}, require_api_key=False)
    assert default_config.llm_provider == "openrouter"
    assert default_config.loop_model == "z-ai/glm-5.2"
    assert default_config.eval_model == "z-ai/glm-5.2"
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env({}, require_api_key=True)
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "key", "MAX_TURNS": "bad"}
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "key",
                "EMBEDDER_ENABLED": "maybe",
            }
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "key",
                "SEARCH_MAX_CONCURRENCY": "1",
            }
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env({"LLM_PROVIDER": "bad", "OPENAI_API_KEY": "key"})
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "key",
                "OPENAI_TEXT_VERBOSITY": "nope",
            }
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "key",
                "OPENAI_REASONING_EFFORT": "nope",
            }
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "key", "SKILL_TOP_K": "0"}
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env(
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "key",
                "SEARCH_QUERY_COUNT": "6",
            }
        )
    with pytest.raises(ConfigurationError):
        RSCConfig.from_env({"LLM_PROVIDER": "openrouter"}, require_api_key=True)
    with pytest.raises(ConfigurationError):
        RSCConfig(max_turns=0).validate()


def test_config_supports_openrouter_provider():
    config = RSCConfig.from_env(
        {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "router-key",
            "OPENROUTER_PROVIDER_ZDR": "true",
            "OPENROUTER_PROVIDER_ONLY": "fireworks,wafer,cloudflare,friendli",
        }
    )
    assert config.llm_provider == "openrouter"
    assert config.openrouter_api_key == "router-key"
    assert config.openrouter_provider_zdr is True
    assert config.openrouter_provider_only == (
        "fireworks",
        "wafer",
        "cloudflare",
        "friendli",
    )
    assert config.loop_model == "z-ai/glm-5.2"
    assert config.eval_model == "z-ai/glm-5.2"
    # Any provider string from .env is accepted without hard-coded checks.
    arbitrary = RSCConfig.from_env(
        {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "router-key",
            "OPENROUTER_PROVIDER_ONLY": "google-vertex,some-new-provider",
        }
    )
    assert arbitrary.openrouter_provider_only == ("google-vertex", "some-new-provider")


def test_config_validation_branch_errors_and_dotenv_helpers(tmp_path: Path):
    invalid_configs = [
        RSCConfig(llm_provider="openai", max_depth=-1),
        RSCConfig(llm_provider="openai", pass_threshold=1.5),
        RSCConfig(llm_provider="openai", n_candidates=1),
        RSCConfig(llm_provider="openai", max_input_tokens_per_call=0),
        RSCConfig(llm_provider="openai", max_output_tokens_per_call=0),
        RSCConfig(llm_provider="openai", max_total_tokens_per_session=0),
        RSCConfig(llm_provider="openai", search_method="PUT"),
        RSCConfig(llm_provider="openai", search_max_results=0),
        RSCConfig(llm_provider="openai", search_provider="bad"),
        RSCConfig(llm_provider="openai", firecrawl_max_age_ms=-1),
    ]
    for config in invalid_configs:
        with pytest.raises(ConfigurationError):
            config.validate()

    with pytest.raises(ConfigurationError):
        RSCConfig(llm_provider="openai").validate(require_api_key=True)

    absolute = tmp_path / ".env"
    absolute.write_text("ABSOLUTE_VALUE=yes\n", encoding="utf-8")
    assert _dotenv_candidates(absolute) == (absolute,)
    assert _merged_env(None)["PATH"]
    assert _merged_env(absolute)["ABSOLUTE_VALUE"] == "yes"
    assert _env_paths(f"{tmp_path / 'one'}{os.pathsep}{tmp_path / 'two'}") == (
        tmp_path / "one",
        tmp_path / "two",
    )


def test_config_loads_firecrawl_key_from_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LLM_PROVIDER=openai\nOPENAI_API_KEY=openai\nFIRECRAWL_API_KEY=firecrawl\nSEARCH_MAX_RESULTS=20\n",
        encoding="utf-8",
    )
    config = RSCConfig.from_env(dotenv_path=dotenv)
    assert config.firecrawl_api_key == "firecrawl"
    assert config.search_max_results == 20


def test_json_formatter_and_log_event():
    logger = get_logger("unit")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    log_event(logger, "unit.event", session_id="s", depth=2, answer=42)
    output = json.loads(stream.getvalue())
    assert output["schema_version"] == "rsc.log.v2"
    assert output["event"] == "unit.event"
    assert output["answer"] == 42
    summary = text_summary("hello\nworld", preview_chars=5)
    assert summary["chars"] == 11
    assert summary["preview"] == "hello..."
    assert summary["text"] == "hello\nworld"
    assert summary["line_count"] == 2
    assert len(summary["sha256"]) == 64
    record = logging.LogRecord(
        "rsc.unit", logging.INFO, __file__, 1, "unit.event", (), None
    )
    record.event = "unit.event"
    record.session_id = "s"
    record.depth = 2
    record.fields = {"answer": 42}
    payload = json.loads(JSONFormatter().format(record))
    assert payload["event"] == "unit.event"
    assert payload["session_id"] == "s"
    assert payload["answer"] == 42


def test_daily_json_file_logging_writes_today_jsonl(tmp_path: Path):
    log_dir = tmp_path / "rsc" / "logs"
    logger_name = "rsc.daily-test"
    logger = logging.getLogger(logger_name)
    old_handlers = logger.handlers[:]
    old_propagate = logger.propagate
    try:
        logger.handlers = []
        configure_daily_file_logging(log_dir, logger_name=logger_name, level="INFO")
        configure_daily_file_logging(log_dir, logger_name=logger_name, level="INFO")
        assert (
            sum(
                isinstance(handler, DailyJSONFileHandler) for handler in logger.handlers
            )
            == 1
        )
        log_event(
            logger,
            "daily.event",
            session_id="s",
            depth=1,
            payload=text_summary("complete payload"),
        )
    finally:
        logger.handlers = old_handlers
        logger.propagate = old_propagate
    today = datetime.now(timezone.utc).date().isoformat()
    path = log_dir / f"rsc-{today}.jsonl"
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["event"] == "daily.event"
    assert record["payload"]["text"] == "complete payload"


def test_openrouter_adapter_exposes_chat_completion_shape():
    class FakeOpenRouterChat:
        def __init__(self) -> None:
            self.calls = []

        def send(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "choices": [{"message": {"content": "router response"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            }

    class FakeOpenRouterSDK:
        def __init__(self) -> None:
            self.chat = FakeOpenRouterChat()

    sdk = FakeOpenRouterSDK()
    adapter = OpenRouterClientAdapter(
        api_key="router-key",
        model="z-ai/glm-5.2",
        sdk=sdk,
        reasoning_effort="xhigh",
        provider=openrouter_provider_options(
            zdr=True,
            only=("fireworks", "wafer", "cloudflare", "friendli"),
        ),
    )
    completion = adapter.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.1,
        max_tokens=100,
    )
    assert completion.choices[0].message.content == "router response"
    assert adapter.model == "z-ai/glm-5.2"
    assert completion.usage.prompt_tokens == 3
    assert sdk.chat.calls[0]["provider"] == {
        "zdr": True,
        "only": ["fireworks", "wafer", "cloudflare", "friendli"],
    }
    assert sdk.chat.calls[0]["stream"] is False
    assert sdk.chat.calls[0]["reasoning"] == {"effort": "xhigh"}


def test_openrouter_adapter_passes_through_stream():
    class FakeOpenRouterChat:
        def send(self, **kwargs):
            assert kwargs["stream"] is True
            return iter([{"choices": [{"delta": {"content": "hi"}}]}])

    class FakeOpenRouterSDK:
        def __init__(self) -> None:
            self.chat = FakeOpenRouterChat()

    adapter = OpenRouterClientAdapter(api_key="router-key", sdk=FakeOpenRouterSDK())
    stream = adapter.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert list(stream) == [{"choices": [{"delta": {"content": "hi"}}]}]


def test_openrouter_adapter_extracts_reasoning_text():
    class FakeOpenRouterChat:
        def send(self, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "answer",
                            "reasoning_details": [
                                {
                                    "type": "reasoning.summary",
                                    "summary": "reason summary",
                                },
                                {"type": "reasoning.text", "text": "step by step"},
                            ],
                        }
                    }
                ]
            }

    class FakeOpenRouterSDK:
        def __init__(self) -> None:
            self.chat = FakeOpenRouterChat()

    adapter = OpenRouterClientAdapter(api_key="router-key", sdk=FakeOpenRouterSDK())
    completion = adapter.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert completion.choices[0].message.reasoning == "reason summary\n\nstep by step"


def test_openrouter_adapter_requires_sdk_or_installed_package(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openrouter":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ConfigurationError):
        OpenRouterClientAdapter(api_key="router-key")


def test_evaluator_malformed_json_and_missing_labels():
    malformed = FakeLLMClient(["oops"])
    evaluator = Evaluator(malformed, "gpt-4o-mini", PromptAssembler("gpt-4o"))
    verdict = evaluator.grade("task", rubric(), "output", 1)
    assert verdict.passed is False
    assert "Malformed evaluator response" in verdict.critique
    missing = FakeLLMClient(
        [
            '{"passed": true, "score": 1.0, "per_criterion": {}, "critique": "bad", "root_causes": "r", "suggested_fix": "f"}'
        ]
    )
    verdict = Evaluator(missing, "gpt-4o-mini", PromptAssembler("gpt-4o")).grade(
        "task", rubric(), "output", 1
    )
    assert verdict.passed is False
    assert verdict.per_criterion == {"complete": False}


def test_evaluator_never_raises_on_client_error():
    class ExplodingClient(FakeLLMClient):
        def create(self, **kwargs):
            del kwargs
            raise RuntimeError("network down")

    verdict = Evaluator(
        ExplodingClient(), "gpt-4o-mini", PromptAssembler("gpt-4o")
    ).grade("task", rubric(), "output", 1)
    assert verdict.passed is False
    assert verdict.root_causes == "Evaluator call failed: RuntimeError."


def test_role_agent_uses_combined_prompt_budget():
    state = composed_state()
    state.artifact.intermediate_results = ["old " * 200]
    assembler = PromptAssembler("gpt-4o", max_input_tokens_per_call=260)
    client = FakeLLMClient(["ok"])
    agent = RoleAgent(client, "gpt-4o", assembler, ArtifactParser())
    agent.invoke(
        RoleInput(
            task="small task",
            rubric=rubric(),
            role=RoleType.PLANNER,
            composed_state=state,
            turn=1,
            session_id="s",
        )
    )
    messages = client.call_log[0]["messages"]
    total_tokens = sum(
        assembler.count_tokens(message["content"]) for message in messages
    )
    assert total_tokens <= assembler.max_input_tokens_per_call


def test_required_structured_events_are_emitted(state_dir: Path):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("rsc")
    old_handlers = logger.handlers[:]
    old_level = logger.level
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    client = FakeLLMClient(
        [
            "planner",
            "critic",
            "| ITEM | VERDICT | REASON |\n|---|---|---|\n| a | PASS | ok |",
            "reviser",
            "synthesizer",
            '{"passed": true, "score": 1.0, "per_criterion": {"complete": true}, "critique": "", "root_causes": "", "suggested_fix": ""}',
            '{"rules": ["Reusable rule"]}',
        ]
    )
    try:
        assembler = PromptAssembler("gpt-4o")
        orchestrator = LoopOrchestrator(
            client=client,
            model="gpt-4o",
            state_loader=StateLoader(state_dir),
            state_manager=StateManager(state_dir, client=client),
            role_agent=RoleAgent(client, "gpt-4o", assembler, ArtifactParser()),
            evaluator=Evaluator(client, "gpt-4o-mini", assembler),
            prompt_assembler=assembler,
            max_turns=1,
        )
        orchestrator.run("task", rubric(), "default", session_id="session")
    finally:
        logger.handlers = old_handlers
        logger.setLevel(old_level)
        logger.propagate = True
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    events = [record["event"] for record in records]
    assert "session.start" in events
    assert "turn.start" in events
    assert "state.load.complete" in events
    assert "role.start" in events
    assert "role.complete" in events
    assert "artifact.update" in events
    assert "evaluator.start" in events
    assert "evaluator.complete" in events
    assert "verdict.complete" in events
    assert "turn.complete" in events
    assert "memory.distill.start" in events
    assert "memory.distill.complete" in events
    assert "memory.append" in events
    assert "session.complete" in events
    assert all(record["schema_version"] == "rsc.log.v2" for record in records)

    role_start = next(record for record in records if record["event"] == "role.start")
    assert role_start["system_prompt"]["chars"] > 0
    assert len(role_start["system_prompt"]["sha256"]) == 64
    assert role_start["user_message"]["preview"].startswith("TASK:")
    assert role_start["estimated_input_tokens"] > 0
    assert role_start["rubric_labels"] == ["complete"]

    role_complete = next(
        record for record in records if record["event"] == "role.complete"
    )
    assert role_complete["success"] is True
    assert role_complete["output"]["chars"] > 0
    assert "artifact_ids" in role_complete

    evaluator_complete = next(
        record for record in records if record["event"] == "evaluator.complete"
    )
    assert evaluator_complete["success"] is True
    assert evaluator_complete["passed"] is True
    assert evaluator_complete["raw_response"]["chars"] > 0

    turn_complete = next(
        record for record in records if record["event"] == "turn.complete"
    )
    assert turn_complete["planner_output"]["preview"] == "planner"
    assert turn_complete["synthesizer_output"]["preview"] == "synthesizer"
    assert turn_complete["cumulative_tokens_input"] > 0

    session_complete = next(
        record for record in records if record["event"] == "session.complete"
    )
    assert session_complete["success"] is True
    assert session_complete["final_output"]["chars"] > 0


def test_session_error_event_is_emitted():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("rsc")
    old_handlers = logger.handlers[:]
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    class BadLoader:
        def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
            del skill_name, artifact
            raise RuntimeError("load failed")

    try:
        assembler = PromptAssembler("gpt-4o")
        orchestrator = LoopOrchestrator(
            client=FakeLLMClient(),
            model="gpt-4o",
            state_loader=BadLoader(),
            state_manager=StateManager(Path("/tmp/rsc-unused")),
            role_agent=RoleAgent(
                FakeLLMClient(), "gpt-4o", assembler, ArtifactParser()
            ),
            evaluator=Evaluator(FakeLLMClient(), "gpt-4o-mini", assembler),
            prompt_assembler=assembler,
            max_turns=1,
        )
        with pytest.raises(RuntimeError):
            orchestrator.run("task", rubric(), "default", session_id="session")
    finally:
        logger.handlers = old_handlers
        logger.propagate = True
    events = [json.loads(line)["event"] for line in stream.getvalue().splitlines()]
    assert "session.error" in events


class ContentFilterError(Exception):
    pass


class RateLimitError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class ErrorThenSuccessClient(FakeLLMClient):
    def __init__(self, errors: list[Exception], responses: list[str]) -> None:
        super().__init__(responses)
        self.errors = list(errors)

    def create(self, **kwargs):
        if self.errors:
            raise self.errors.pop(0)
        return super().create(**kwargs)


def test_role_agent_handles_content_filter_and_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    filtered = ErrorThenSuccessClient([ContentFilterError("blocked")], [])
    agent = RoleAgent(filtered, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser())
    output = agent.invoke(role_input())
    assert output.error == "blocked"
    retrying = ErrorThenSuccessClient(
        [RateLimitError("rate"), APITimeoutError("timeout")], ["ok"]
    )
    output = RoleAgent(
        retrying, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser()
    ).invoke(role_input())
    assert output.content == "ok"


def test_role_agent_accepts_temperature_overrides():
    client = FakeLLMClient(["ok"])
    agent = RoleAgent(
        client,
        "gpt-4o",
        PromptAssembler("gpt-4o"),
        ArtifactParser(),
        temperature_map={RoleType.PLANNER: 0.9},
    )
    agent.invoke(role_input())
    assert client.call_log[0]["temperature"] == 0.9


def test_role_agent_streams_deltas_and_aggregates_content():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("rsc.role_agent")
    old_handlers = logger.handlers[:]
    old_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    class StreamingClient(FakeLLMClient):
        def create(self, **kwargs):
            self.call_log.append(kwargs)
            if kwargs.get("stream"):
                return iter(
                    [
                        FakeStreamChunk([FakeStreamChoice(FakeDelta("hello "))]),
                        FakeStreamChunk(
                            [FakeStreamChoice(FakeDelta("world"), finish_reason="stop")]
                        ),
                    ]
                )
            return super().create(**kwargs)

    try:
        client = StreamingClient()
        output = RoleAgent(
            client, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser()
        ).invoke(role_input())
    finally:
        logger.handlers = old_handlers
        logger.propagate = old_propagate

    assert output.content == "hello world"
    assert client.call_log[0]["stream"] is True
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert any(record["event"] == "role.delta" for record in records)


def test_role_agent_stream_helpers_cover_dict_and_message_chunks():
    assert (
        RoleAgent._stream_delta_text({"choices": [{"delta": {"content": "a"}}]}) == "a"
    )
    assert (
        RoleAgent._stream_delta_text({"choices": [{"message": {"content": "b"}}]})
        == "b"
    )
    assert RoleAgent._stream_delta_text({"content": "c"}) == "c"
    assert RoleAgent._stream_delta_text({"text": "d"}) == "d"
    assert (
        RoleAgent._stream_reasoning_text(
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [
                                {"type": "reasoning.text", "text": "think a"},
                                {"type": "reasoning.summary", "summary": "think b"},
                            ]
                        }
                    }
                ]
            }
        )
        == "think a\n\nthink b"
    )
    assert (
        RoleAgent._stream_finish_reason({"choices": [{"finish_reason": "stop"}]})
        == "stop"
    )

    class Choice:
        delta = {"content": "e"}
        finish_reason = "done"

    class Chunk:
        choices = [Choice()]

    assert RoleAgent._stream_delta_text(Chunk()) == "e"
    assert RoleAgent._stream_finish_reason(Chunk()) == "done"

    class ReasoningItem:
        text = "think c"

    class ReasoningDelta:
        reasoning_details = [ReasoningItem()]

    class ReasoningChoice:
        delta = ReasoningDelta()

    class ReasoningChunk:
        choices = [ReasoningChoice()]

    assert RoleAgent._stream_reasoning_text(ReasoningChunk()) == "think c"


def test_role_agent_falls_back_when_stream_argument_not_supported():
    class NoStreamClient(FakeLLMClient):
        def create(self, **kwargs):
            if kwargs.get("stream"):
                raise TypeError("stream unsupported")
            return super().create(**kwargs)

    client = NoStreamClient(["fallback ok"])
    output = RoleAgent(
        client, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser()
    ).invoke(role_input())
    assert output.content == "fallback ok"
    assert client.call_log[-1].get("stream") is None


def test_role_agent_raises_unhandled_errors():
    client = ErrorThenSuccessClient([RuntimeError("boom")], [])
    agent = RoleAgent(client, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser())
    with pytest.raises(RuntimeError):
        agent.invoke(role_input())


def test_search_over_inference_invalid_and_failure_paths():
    with pytest.raises(ValueError):
        SearchOverInference(object(), object(), n_candidates=1)

    class FailingAgent:
        @contextmanager
        def temperature_override(self, role: RoleType, temperature: float):
            del role, temperature
            yield

        def invoke(self, planner_input):
            del planner_input
            raise RuntimeError("nope")

    class FailingEvaluator(QueueEvaluator):
        def grade(self, task, rubric, output, turn):
            raise RuntimeError("bad grade")

    search = SearchOverInference(FailingAgent(), FailingEvaluator(), n_candidates=2)
    best = search.generate_best(role_input())
    assert best.error == "candidate failed"


def test_search_over_inference_preserves_temperature_on_candidate_error():
    class OneBadAgent:
        _temperature_map = {RoleType.PLANNER: 0.4}

        @contextmanager
        def temperature_override(self, role: RoleType, temperature: float):
            original = self._temperature_map[role]
            self._temperature_map[role] = temperature
            try:
                yield
            finally:
                self._temperature_map[role] = original

        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, planner_input):
            del planner_input
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("bad")
            return RoleOutput(role=RoleType.PLANNER, content="ok")

    agent = OneBadAgent()
    search = SearchOverInference(
        agent,
        QueueEvaluator(
            [EvalVerdict(passed=True, score=1.0), EvalVerdict(passed=False, score=0.0)]
        ),
        n_candidates=2,
    )
    assert search.generate_best(role_input()).content in {"ok", ""}
    assert agent._temperature_map[RoleType.PLANNER] == 0.4
