from __future__ import annotations

import json
from pathlib import Path

from rsc.artifact_protocol import ArtifactParser
from rsc.contracts import (
    ArtifactRecord,
    ArtifactState,
    ClaudeState,
    ComposedState,
    EvalVerdict,
    LoopStatus,
    MemoryEntry,
    MemoryStage,
    MemoryState,
    RoleInput,
    RoleOutput,
    RoleType,
    SelectedSkill,
    SkillReadiness,
    RubricCriterion,
    SkillState,
)
from rsc.evaluator import Evaluator
from rsc.loop_orchestrator import LoopOrchestrator
from rsc.prompt_assembler import PromptAssembler
from rsc.role_agent import DEFAULT_TEMPERATURE_MAP, RoleAgent
from rsc.search_inference import SearchOverInference
from rsc.search_provider import FunctionSearchProvider
from rsc.state_manager import StateManager

from tests.conftest import FakeLLMClient


def composed_state(rules: list[str] | None = None) -> ComposedState:
    return ComposedState(
        claude=ClaudeState(
            values_and_principles="truth",
            constraints=["keep contract"],
            conduct_rules=["be exact"],
        ),
        memory=MemoryState(history_summary="history", distilled_rules=rules or []),
        skill=SkillState(name="default", source_file="default.md"),
        artifact=ArtifactState(session_id="s"),
    )


def rubric() -> list[RubricCriterion]:
    return [RubricCriterion(label="complete", description="Finish the task")]


class SpyStateLoader:
    def __init__(self, rules: list[str] | None = None) -> None:
        self.calls = 0
        self.rules = rules or []

    def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
        del skill_name
        self.calls += 1
        state = composed_state(self.rules)
        state.artifact = artifact
        return state


class SpyStateManager:
    def __init__(self) -> None:
        self.appended: list[MemoryEntry] = []
        self.distill_count = 0

    def update_artifact_state(
        self, current: ArtifactState, role_output: RoleOutput, turn: int
    ) -> ArtifactState:
        data = current.model_dump()
        data["current_turn"] = turn
        if role_output.role == RoleType.PLANNER:
            data["current_plan"] = role_output.content
        data["artifacts"] = list(current.artifacts) + list(role_output.artifacts)
        return ArtifactState.model_validate(data)

    def append_memory_entry(self, entry: MemoryEntry) -> None:
        self.appended.append(entry)

    def distill_to_memory(self, task: str, loop_turns: list, client) -> list[str]:
        del task, loop_turns, client
        self.distill_count += 1
        return ["distilled"]


class SpyRoleAgent:
    def __init__(self, tokens: int = 1, recursive: bool = False) -> None:
        self.inputs: list[RoleInput] = []
        self.tokens = tokens
        self.recursive = recursive

    def invoke(self, role_input: RoleInput) -> RoleOutput:
        self.inputs.append(role_input)
        artifacts = []
        content = f"{role_input.role.value} output"
        if (
            self.recursive
            and role_input.role == RoleType.REVISER
            and role_input.depth == 0
        ):
            content = '<!--ARTIFACT:START id="a1" recurse="true" -->subtask<!--ARTIFACT:END id="a1" -->'
            artifacts = [
                ArtifactRecord(
                    artifact_id="a1",
                    role=RoleType.REVISER,
                    turn=role_input.turn,
                    content="subtask",
                    can_invoke_model=True,
                )
            ]
        return RoleOutput(
            role=role_input.role,
            content=content,
            artifacts=artifacts,
            tokens_used_input=self.tokens,
            tokens_used_output=self.tokens,
        )


class QueueEvaluator:
    def __init__(self, verdicts: list[EvalVerdict] | None = None) -> None:
        self.verdicts = list(verdicts or [])
        self.calls: list[dict] = []

    def grade(
        self, task: str, rubric: list[RubricCriterion], output: str, turn: int
    ) -> EvalVerdict:
        self.calls.append(
            {"task": task, "rubric": rubric, "output": output, "turn": turn}
        )
        if self.verdicts:
            return self.verdicts.pop(0)
        return EvalVerdict(
            passed=True,
            score=1.0,
            per_criterion={criterion.label: True for criterion in rubric},
        )


