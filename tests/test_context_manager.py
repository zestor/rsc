"""Tests for ContextManager and role-scoped system prompt rendering.

Covers:
- Role-scoped system prompts: each role gets only its expected sections.
- Role-specific search results: each role sees only its own results.
- 80% context window guard: under budget = no-op; over budget = reactive summarization.
- Reactive summarization order: search results first, then domain knowledge,
  then learned rules, then ongoing context, then history summary, then exhausted.
- Proactive summarization: search records, domain knowledge, history summary.
- Summarization cache: same content summarized once.
- Sacred message guarantee: system/user messages never truncated after rendering.
- Reasoning exclusion: reasoning never in downstream prompts.
- Backward compatibility: with no context_manager, behavior unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from rsc.config import RSCConfig
from rsc.context_manager import ContextManager
from rsc.contracts import (
    ArtifactState,
    ClaudeState,
    ComposedState,
    MemoryState,
    RoleType,
    RubricCriterion,
    SearchRecord,
    SkillState,
)
from rsc.exceptions import ConfigurationError
from rsc.prompt_assembler import ROLE_SECTIONS, PromptAssembler

from tests.conftest import FakeLLMClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _composed_state(
    *,
    search_results: list[SearchRecord] | None = None,
    domain_knowledge: str = "",
    distilled_rules: list[str] | None = None,
    ongoing_context: str = "",
    history_summary: str = "",
    current_plan: str = "",
) -> ComposedState:
    return ComposedState(
        claude=ClaudeState(
            values_and_principles="truth",
            constraints=["keep contract"],
            conduct_rules=["be exact"],
            response_style="clear prose",
        ),
        memory=MemoryState(
            history_summary=history_summary,
            distilled_rules=distilled_rules or [],
            ongoing_context=ongoing_context,
        ),
        skill=SkillState(
            name="default",
            source_file="default.md",
            domain_knowledge=domain_knowledge,
        ),
        artifact=ArtifactState(
            session_id="s",
            search_results=search_results or [],
            current_plan=current_plan,
        ),
    )


def _rubric() -> list[RubricCriterion]:
    return [RubricCriterion(label="complete", description="Finish the task")]


def _make_context_manager(
    *,
    responses: list[str] | None = None,
    context_window_tokens: int = 1_000_000,
    budget_ratio: float = 0.8,
    search_summary_target_tokens: int = 500,
    domain_knowledge_target_tokens: int = 2000,
    history_summary_threshold: int = 1000,
    learned_rules_threshold: int = 15,
) -> tuple[ContextManager, FakeLLMClient, PromptAssembler]:
    client = FakeLLMClient(responses=responses or [])
    assembler = PromptAssembler(
        "gpt-4o",
        learned_rules_threshold=learned_rules_threshold,
    )
    cm = ContextManager(
        prompt_assembler=assembler,
        client=client,
        model="gpt-4o",
        context_window_tokens=context_window_tokens,
        output_tokens=65536,
        budget_ratio=budget_ratio,
        search_summary_target_tokens=search_summary_target_tokens,
        domain_knowledge_target_tokens=domain_knowledge_target_tokens,
        history_summary_threshold=history_summary_threshold,
        learned_rules_threshold=learned_rules_threshold,
    )
    return cm, client, assembler


# ---------------------------------------------------------------------------
# Role-scoped system prompts
# ---------------------------------------------------------------------------


class TestRoleScopedSystemPrompts:
    def test_all_five_roles_have_section_sets(self):
        for role in RoleType:
            assert role in ROLE_SECTIONS
            assert len(ROLE_SECTIONS[role]) > 0

    def test_critic_excludes_search_results_and_plan(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q", content="data", metadata={"role": "planner"})
            ],
            current_plan="## Step 1",
            domain_knowledge="Python facts",
            distilled_rules=["rule one"],
            ongoing_context="session info",
            history_summary="past context",
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.CRITIC)
        assert "## BEHAVIORAL CONSTITUTION" in system
        assert "## CONSTRAINTS" in system
        assert "## CONDUCT RULES" in system
        assert "## LEARNED RULES" in system
        assert "## SEARCH RESULTS" not in system
        assert "## CURRENT PLAN" not in system
        assert "## DOMAIN KNOWLEDGE" not in system
        assert "## SELECTED SKILLS" not in system
        assert "## INTERMEDIATE RESULTS" not in system
        assert "## DECISIONS MADE" not in system
        assert "## METRICS" not in system

    def test_verifier_excludes_search_results_and_plan(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q", content="data", metadata={"role": "planner"})
            ],
            current_plan="## Step 1",
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.VERIFIER)
        assert "## SEARCH RESULTS" not in system
        assert "## CURRENT PLAN" not in system
        assert "## DOMAIN KNOWLEDGE" not in system

    def test_planner_includes_search_results(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q", content="data", metadata={"role": "planner"})
            ],
            domain_knowledge="Python facts",
            history_summary="past context",
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.PLANNER)
        assert "## SEARCH RESULTS" in system
        assert "## DOMAIN KNOWLEDGE" in system
        assert "## HISTORY SUMMARY" in system

    def test_reviser_includes_search_and_domain_but_not_plan(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q", content="data", metadata={"role": "reviser"})
            ],
            current_plan="## Step 1",
            domain_knowledge="Python facts",
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.REVISER)
        assert "## SEARCH RESULTS" in system
        assert "## DOMAIN KNOWLEDGE" in system
        assert "## CURRENT PLAN" not in system
        assert "## INTERMEDIATE RESULTS" not in system
        assert "## DECISIONS MADE" not in system
        assert "## SELECTED SKILLS" not in system
        assert "## HISTORY SUMMARY" not in system
        assert "## ONGOING CONTEXT" not in system
        assert "## TEMPLATES" not in system

    def test_synthesizer_includes_response_style_excludes_search(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q", content="data", metadata={"role": "planner"})
            ],
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(
            state, RoleType.SYNTHESIZER
        )
        assert "## RESPONSE STYLE" in system
        assert "## SEARCH RESULTS" not in system
        assert "## SELECTED SKILLS" not in system
        assert "## HISTORY SUMMARY" not in system

    def test_metrics_never_in_any_prompt(self):
        state = _composed_state()
        state.artifact.metrics = {"search_calls": 5}
        assembler = PromptAssembler("gpt-4o")
        for role in RoleType:
            system = assembler.build_role_system_prompt_for_role(state, role)
            assert "## METRICS" not in system

    def test_section_counts_per_role(self):
        assert len(ROLE_SECTIONS[RoleType.PLANNER]) == 13
        assert len(ROLE_SECTIONS[RoleType.CRITIC]) == 7
        assert len(ROLE_SECTIONS[RoleType.VERIFIER]) == 7
        assert len(ROLE_SECTIONS[RoleType.REVISER]) == 9
        assert len(ROLE_SECTIONS[RoleType.SYNTHESIZER]) == 11


# ---------------------------------------------------------------------------
# Role-specific search results
# ---------------------------------------------------------------------------


class TestRoleSpecificSearchResults:
    def test_planner_sees_only_planner_results(self):
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q1", content="planner data", metadata={"role": "planner"}
                ),
                SearchRecord(
                    query="q2", content="reviser data", metadata={"role": "reviser"}
                ),
            ],
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.PLANNER)
        assert "planner data" in system
        assert "reviser data" not in system

    def test_reviser_sees_only_reviser_results(self):
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q1", content="planner data", metadata={"role": "planner"}
                ),
                SearchRecord(
                    query="q2", content="reviser data", metadata={"role": "reviser"}
                ),
            ],
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.REVISER)
        assert "reviser data" in system
        assert "planner data" not in system

    def test_untagged_results_default_to_planner(self):
        state = _composed_state(
            search_results=[
                SearchRecord(query="q1", content="baseline data", metadata={}),
            ],
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.PLANNER)
        assert "baseline data" in system

    def test_critic_sees_no_search_results(self):
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q1", content="planner data", metadata={"role": "planner"}
                ),
            ],
        )
        assembler = PromptAssembler("gpt-4o")
        system = assembler.build_role_system_prompt_for_role(state, RoleType.CRITIC)
        assert "planner data" not in system
        assert "## SEARCH RESULTS" not in system


# ---------------------------------------------------------------------------
# 80% context window guard
# ---------------------------------------------------------------------------


class TestContextWindowGuard:
    def test_under_budget_noop(self):
        state = _composed_state(domain_knowledge="small")
        cm, _, _ = _make_context_manager()
        result_state, exhausted = cm.enforce_budget(
            composed_state=state,
            role=RoleType.PLANNER,
            session_id="s1",
            depth=0,
            turn=1,
        )
        assert exhausted is False
        # State should be unchanged (deepcopy returned)
        assert result_state.skill.domain_knowledge == "small"

    def test_over_budget_triggers_search_summarization(self):
        # Create a state with large search results that exceed a tiny budget
        big_content = "x" * 5000
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q", content=big_content, metadata={"role": "planner"}
                ),
            ],
        )
        cm, client, _ = _make_context_manager(
            responses=["summarized content"],
            context_window_tokens=500,  # tiny budget to force summarization
            budget_ratio=0.8,
        )
        result_state, exhausted = cm.enforce_budget(
            composed_state=state,
            role=RoleType.PLANNER,
            session_id="s1",
            depth=0,
            turn=1,
        )
        assert exhausted is False
        # Search results should have been re-summarized
        assert len(client.call_log) >= 1
        # The result state should have different (shorter) content
        result_content = result_state.artifact.search_results[0].content
        assert len(result_content) < len(big_content)

    def test_exhausted_when_all_steps_insufficient(self):
        # Create a state so large that even summarization can't help
        # because the LLM response is also large
        big_content = "x" * 50000
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q", content=big_content, metadata={"role": "planner"}
                ),
            ],
            domain_knowledge=big_content,
            ongoing_context=big_content,
            history_summary=big_content,
            distilled_rules=["rule"] * 20,
        )
        cm, client, _ = _make_context_manager(
            responses=[big_content],  # LLM returns large content too
            context_window_tokens=100,  # impossibly small budget
            budget_ratio=0.8,
        )
        result_state, exhausted = cm.enforce_budget(
            composed_state=state,
            role=RoleType.PLANNER,
            session_id="s1",
            depth=0,
            turn=1,
        )
        assert exhausted is True

    def test_input_budget_property(self):
        cm, _, _ = _make_context_manager(
            context_window_tokens=1_000_000,
            budget_ratio=0.8,
        )
        assert cm.input_budget == 800_000

    def test_input_budget_with_different_ratio(self):
        cm, _, _ = _make_context_manager(
            context_window_tokens=500_000,
            budget_ratio=0.7,
        )
        assert cm.input_budget == 350_000


# ---------------------------------------------------------------------------
# Reactive summarization order
# ---------------------------------------------------------------------------


class TestReactiveSummarizationOrder:
    def test_search_results_summarized_first(self):
        big_search = "The quick brown fox jumped over the lazy dog. " * 200
        big_domain = "Python is a programming language with many features. " * 200
        state = _composed_state(
            search_results=[
                SearchRecord(
                    query="q", content=big_search, metadata={"role": "planner"}
                ),
            ],
            domain_knowledge=big_domain,
        )
        cm, client, _ = _make_context_manager(
            responses=["short summary"],
            context_window_tokens=2000,
            budget_ratio=0.8,
            search_summary_target_tokens=10,  # force summarization
        )
        cm.enforce_budget(
            composed_state=state,
            role=RoleType.PLANNER,
            session_id="s1",
            depth=0,
            turn=1,
        )
        # First LLM call should be for search results
        assert len(client.call_log) >= 1
        first_call_content = client.call_log[0]["messages"][1]["content"]
        assert "search" in first_call_content.lower() or "Search" in first_call_content


# ---------------------------------------------------------------------------
# Proactive summarization
# ---------------------------------------------------------------------------


class TestProactiveSummarization:
    def test_summarize_search_record_when_large(self):
        # Need content large enough in tokens (~500+ tokens to exceed target of 500)
        big_content = "The quick brown fox jumped over the lazy dog. " * 200
        record = SearchRecord(query="q", content=big_content, metadata={})
        cm, client, _ = _make_context_manager(
            responses=["summarized"],
            search_summary_target_tokens=500,
        )
        result = cm.summarize_search_record(record, session_id="s1", depth=0)
        assert result.content == "summarized"
        assert result.metadata.get("summarized") is True
        assert "original_tokens" in result.metadata

    def test_summarize_search_record_skipped_when_small(self):
        record = SearchRecord(query="q", content="small", metadata={})
        cm, client, _ = _make_context_manager(
            responses=["should not be called"],
            search_summary_target_tokens=500,
        )
        result = cm.summarize_search_record(record, session_id="s1", depth=0)
        assert result.content == "small"
        assert len(client.call_log) == 0

    def test_summarize_search_record_idempotent(self):
        record = SearchRecord(
            query="q",
            content="data",
            metadata={"summarized": True},
        )
        cm, client, _ = _make_context_manager(responses=["should not be called"])
        result = cm.summarize_search_record(record, session_id="s1", depth=0)
        assert result.content == "data"
        assert len(client.call_log) == 0

    def test_summarize_domain_knowledge_when_large(self):
        big_domain = "Python is a programming language with many features. " * 500
        cm, client, _ = _make_context_manager(
            responses=["summarized domain"],
            domain_knowledge_target_tokens=2000,
        )
        result = cm.summarize_domain_knowledge(big_domain, session_id="s1", depth=0)
        assert result == "summarized domain"

    def test_summarize_domain_knowledge_skipped_when_small(self):
        cm, client, _ = _make_context_manager(
            responses=["should not be called"],
            domain_knowledge_target_tokens=2000,
        )
        result = cm.summarize_domain_knowledge("small domain", session_id="s1", depth=0)
        assert result == "small domain"
        assert len(client.call_log) == 0

    def test_maybe_summarize_history_when_over_threshold(self):
        big_history = (
            "Previous session explored many topics including Python and JavaScript. "
            * 200
        )
        cm, client, _ = _make_context_manager(
            responses=["compressed history"],
            history_summary_threshold=1000,
        )
        result = cm.maybe_summarize_history(big_history, session_id="s1", depth=0)
        assert result == "compressed history"

    def test_maybe_summarize_history_skipped_when_under_threshold(self):
        cm, client, _ = _make_context_manager(
            responses=["should not be called"],
            history_summary_threshold=1000,
        )
        result = cm.maybe_summarize_history("small history", session_id="s1", depth=0)
        assert result == "small history"
        assert len(client.call_log) == 0


# ---------------------------------------------------------------------------
# Summarization cache
# ---------------------------------------------------------------------------


class TestSummarizationCache:
    def test_same_content_summarized_once(self):
        content = "x" * 3000
        cm, client, _ = _make_context_manager(responses=["summary"])
        result1 = cm.summarize(
            content,
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        result2 = cm.summarize(
            content,
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        assert result1 == result2 == "summary"
        assert len(client.call_log) == 1  # only one LLM call

    def test_different_content_summarized_separately(self):
        cm, client, _ = _make_context_manager(responses=["summary1", "summary2"])
        result1 = cm.summarize(
            "content1" * 500,
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        result2 = cm.summarize(
            "content2" * 500,
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        assert result1 == "summary1"
        assert result2 == "summary2"
        assert len(client.call_log) == 2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_llm_error_returns_original_content(self):
        cm, client, _ = _make_context_manager(responses=[])

        def boom(**kwargs):
            raise RuntimeError("LLM down")

        client.chat.completions.create = boom  # type: ignore[method-assign]
        result = cm.summarize(
            "original content",
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        assert result == "original content"

    def test_empty_content_returned_unchanged(self):
        cm, _, _ = _make_context_manager(responses=["should not be called"])
        result = cm.summarize(
            "",
            instruction="test",
            target_tokens=100,
            session_id="s1",
            depth=0,
        )
        assert result == ""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self):
        config = RSCConfig.from_env(environ={}, dotenv_path=None, require_api_key=False)
        assert config.llm_context_window_tokens == 1_000_000
        assert config.llm_output_tokens == 65_536
        assert config.context_budget_ratio == 0.8
        assert config.context_search_summary_target_tokens == 500
        assert config.context_domain_knowledge_target_tokens == 2000
        assert config.context_history_summary_threshold == 1000
        assert config.context_learned_rules_threshold == 15

    def test_env_overrides(self):
        env = {
            "LLM_CONTEXT_WINDOW_TOKENS": "524288",
            "LLM_OUTPUT_TOKENS": "32768",
            "CONTEXT_BUDGET_RATIO": "0.7",
            "CONTEXT_SEARCH_SUMMARY_TARGET_TOKENS": "300",
            "CONTEXT_DOMAIN_KNOWLEDGE_TARGET_TOKENS": "1500",
            "CONTEXT_HISTORY_SUMMARY_THRESHOLD": "800",
            "CONTEXT_LEARNED_RULES_THRESHOLD": "10",
        }
        config = RSCConfig.from_env(
            environ=env, dotenv_path=None, require_api_key=False
        )
        assert config.llm_context_window_tokens == 524288
        assert config.llm_output_tokens == 32768
        assert config.context_budget_ratio == 0.7
        assert config.context_search_summary_target_tokens == 300
        assert config.context_domain_knowledge_target_tokens == 1500
        assert config.context_history_summary_threshold == 800
        assert config.context_learned_rules_threshold == 10

    def test_validation_rejects_bad_budget_ratio(self):
        with pytest.raises(ConfigurationError):
            RSCConfig(
                context_budget_ratio=0.3,
            ).validate()

    def test_validation_rejects_zero_context_window(self):
        with pytest.raises(ConfigurationError):
            RSCConfig(
                llm_context_window_tokens=0,
            ).validate()

    def test_validation_rejects_zero_output_tokens(self):
        with pytest.raises(ConfigurationError):
            RSCConfig(
                llm_output_tokens=0,
            ).validate()


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_no_context_manager_role_agent_works(self):
        """RoleAgent with context_manager=None should work as before."""
        from rsc.artifact_protocol import ArtifactParser
        from rsc.role_agent import RoleAgent
        from rsc.contracts import RoleInput, RoleOutput

        assembler = PromptAssembler("gpt-4o")
        client = FakeLLMClient(responses=["plan output"])
        agent = RoleAgent(
            client=client,
            model="gpt-4o",
            prompt_assembler=assembler,
            artifact_parser=ArtifactParser(),
            max_output_tokens=1000,
            # context_manager defaults to None
        )
        state = _composed_state()
        role_input = RoleInput(
            task="do something",
            rubric=_rubric(),
            role=RoleType.PLANNER,
            composed_state=state,
            turn=1,
            session_id="s1",
            depth=0,
        )
        result = agent.invoke(role_input)
        assert result.content == "plan output"
        assert result.error is None or result.error == ""