class SpySearch:
    def __init__(self) -> None:
        self.calls = 0

    def generate_best(self, planner_input: RoleInput) -> RoleOutput:
        del planner_input
        self.calls += 1
        return RoleOutput(
            role=RoleType.PLANNER,
            content="search planner",
            tokens_used_input=1,
            tokens_used_output=1,
        )


class SpySkillRouter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def route(self, task: str, *, top_k: int = 3):
        self.calls.append({"task": task, "top_k": top_k})

        class Result:
            discovered_count = 2
            selected = [
                SelectedSkill(
                    skill_id="coding.python",
                    name="Python Coding",
                    score=0.9,
                    readiness=SkillReadiness.READY,
                    reason="matched python",
                    content_excerpt="Use pytest.",
                )
            ]

        return Result()


def make_orchestrator(
    role_agent: SpyRoleAgent,
    evaluator: QueueEvaluator,
    state_loader: SpyStateLoader | None = None,
    state_manager: SpyStateManager | None = None,
    search=None,
    skill_router=None,
    max_turns: int = 1,
    max_depth: int = 3,
    max_tokens: int = 120000,
) -> tuple[LoopOrchestrator, SpyStateLoader, SpyStateManager]:
    loader = state_loader or SpyStateLoader()
    manager = state_manager or SpyStateManager()
    assembler = PromptAssembler("gpt-4o")
    orchestrator = LoopOrchestrator(
        client=FakeLLMClient(),
        model="gpt-4o",
        state_loader=loader,
        state_manager=manager,
        role_agent=role_agent,
        evaluator=evaluator,
        prompt_assembler=assembler,
        search_over_inference=search,
        skill_router=skill_router,
        skill_top_k=2,
        max_turns=max_turns,
        max_depth=max_depth,
        max_total_tokens_per_session=max_tokens,
    )
    return orchestrator, loader, manager


def failed(score: float = 0.2, critique: str = "needs work") -> EvalVerdict:
    return EvalVerdict(
        passed=False,
        score=score,
        per_criterion={"complete": False},
        critique=critique,
        root_causes="missing detail",
        suggested_fix="add detail",
    )


def test_evaluator_independent_context():
    client = FakeLLMClient(
        [
            '{"passed": true, "score": 1.0, "per_criterion": {"complete": true}, "critique": "", "root_causes": "", "suggested_fix": ""}'
        ]
    )
    evaluator = Evaluator(client, "gpt-4o-mini", PromptAssembler("gpt-4o"))
    verdict = evaluator.grade("task", rubric(), "output", 1)
    assert verdict.passed is True
    assert len(client.call_log[0]["messages"]) == 2
    assert [message["role"] for message in client.call_log[0]["messages"]] == [
        "system",
        "user",
    ]


def test_role_agent_uses_fresh_context_per_role():
    client = FakeLLMClient(["planner", "critic"])
    agent = RoleAgent(client, "gpt-4o", PromptAssembler("gpt-4o"), ArtifactParser())
    state = composed_state()
    agent.invoke(
        RoleInput(
            task="task",
            rubric=rubric(),
            role=RoleType.PLANNER,
            composed_state=state,
            turn=1,
            session_id="s",
        )
    )
    agent.invoke(
        RoleInput(
            task="task",
            rubric=rubric(),
            role=RoleType.CRITIC,
            prior_output="planner",
            composed_state=state,
            turn=1,
            session_id="s",
        )
    )
    assert all(len(call["messages"]) == 2 for call in client.call_log)
    assert all(
        call["messages"][0]["role"] == "system"
        and call["messages"][1]["role"] == "user"
        for call in client.call_log
    )


def test_verifier_receives_planner_not_critic():
    role_agent = SpyRoleAgent()
    orchestrator, _, _ = make_orchestrator(role_agent, QueueEvaluator())
    orchestrator.run("task", rubric(), "default")
    verifier_input = next(
        item for item in role_agent.inputs if item.role == RoleType.VERIFIER
    )
    assert verifier_input.prior_output == "planner output"
    assert verifier_input.prior_output != "critic output"


def test_reviser_receives_combined_input():
    role_agent = SpyRoleAgent()
    orchestrator, _, _ = make_orchestrator(role_agent, QueueEvaluator())
    orchestrator.run("task", rubric(), "default")
    reviser_input = next(
        item for item in role_agent.inputs if item.role == RoleType.REVISER
    )
    assert "PLAN:" in reviser_input.prior_output
    assert "CRITIQUE:" in reviser_input.prior_output
    assert "VERIFICATION:" in reviser_input.prior_output


def test_synthesizer_receives_prior_verdict_on_turn_gt_1():
    role_agent = SpyRoleAgent()
    evaluator = QueueEvaluator(
        [
            failed(0.2, "first critique"),
            EvalVerdict(passed=True, score=1.0, per_criterion={"complete": True}),
        ]
    )
    orchestrator, _, _ = make_orchestrator(role_agent, evaluator, max_turns=2)
    orchestrator.run("task", rubric(), "default")
    synthesizer_inputs = [
        item for item in role_agent.inputs if item.role == RoleType.SYNTHESIZER
    ]
    assert (
        "PRIOR EVALUATOR CRITIQUE:\nfirst critique"
        in synthesizer_inputs[1].prior_output
    )


def test_state_loaded_once_per_turn_not_per_role():
    role_agent = SpyRoleAgent()
    evaluator = QueueEvaluator(
        [
            failed(),
            EvalVerdict(passed=True, score=1.0, per_criterion={"complete": True}),
        ]
    )
    orchestrator, loader, _ = make_orchestrator(role_agent, evaluator, max_turns=2)
    result = orchestrator.run("task", rubric(), "default")
    assert result.turns_used == 2
    # Each turn loads state twice: once for memory consultation, once after
    # planner-scoped search for the Planner invocation.
    assert loader.calls == 4


def test_search_context_injected_before_planner_state_load():
    role_agent = SpyRoleAgent()
    seen_artifacts: list[ArtifactState] = []

    class SearchAwareLoader(SpyStateLoader):
        def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
            seen_artifacts.append(artifact)
            return super().load(skill_name, artifact)

    queries: list[tuple[str, int]] = []
    provider = FunctionSearchProvider(
        lambda query, max_results: queries.append((query, max_results))
        or "## Web Context\nFresh markdown facts.",
        name="test-search",
    )
    loader = SearchAwareLoader()
    assembler = PromptAssembler("gpt-4o")
    orchestrator = LoopOrchestrator(
        client=FakeLLMClient(),
        model="gpt-4o",
        state_loader=loader,
        state_manager=SpyStateManager(),
        role_agent=role_agent,
        evaluator=QueueEvaluator(),
        prompt_assembler=assembler,
        search_provider=provider,
        search_max_results=7,
        max_turns=1,
    )
    orchestrator.run("what changed today?", rubric(), "default")
    assert queries[0] == ("what changed today?", 7)
    assert len(queries) >= 1
    # First load is for memory consultation (no search results).
    # Second load is after planner search (has search results).
    assert len(seen_artifacts) >= 2
    planner_load = seen_artifacts[1]
    assert (
        planner_load.search_results[0].content
        == "## Web Context\nFresh markdown facts."
    )
    planner_input = next(
        item for item in role_agent.inputs if item.role == RoleType.PLANNER
    )
    system = assembler.build_role_system_prompt(planner_input)
    assert "## SEARCH RESULTS" in system
    assert "Fresh markdown facts." in system


def test_search_queries_use_user_question_and_chunk_context():
    orchestrator, _, _ = make_orchestrator(SpyRoleAgent(), QueueEvaluator())
    orchestrator.search_query_count = 3
    task = (
        "Mode: research\n\n"
        "# Original User Request\nvalidate that the text is intellectually honest\n\n"
        "# Document Section 2 of 6: Gods Aliens.md\n"
        "Chunk ID: gods-0002\nWords: 2600\n\n"
        "Ancient astronauts evidence Sumerian Anunnaki Zecharia Sitchin claims archeology chronology honesty"
    )
    queries = orchestrator._search_queries_for_task(task)
    assert len(queries) == 3
    assert queries[0] == "validate that the text is intellectually honest"
    assert "Gods Aliens.md" in queries[1]
    assert all(len(query) <= 320 for query in queries)
    assert all("Chunk ID" not in query for query in queries)


def test_search_queries_for_plain_question_uses_llm_diversification():
    """A plain user question with no document context should still produce multiple queries via the LLM."""
    client = FakeLLMClient(
        responses=[
            "evidence supporting intellectual honesty in academic writing\n"
            "critiques of intellectual dishonesty in research\n"
            "recent standards for intellectual honesty 2024"
        ]
    )
    orchestrator = LoopOrchestrator(
        client=client,
        model="gpt-4o",
        state_loader=SpyStateLoader(),
        state_manager=SpyStateManager(),
        role_agent=SpyRoleAgent(),
        evaluator=QueueEvaluator(),
        prompt_assembler=PromptAssembler("gpt-4o"),
        search_query_count=3,
        max_turns=1,
    )
    task = "# Original User Request\nIs intellectual honesty important in science?\n"
    queries = orchestrator._search_queries_for_task(task)
    assert len(queries) == 3
    assert "is intellectual honesty important in science" in queries[0].lower()
    assert all(len(query) <= 320 for query in queries)
    # The LLM was called to generate diverse queries.
    assert len(client.call_log) == 1
    assert client.call_log[0]["model"] == "gpt-4o"


def test_search_queries_llm_failure_falls_back_to_heuristics():
    """If the LLM call fails, the orchestrator should still return at least the base question."""

    class BrokenClient:
        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            raise RuntimeError("LLM unavailable")

    orchestrator = LoopOrchestrator(
        client=BrokenClient(),
        model="gpt-4o",
        state_loader=SpyStateLoader(),
        state_manager=SpyStateManager(),
        role_agent=SpyRoleAgent(),
        evaluator=QueueEvaluator(),
        prompt_assembler=PromptAssembler("gpt-4o"),
        search_query_count=3,
        max_turns=1,
    )
    task = "# Original User Request\nWhat are the risks of AI alignment?\n"
    queries = orchestrator._search_queries_for_task(task)
    assert len(queries) >= 1
    assert "what are the risks of ai alignment" in queries[0].lower()


def test_skill_router_selects_primary_skill_before_planner_state_load():
    role_agent = SpyRoleAgent()
    skill_router = SpySkillRouter()
    seen_skill_names: list[str] = []

    class SkillAwareLoader(SpyStateLoader):
        def load(self, skill_name: str, artifact: ArtifactState) -> ComposedState:
            seen_skill_names.append(skill_name)
            state = super().load(skill_name, artifact)
            state.artifact = artifact
            return state

    orchestrator, _, _ = make_orchestrator(
        role_agent,
        QueueEvaluator(),
        state_loader=SkillAwareLoader(),
        skill_router=skill_router,
    )
    orchestrator.run("fix a python test", rubric(), "default")
    assert skill_router.calls == [{"task": "fix a python test", "top_k": 2}]
    # Two loads per turn: one for consultation, one for planner
    assert seen_skill_names == ["coding.python", "coding.python"]
    planner_input = next(
        item for item in role_agent.inputs if item.role == RoleType.PLANNER
    )
    assert (
        planner_input.composed_state.artifact.selected_skills[0].skill_id
        == "coding.python"
    )


def test_recursive_artifacts_processed_after_reviser_before_synthesizer():
    role_agent = SpyRoleAgent(recursive=True)
    orchestrator, _, _ = make_orchestrator(role_agent, QueueEvaluator(), max_depth=1)
    result = orchestrator.run("task", rubric(), "default")
    assert result.turns[0].recursive_results == {"a1": "synthesizer output"}
    synthesizer_input = [
        item
        for item in role_agent.inputs
        if item.role == RoleType.SYNTHESIZER and item.depth == 0
    ][0]
    assert "## a1\nsynthesizer output" in synthesizer_input.prior_output


def test_max_depth_guard_ignores_recursive_artifacts():
    role_agent = SpyRoleAgent(recursive=True)
    orchestrator, _, _ = make_orchestrator(role_agent, QueueEvaluator(), max_depth=0)
    result = orchestrator.run("task", rubric(), "default")
    assert result.turns[0].recursive_results == {}


def test_score_stagnation_triggers_diversity_injection():
    role_agent = SpyRoleAgent()
    evaluator = QueueEvaluator(
        [
            failed(0.20),
            failed(0.21),
            EvalVerdict(passed=True, score=1.0, per_criterion={"complete": True}),
        ]
    )
    orchestrator, _, _ = make_orchestrator(role_agent, evaluator, max_turns=3)
    orchestrator.run("task", rubric(), "default")
    third_planner = [
        item for item in role_agent.inputs if item.role == RoleType.PLANNER
    ][2]
    assert third_planner.inject_diversity is True


def test_verifier_zero_score_triggers_search_over_inference():
    class ZeroPromptAssembler(PromptAssembler):
        def verifier_output_score(self, verifier_content: str) -> float:
            del verifier_content
            return 0.0

    role_agent = SpyRoleAgent()
    search = SpySearch()
    assembler = ZeroPromptAssembler("gpt-4o")
    orchestrator = LoopOrchestrator(
        client=FakeLLMClient(),
        model="gpt-4o",
        state_loader=SpyStateLoader(),
        state_manager=SpyStateManager(),
        role_agent=role_agent,
        evaluator=QueueEvaluator(),
        prompt_assembler=assembler,
        search_over_inference=search,
        max_turns=1,
    )
    orchestrator.run("task", rubric(), "default")
    assert search.calls == 1


def test_low_prior_score_uses_search_over_inference_on_later_turn():
    role_agent = SpyRoleAgent()
    search = SpySearch()
    evaluator = QueueEvaluator(
        [
            failed(0.2),
            failed(0.2),
            EvalVerdict(passed=True, score=1.0, per_criterion={"complete": True}),
        ]
    )
    orchestrator, _, _ = make_orchestrator(
        role_agent, evaluator, search=search, max_turns=3
    )
    orchestrator.run("task", rubric(), "default")
    assert search.calls >= 1


def test_memory_append_only_except_compression_replacement(state_dir: Path):
    manager = StateManager(state_dir, max_ledger_entries=10)
    manager.append_memory_entry(
        MemoryEntry(task_hint="t", stage=MemoryStage.FAIL, content="f1", session_id="s")
    )
    manager.append_memory_entry(
        MemoryEntry(
            task_hint="t", stage=MemoryStage.INVESTIGATE, content="i1", session_id="s"
        )
    )
    ledger = json.loads((state_dir / "memory_ledger.json").read_text())
    assert [entry["content"] for entry in ledger["entries"]] == ["f1", "i1"]


def test_distill_to_memory_runs_once_post_loop():
    role_agent = SpyRoleAgent()
    evaluator = QueueEvaluator([failed(), failed()])
    orchestrator, _, manager = make_orchestrator(role_agent, evaluator, max_turns=2)
    result = orchestrator.run("task", rubric(), "default")
    assert result.status == LoopStatus.EXHAUSTED
    assert manager.distill_count == 1


def test_consult_entries_written_when_rules_injected():
    role_agent = SpyRoleAgent()
    loader = SpyStateLoader(rules=["reuse this"])
    manager = SpyStateManager()
    orchestrator, _, _ = make_orchestrator(
        role_agent, QueueEvaluator(), state_loader=loader, state_manager=manager
    )
    orchestrator.run("task", rubric(), "default")
    consults = [
        entry for entry in manager.appended if entry.stage == MemoryStage.CONSULT
    ]
    assert len(consults) == 1
    assert consults[0].content == "reuse this"


def test_prompt_budget_truncation_order():
    state = composed_state([f"rule {index}" for index in range(20)])
    state.artifact.current_plan = "latest plan must remain"
    state.artifact.intermediate_results = [f"old-result-{index}" for index in range(60)]
    state.artifact.decisions = [f"decision-{index}" for index in range(20)]
    state.memory.history_summary = "history " * 200
    state.skill.domain_knowledge = "domain " * 200
    assembler = PromptAssembler("gpt-4o", max_input_tokens_per_call=500)
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
    assert "old-result-0" not in prompt
    # PLANNER does not include CURRENT PLAN (it creates the plan).
    # Instead verify that CONSTRAINTS (always-included) survives truncation.
    assert "- keep contract" in prompt


def test_token_budget_exhaustion_returns_exhausted_status():
    role_agent = SpyRoleAgent(tokens=100)
    evaluator = QueueEvaluator([failed(0.25, "over budget and incomplete")])
    orchestrator, _, _ = make_orchestrator(role_agent, evaluator, max_tokens=10)
    result = orchestrator.run("task", rubric(), "default")
    assert result.status == LoopStatus.EXHAUSTED
    assert result.final_score == 0.25
    assert evaluator.calls


def test_passing_output_wins_even_when_budget_exhausted():
    role_agent = SpyRoleAgent(tokens=100)
    evaluator = QueueEvaluator(
        [EvalVerdict(passed=True, score=1.0, per_criterion={"complete": True})]
    )
    orchestrator, _, _ = make_orchestrator(role_agent, evaluator, max_tokens=10)
    result = orchestrator.run("task", rubric(), "default")
    assert result.status == LoopStatus.PASSED
    assert result.final_score == 1.0


def test_role_temperatures_match_defaults():
    assert DEFAULT_TEMPERATURE_MAP[RoleType.PLANNER] == 0.4
    assert DEFAULT_TEMPERATURE_MAP[RoleType.CRITIC] == 0.2
    assert DEFAULT_TEMPERATURE_MAP[RoleType.VERIFIER] == 0.0
    assert DEFAULT_TEMPERATURE_MAP[RoleType.REVISER] == 0.3
    assert DEFAULT_TEMPERATURE_MAP[RoleType.SYNTHESIZER] == 0.2


def test_golden_planner_message_fixture():
    fixture = json.loads(
        Path("tests/fixtures/golden/prompt_assembler_planner_basic.json").read_text(
            encoding="utf-8"
        )
    )
    assembler = PromptAssembler("gpt-4o")
    state = composed_state()
    role_input = RoleInput(
        task="Do the work",
        rubric=rubric(),
        role=RoleType.PLANNER,
        composed_state=state,
        turn=1,
        session_id="s",
    )
    system = assembler.build_role_system_prompt(role_input)
    user = assembler.build_role_user_message(role_input)
    assert all(text in system for text in fixture["expected"]["system_prompt_contains"])
    assert user.strip() == fixture["expected"]["user_message_exact"]


def test_search_over_inference_selects_best_shortest_candidate():
    client = FakeLLMClient(
        [
            "longer candidate",
            "short",
            '{"passed": true, "score": 1.0, "per_criterion": {"complete": true}, "critique": "", "root_causes": "", "suggested_fix": ""}',
            '{"passed": true, "score": 1.0, "per_criterion": {"complete": true}, "critique": "", "root_causes": "", "suggested_fix": ""}',
        ]
    )
    assembler = PromptAssembler("gpt-4o")
    agent = RoleAgent(client, "gpt-4o", assembler, ArtifactParser())
    evaluator = Evaluator(client, "gpt-4o-mini", assembler)
    search = SearchOverInference(agent, evaluator, n_candidates=2)
    best = search.generate_best(
        RoleInput(
            task="task",
            rubric=rubric(),
            role=RoleType.PLANNER,
            composed_state=composed_state(),
            turn=1,
            session_id="s",
        )
    )
    assert best.content == "short"


def test_state_manager_distill_deduplicates_existing_rule(state_dir: Path):
    client = FakeLLMClient(['{"rules": ["Keep it short", "New rule"]}'])
    manager = StateManager(state_dir, client=client)
    manager.append_memory_entry(
        MemoryEntry(
            task_hint="t",
            stage=MemoryStage.DISTILL,
            content="Keep it short",
            session_id="s",
        )
    )
    added = manager.distill_to_memory("task", [], client)
    assert added == ["New rule"]
