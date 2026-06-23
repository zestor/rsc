from __future__ import annotations

import re
from collections import Counter
from time import perf_counter
from uuid import uuid4

from .contracts import (
    ArtifactState,
    EvalVerdict,
    LoopResult,
    LoopStatus,
    LoopTurnRecord,
    MemoryEntry,
    MemoryStage,
    RoleInput,
    RoleOutput,
    RoleType,
    RubricCriterion,
    SearchRecord,
)
from .observability import get_logger, log_event, model_dump_summary, text_summary
from .role_search_planner import RoleSearchPlanner, planner_should_search


class LoopOrchestrator:
    def __init__(
        self,
        client,
        model: str,
        state_loader,
        state_manager,
        role_agent,
        evaluator,
        prompt_assembler,
        search_over_inference=None,
        search_provider=None,
        search_max_results: int = 5,
        search_query_count: int = 3,
        skill_router=None,
        skill_top_k: int = 3,
        max_turns: int = 3,
        max_depth: int = 3,
        pass_threshold: float = 1.0,
        max_total_tokens_per_session: int = 120000,
        role_search_planner: RoleSearchPlanner | None = None,
        role_search_max_calls_per_turn: int = 2,
        role_search_max_total_records: int = 50,
        chat_store=None,
        verifier_enabled: bool = True,
        synthesizer_enabled: bool = True,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        self.client = client
        self.model = model
        self.state_loader = state_loader
        self.state_manager = state_manager
        self.role_agent = role_agent
        self.evaluator = evaluator
        self.prompt_assembler = prompt_assembler
        self.search_over_inference = search_over_inference
        self.search_provider = search_provider
        self.search_max_results = search_max_results
        self.search_query_count = search_query_count
        self.skill_router = skill_router
        self.skill_top_k = skill_top_k
        self.max_turns = max_turns
        self.max_depth = max_depth
        self.pass_threshold = pass_threshold
        self.max_total_tokens_per_session = max_total_tokens_per_session
        self.role_search_planner = role_search_planner
        self.role_search_max_calls_per_turn = role_search_max_calls_per_turn
        self.role_search_max_total_records = role_search_max_total_records
        self.chat_store = chat_store
        self.verifier_enabled = verifier_enabled
        self.synthesizer_enabled = synthesizer_enabled
        self._logger = get_logger("loop_orchestrator")

    def run(
        self,
        task: str,
        rubric: list[RubricCriterion],
        skill_name: str = "default",
        session_id: str | None = None,
        parent_session_id: str | None = None,
        depth: int = 0,
    ) -> LoopResult:
        try:
            result = self._run(
                task=task,
                rubric=rubric,
                skill_name=skill_name,
                session_id=session_id,
                parent_session_id=parent_session_id,
                depth=depth,
            )
            # Persist run content for cross-chat retrieval (depth 0 only)
            if depth == 0 and self.chat_store is not None:
                try:
                    self.chat_store.persist_run(result)
                except Exception as exc:
                    log_event(
                        self._logger,
                        "chat_store.persist.error",
                        session_id=result.session_id,
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                        success=False,
                    )
            return result
        except Exception as exc:
            log_event(
                self._logger,
                "session.error",
                session_id=session_id or "",
                depth=depth,
                error=str(exc),
                error_type=exc.__class__.__name__,
                task=text_summary(task),
                skill_name=skill_name,
                rubric_labels=[criterion.label for criterion in rubric],
                success=False,
            )
            raise

    def _run(
        self,
        task: str,
        rubric: list[RubricCriterion],
        skill_name: str = "default",
        session_id: str | None = None,
        parent_session_id: str | None = None,
        depth: int = 0,
    ) -> LoopResult:
        assert depth <= self.max_depth
        session_id = session_id or str(uuid4())
        artifact_state = ArtifactState(session_id=session_id, current_turn=0)
        artifact_state, skill_name = self._route_skill_context(
            artifact_state=artifact_state,
            requested_skill_name=skill_name,
            task=task,
            session_id=session_id,
            depth=depth,
        )
        loop_turns: list[LoopTurnRecord] = []
        prior_verdict_critique: str | None = None
        total_tokens_input = 0
        total_tokens_output = 0
        final_output = ""
        consulted = False
        log_event(
            self._logger,
            "session.start",
            session_id=session_id,
            depth=depth,
            parent_session_id=parent_session_id,
            task=text_summary(task),
            rubric_labels=[criterion.label for criterion in rubric],
            requested_skill_name=skill_name,
            max_turns=self.max_turns,
            max_depth=self.max_depth,
            pass_threshold=self.pass_threshold,
            max_total_tokens_per_session=self.max_total_tokens_per_session,
            search_enabled=self.search_provider is not None,
            skill_router_enabled=self.skill_router is not None,
        )

        for turn in range(1, self.max_turns + 1):
            turn_start = perf_counter()
            role_search_calls_this_turn = 0
            rubric_has_accuracy = any(
                "accuracy" in criterion.label.lower()
                or "accuracy" in criterion.description.lower()
                or "citation" in criterion.label.lower()
                or "citation" in criterion.description.lower()
                for criterion in rubric
            )
            log_event(
                self._logger,
                "turn.start",
                session_id=session_id,
                depth=depth,
                turn=turn,
                prior_verdict_critique=text_summary(prior_verdict_critique),
                prior_turn_count=len(loop_turns),
                artifact_state=model_dump_summary(artifact_state),
                cumulative_tokens_input=total_tokens_input,
                cumulative_tokens_output=total_tokens_output,
            )
            recursive_results: dict[str, str] = {}
            inject_diversity = self._should_inject_diversity(loop_turns)
            composed_state = self.state_loader.load(
                skill_name=skill_name, artifact=artifact_state
            )
            log_event(
                self._logger,
                "state.load.complete",
                session_id=session_id,
                depth=depth,
                turn=turn,
                skill_name=composed_state.skill.name,
                claude_source=composed_state.claude.source_file,
                memory_source=composed_state.memory.source_file,
                skill_source=composed_state.skill.source_file,
                distilled_rule_count=len(composed_state.memory.distilled_rules),
                search_result_count=len(composed_state.artifact.search_results),
                selected_skill_count=len(composed_state.artifact.selected_skills),
                artifact_count=len(composed_state.artifact.artifacts),
                state=model_dump_summary(composed_state),
            )
            if not consulted and composed_state.memory.distilled_rules:
                self.state_manager.append_memory_entry(
                    MemoryEntry(
                        task_hint=task[:80],
                        stage=MemoryStage.CONSULT,
                        content="\n".join(composed_state.memory.distilled_rules),
                        session_id=session_id,
                    )
                )
                consulted = True

            # Planner-scoped search: run right before the Planner so search
            # results are context-aware (incorporates prior turn critique on
            # turn ≥ 2) and appear in strict chronological order.
            planner_search_context = task
            if prior_verdict_critique:
                planner_search_context = (
                    f"{task}\n\nPrior critique:\n{prior_verdict_critique}"
                )
            artifact_state = self._maybe_run_planner_search(
                artifact_state=artifact_state,
                context=planner_search_context,
                session_id=session_id,
                depth=depth,
                turn=turn,
            )
            composed_state = self.state_loader.load(
                skill_name=skill_name, artifact=artifact_state
            )
            planner_input = RoleInput(
                task=task,
                rubric=rubric,
                role=RoleType.PLANNER,
                prior_output=None,
                composed_state=composed_state,
                turn=turn,
                session_id=session_id,
                depth=depth,
                inject_diversity=inject_diversity,
                prior_verdict_critique=prior_verdict_critique,
                original_task=task,
            )
            planner_output = self._invoke_planner(
                planner_input, turn, prior_verdict_critique, loop_turns
            )
            artifact_state = self.state_manager.update_artifact_state(
                artifact_state, planner_output, turn
            )
            total_tokens_input += planner_output.tokens_used_input
            total_tokens_output += planner_output.tokens_used_output

            if role_search_calls_this_turn < self.role_search_max_calls_per_turn:
                before = len(artifact_state.search_results)
                artifact_state = self._maybe_run_role_search(
                    role=RoleType.CRITIC,
                    context=planner_output.content,
                    trigger="after_planner",
                    source_label="planner_output",
                    artifact_state=artifact_state,
                    session_id=session_id,
                    depth=depth,
                    turn=turn,
                    task=task,
                    planner_output=planner_output.content,
                    critic_output=None,
                    verifier_output=None,
                    revised_output=None,
                    prior_verdict_critique=prior_verdict_critique,
                    rubric_has_accuracy=rubric_has_accuracy,
                )
                if len(artifact_state.search_results) > before:
                    role_search_calls_this_turn += 1
                    composed_state = composed_state.model_copy(
                        update={"artifact": artifact_state}
                    )

            critic_output = self.role_agent.invoke(
                self._role_input(
                    task,
                    rubric,
                    RoleType.CRITIC,
                    planner_output.content,
                    composed_state,
                    turn,
                    session_id,
                    depth,
                    inject_diversity,
                    prior_verdict_critique,
                )
            )
            artifact_state = self.state_manager.update_artifact_state(
                artifact_state, critic_output, turn
            )
            total_tokens_input += critic_output.tokens_used_input
            total_tokens_output += critic_output.tokens_used_output

            if role_search_calls_this_turn < self.role_search_max_calls_per_turn:
                before = len(artifact_state.search_results)
                artifact_state = self._maybe_run_role_search(
                    role=RoleType.VERIFIER,
                    context=planner_output.content,
                    trigger="after_critic",
                    source_label="planner_output",
                    artifact_state=artifact_state,
                    session_id=session_id,
                    depth=depth,
                    turn=turn,
                    task=task,
                    planner_output=planner_output.content,
                    critic_output=critic_output.content,
                    verifier_output=None,
                    revised_output=None,
                    prior_verdict_critique=prior_verdict_critique,
                    rubric_has_accuracy=rubric_has_accuracy,
                )
                if len(artifact_state.search_results) > before:
                    role_search_calls_this_turn += 1
                    composed_state = composed_state.model_copy(
                        update={"artifact": artifact_state}
                    )

            # --- Verifier (optional) ---
            if self.verifier_enabled:
                verifier_output = self.role_agent.invoke(
                    self._role_input(
                        task,
                        rubric,
                        RoleType.VERIFIER,
                        planner_output.content,
                        composed_state,
                        turn,
                        session_id,
                        depth,
                        inject_diversity,
                        prior_verdict_critique,
                    )
                )
                artifact_state = self.state_manager.update_artifact_state(
                    artifact_state, verifier_output, turn
                )
                total_tokens_input += verifier_output.tokens_used_input
                total_tokens_output += verifier_output.tokens_used_output
            else:
                verifier_output = RoleOutput(
                    role=RoleType.VERIFIER,
                    content="(verifier disabled)",
                )

            if (
                self.verifier_enabled
                and self.prompt_assembler.verifier_output_score(verifier_output.content)
                == 0.0
                and self.search_over_inference
            ):
                log_event(
                    self._logger,
                    "search_inference.start",
                    session_id=session_id,
                    depth=depth,
                    turn=turn,
                    trigger="verifier_zero_score",
                    planner_output=text_summary(planner_output.content),
                    verifier_output=text_summary(verifier_output.content),
                )
                planner_output = self.search_over_inference.generate_best(planner_input)
                critic_output = self.role_agent.invoke(
                    self._role_input(
                        task,
                        rubric,
                        RoleType.CRITIC,
                        planner_output.content,
                        composed_state,
                        turn,
                        session_id,
                        depth,
                        True,
                        prior_verdict_critique,
                    )
                )
                verifier_output = self.role_agent.invoke(
                    self._role_input(
                        task,
                        rubric,
                        RoleType.VERIFIER,
                        planner_output.content,
                        composed_state,
                        turn,
                        session_id,
                        depth,
                        True,
                        prior_verdict_critique,
                    )
                )

            reviser_combined_input = self.prompt_assembler.build_reviser_prior_output(
                planner_output=planner_output.content,
                critic_output=critic_output.content,
                verifier_output=verifier_output.content,
                prior_verdict_critique=prior_verdict_critique,
                recursive_results=recursive_results,
                inject_diversity=inject_diversity,
                original_task=task if turn >= 3 else None,
                task=task,
                rubric=rubric,
                synthesizer_enabled=self.synthesizer_enabled,
            )

            if role_search_calls_this_turn < self.role_search_max_calls_per_turn:
                before = len(artifact_state.search_results)
                reviser_context = (
                    f"CRITIC ISSUES:\n{critic_output.content}\n\n"
                    f"VERIFIER FAILS:\n{verifier_output.content}\n\n"
                    f"PLAN:\n{planner_output.content}"
                )
                artifact_state = self._maybe_run_role_search(
                    role=RoleType.REVISER,
                    context=reviser_context,
                    trigger="after_verifier",
                    source_label="critic_and_verifier_issues",
                    artifact_state=artifact_state,
                    session_id=session_id,
                    depth=depth,
                    turn=turn,
                    task=task,
                    planner_output=planner_output.content,
                    critic_output=critic_output.content,
                    verifier_output=verifier_output.content,
                    revised_output=None,
                    prior_verdict_critique=prior_verdict_critique,
                    rubric_has_accuracy=rubric_has_accuracy,
                )
                if len(artifact_state.search_results) > before:
                    role_search_calls_this_turn += 1
                    composed_state = composed_state.model_copy(
                        update={"artifact": artifact_state}
                    )

            reviser_output = self.role_agent.invoke(
                self._role_input(
                    task,
                    rubric,
                    RoleType.REVISER,
                    reviser_combined_input,
                    composed_state,
                    turn,
                    session_id,
                    depth,
                    inject_diversity,
                    prior_verdict_critique,
                )
            )
            artifact_state = self.state_manager.update_artifact_state(
                artifact_state, reviser_output, turn
            )
            total_tokens_input += reviser_output.tokens_used_input
            total_tokens_output += reviser_output.tokens_used_output

            if role_search_calls_this_turn < self.role_search_max_calls_per_turn:
                before = len(artifact_state.search_results)
                artifact_state = self._maybe_run_role_search(
                    role=RoleType.SYNTHESIZER,
                    context=reviser_output.content,
                    trigger="after_reviser",
                    source_label="revised_output",
                    artifact_state=artifact_state,
                    session_id=session_id,
                    depth=depth,
                    turn=turn,
                    task=task,
                    planner_output=planner_output.content,
                    critic_output=critic_output.content,
                    verifier_output=verifier_output.content,
                    revised_output=reviser_output.content,
                    prior_verdict_critique=prior_verdict_critique,
                    rubric_has_accuracy=rubric_has_accuracy,
                )
                if len(artifact_state.search_results) > before:
                    role_search_calls_this_turn += 1
                    composed_state = composed_state.model_copy(
                        update={"artifact": artifact_state}
                    )

            for artifact in [
                artifact
                for artifact in reviser_output.artifacts
                if artifact.can_invoke_model
            ]:
                if depth < self.max_depth:
                    log_event(
                        self._logger,
                        "recursion.start",
                        session_id=session_id,
                        depth=depth,
                        artifact_id=artifact.artifact_id,
                    )
                    recursive_loop_result = self.run(
                        task=artifact.content,
                        rubric=rubric,
                        skill_name=skill_name,
                        session_id=f"{session_id}-r{depth + 1}-{artifact.artifact_id}",
                        parent_session_id=session_id,
                        depth=depth + 1,
                    )
                    recursive_results[artifact.artifact_id] = (
                        recursive_loop_result.final_output
                    )
                    log_event(
                        self._logger,
                        "recursion.complete",
                        session_id=session_id,
                        depth=depth,
                        artifact_id=artifact.artifact_id,
                        child_session_id=recursive_loop_result.session_id,
                    )

            # --- Synthesizer (optional; when disabled, reviser output is final) ---
            if self.synthesizer_enabled:
                synthesizer_input = (
                    self.prompt_assembler.build_synthesizer_prior_output(
                        revised_output=reviser_output.content,
                        prior_verdict_critique=prior_verdict_critique,
                        recursive_results=recursive_results,
                        task=task,
                        rubric=rubric,
                    )
                )
                synthesizer_output = self.role_agent.invoke(
                    self._role_input(
                        task,
                        rubric,
                        RoleType.SYNTHESIZER,
                        synthesizer_input,
                        composed_state,
                        turn,
                        session_id,
                        depth,
                        inject_diversity,
                        prior_verdict_critique,
                    )
                )
                artifact_state = self.state_manager.update_artifact_state(
                    artifact_state, synthesizer_output, turn
                )
                total_tokens_input += synthesizer_output.tokens_used_input
                total_tokens_output += synthesizer_output.tokens_used_output
                final_output = synthesizer_output.content
            else:
                synthesizer_output = RoleOutput(
                    role=RoleType.SYNTHESIZER,
                    content="(synthesizer disabled)",
                )
                final_output = reviser_output.content

            exhausted = self._token_budget_exhausted(
                total_tokens_input, total_tokens_output
            )
            verdict = self.evaluator.grade(
                task=task, rubric=rubric, output=final_output, turn=turn
            )
            log_event(
                self._logger,
                "verdict.complete",
                session_id=session_id,
                depth=depth,
                turn=turn,
                passed=verdict.passed,
                score=verdict.score,
                per_criterion=verdict.per_criterion,
                critique=text_summary(verdict.critique),
                root_causes=text_summary(verdict.root_causes),
                suggested_fix=text_summary(verdict.suggested_fix),
                exhausted=exhausted,
                cumulative_tokens_input=total_tokens_input,
                cumulative_tokens_output=total_tokens_output,
            )
            turn_record = LoopTurnRecord(
                turn=turn,
                role_outputs={
                    "planner": planner_output.content,
                    "critic": critic_output.content,
                    "verifier": verifier_output.content,
                    "reviser": reviser_output.content,
                    "synthesizer": synthesizer_output.content,
                },
                verdict=verdict,
                elapsed_seconds=perf_counter() - turn_start,
                recursive_results=recursive_results,
            )
            loop_turns.append(turn_record)
            log_event(
                self._logger,
                "turn.complete",
                session_id=session_id,
                depth=depth,
                turn=turn,
                elapsed_seconds=turn_record.elapsed_seconds,
                passed=verdict.passed,
                score=verdict.score,
                exhausted=exhausted,
                planner_output=text_summary(planner_output.content),
                critic_output=text_summary(critic_output.content),
                verifier_output=text_summary(verifier_output.content),
                reviser_output=text_summary(reviser_output.content),
                synthesizer_output=text_summary(synthesizer_output.content),
                recursive_result_count=len(recursive_results),
                cumulative_tokens_input=total_tokens_input,
                cumulative_tokens_output=total_tokens_output,
            )
            if verdict.passed and verdict.score >= self.pass_threshold:
                try:
                    rules = self.state_manager.distill_to_memory(
                        task, loop_turns, self.client
                    )
                except Exception as exc:
                    log_event(
                        self._logger,
                        "memory.distill.error",
                        session_id=session_id,
                        depth=depth,
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                        success=False,
                    )
                    rules = []
                result = self._result(
                    session_id,
                    parent_session_id,
                    task,
                    final_output,
                    LoopStatus.PASSED,
                    loop_turns,
                    rules,
                    total_tokens_input,
                    total_tokens_output,
                )
                self._log_session_complete(result, depth)
                return result
            if exhausted:
                result = self._result(
                    session_id,
                    parent_session_id,
                    task,
                    final_output,
                    LoopStatus.EXHAUSTED,
                    loop_turns,
                    [],
                    total_tokens_input,
                    total_tokens_output,
                )
                self._log_session_complete(result, depth)
                return result
            self.state_manager.append_memory_entry(
                MemoryEntry(
                    task_hint=task[:80],
                    stage=MemoryStage.FAIL,
                    content=verdict.critique,
                    session_id=session_id,
                )
            )
            self.state_manager.append_memory_entry(
                MemoryEntry(
                    task_hint=task[:80],
                    stage=MemoryStage.INVESTIGATE,
                    content=verdict.root_causes,
                    session_id=session_id,
                )
            )
            prior_verdict_critique = verdict.critique

        try:
            rules = self.state_manager.distill_to_memory(task, loop_turns, self.client)
        except Exception as exc:
            log_event(
                self._logger,
                "memory.distill.error",
                session_id=session_id,
                depth=depth,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            rules = []
        result = self._result(
            session_id,
            parent_session_id,
            task,
            final_output,
            LoopStatus.EXHAUSTED,
            loop_turns,
            rules,
            total_tokens_input,
            total_tokens_output,
        )
        self._log_session_complete(result, depth)
        return result

    def _invoke_planner(
        self,
        planner_input: RoleInput,
        turn: int,
        prior_verdict_critique: str | None,
        loop_turns: list[LoopTurnRecord],
    ):
        if (
            self.search_over_inference is not None
            and turn >= 3
            and prior_verdict_critique is not None
            and loop_turns
            and loop_turns[-1].verdict is not None
            and loop_turns[-1].verdict.score < 0.5
        ):
            return self.search_over_inference.generate_best(planner_input)
        return self.role_agent.invoke(planner_input)

    def _inject_search_context(
        self,
        artifact_state: ArtifactState,
        task: str,
        session_id: str,
        depth: int,
    ) -> ArtifactState:
        if self.search_provider is None:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                reason="no_search_provider",
            )
            return artifact_state
        provider_name = getattr(
            self.search_provider, "name", self.search_provider.__class__.__name__
        )
        queries = self._search_queries_for_task(task)
        log_event(
            self._logger,
            "search.plan",
            session_id=session_id,
            depth=depth,
            provider=provider_name,
            query_count=len(queries),
            queries=[text_summary(query) for query in queries],
        )
        updated = artifact_state
        for query_index, query in enumerate(queries, start=1):
            updated = self._run_search_query(
                artifact_state=updated,
                query=query,
                provider_name=provider_name,
                session_id=session_id,
                depth=depth,
                query_index=query_index,
                query_count=len(queries),
            )
        return updated

    def _maybe_run_planner_search(
        self,
        *,
        artifact_state: ArtifactState,
        context: str,
        session_id: str,
        depth: int,
        turn: int,
    ) -> ArtifactState:
        """Run planner-scoped search right before the Planner executes.

        Uses the baseline search provider (not RoleSearchPlanner) with the
        full task + prior critique context. Results are tagged as 'planner'
        and only appear in the Planner's system prompt.
        """
        if self.search_provider is None:
            return artifact_state
        # On turns ≥ 2, skip if we already have planner results from prior turns
        # (they accumulate in artifact_state.search_results across turns).
        existing_planner_results = [
            r
            for r in artifact_state.search_results
            if r.metadata.get("role", "planner") == "planner"
        ]
        if turn > 1 and existing_planner_results:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role="planner",
                trigger="before_planner",
                reason="already_have_planner_results",
            )
            return artifact_state
        return self._inject_search_context(
            artifact_state=artifact_state,
            task=context,
            session_id=session_id,
            depth=depth,
        )

    def _maybe_run_role_search(
        self,
        *,
        role: RoleType,
        context: str,
        trigger: str,
        source_label: str,
        artifact_state: ArtifactState,
        session_id: str,
        depth: int,
        turn: int,
        task: str,
        planner_output: str | None,
        critic_output: str | None,
        verifier_output: str | None,
        revised_output: str | None,
        prior_verdict_critique: str | None,
        rubric_has_accuracy: bool,
    ) -> ArtifactState:
        """Run role-scoped search if the trigger policy fires and budgets allow.

        Returns ``artifact_state`` unchanged when disabled, when the trigger
        policy is False, or when the per-turn / total-record budgets are
        exhausted. Otherwise appends the new :class:`SearchRecord` instances.
        """
        planner = self.role_search_planner
        if planner is None or not planner.enabled:
            return artifact_state
        if len(artifact_state.search_results) >= self.role_search_max_total_records:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                reason="total_records_budget_exhausted",
            )
            return artifact_state
        if not planner_should_search(
            role,
            task=task,
            planner_output=planner_output,
            critic_output=critic_output,
            verifier_output=verifier_output,
            revised_output=revised_output,
            prior_verdict_critique=prior_verdict_critique,
            turn=turn,
            rubric_has_accuracy=rubric_has_accuracy,
        ):
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                reason="trigger_policy_false",
            )
            return artifact_state
        records = planner.plan_and_execute(
            context=context,
            role=role,
            trigger=trigger,
            session_id=session_id,
            depth=depth,
            turn=turn,
            source_label=source_label,
        )
        if not records:
            return artifact_state
        return artifact_state.model_copy(
            update={
                "search_results": [*artifact_state.search_results, *records],
            }
        )

    def _run_search_query(
        self,
        *,
        artifact_state: ArtifactState,
        query: str,
        provider_name: str,
        session_id: str,
        depth: int,
        query_index: int,
        query_count: int,
    ) -> ArtifactState:
        log_event(
            self._logger,
            "search.start",
            session_id=session_id,
            depth=depth,
            provider=provider_name,
            query=text_summary(query),
            query_index=query_index,
            query_count=query_count,
            max_results=self.search_max_results,
        )
        content = self.search_provider.search(
            query, max_results=self.search_max_results
        )
        search_record = SearchRecord(
            query=query,
            content=content,
            provider=provider_name,
            turn=0,
            metadata={
                "query_index": query_index,
                "query_count": query_count,
                "role": "planner",
            },
        )
        metrics = dict(artifact_state.metrics)
        metrics["search_calls"] = metrics.get("search_calls", 0) + 1
        metrics["last_search_query"] = query
        updated = artifact_state.model_copy(
            update={
                "search_results": [*artifact_state.search_results, search_record],
                "metrics": metrics,
            }
        )
        log_event(
            self._logger,
            "search.complete",
            session_id=session_id,
            depth=depth,
            provider=provider_name,
            query=text_summary(query),
            query_index=query_index,
            query_count=query_count,
            content_chars=len(content),
            content=text_summary(content),
            result_count=len(updated.search_results),
            success=True,
        )
        return updated

    def _search_queries_for_task(self, task: str) -> list[str]:
        base_question = (
            _extract_section(task, "Original User Request")
            or _extract_section(task, "User Question")
            or task
        )
        base_question = _clean_query(base_question)
        section_title = _document_section_title(task)
        keywords = _context_keywords(task)
        # Use the LLM to generate diverse search queries for well-rounded coverage.
        llm_queries = self._generate_diverse_queries(
            base_question, section_title, keywords
        )
        # Always include the base question as the first query for grounding.
        candidates = [base_question]
        if section_title:
            candidates.append(f"{base_question} {section_title}")
        if keywords:
            candidates.append(f"{base_question} {' '.join(keywords)}")
        if section_title and keywords:
            candidates.append(f"{section_title} {' '.join(keywords)}")
        candidates.extend(llm_queries)

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = _clean_query(candidate)
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            deduped.append(normalized[:320])
            if len(deduped) >= self.search_query_count:
                break
        return deduped or [_clean_query(task)[:320]]

    def _generate_diverse_queries(
        self,
        base_question: str,
        section_title: str,
        keywords: list[str],
    ) -> list[str]:
        """Ask the LLM to produce diverse search queries for multi-perspective coverage."""
        context_parts: list[str] = []
        if section_title:
            context_parts.append(f"Document section: {section_title}")
        if keywords:
            context_parts.append(f"Keywords: {', '.join(keywords)}")
        context_block = (
            "\n".join(context_parts) if context_parts else "No additional context."
        )
        prompt = (
            "You are a search query planner. Given the user's question and optional context, "
            f"generate {self.search_query_count} diverse web search queries that explore "
            "different facets of the question — including supporting evidence, opposing "
            "viewpoints, recent developments, and background context. Each query should be "
            "a concise web search string (no more than 60 words). Return one query per line, "
            "with no numbering, bullets, or extra commentary.\n\n"
            f"User question:\n{base_question}\n\n"
            f"Context:\n{context_block}\n\n"
            f"Queries:"
        )
        messages = [
            {"role": "system", "content": "You generate diverse web search queries."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=512,
            )
            raw = _extract_text(response)
        except Exception:
            return []
        queries: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip().strip('"').strip("'").strip("*").strip("-")
            stripped = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            if stripped and len(stripped) > 5:
                queries.append(stripped)
        return queries

    def _route_skill_context(
        self,
        artifact_state: ArtifactState,
        requested_skill_name: str,
        task: str,
        session_id: str,
        depth: int,
    ) -> tuple[ArtifactState, str]:
        if self.skill_router is None:
            log_event(
                self._logger,
                "skill.route.skip",
                session_id=session_id,
                depth=depth,
                requested_skill_name=requested_skill_name,
                reason="no_skill_router",
            )
            return artifact_state, requested_skill_name
        log_event(
            self._logger,
            "skill.route.start",
            session_id=session_id,
            depth=depth,
            requested_skill_name=requested_skill_name,
            task=text_summary(task),
            top_k=self.skill_top_k,
        )
        route_result = self.skill_router.route(task, top_k=self.skill_top_k)
        selected = route_result.selected
        routed_at = getattr(route_result, "routed_at", None)
        log_event(
            self._logger,
            "skill.route",
            session_id=session_id,
            depth=depth,
            discovered_count=route_result.discovered_count,
            selected_count=len(selected),
            routed_at=routed_at.isoformat() if routed_at is not None else "",
        )
        for skill in selected:
            log_event(
                self._logger,
                "skill.selected",
                session_id=session_id,
                depth=depth,
                skill_id=skill.skill_id,
                readiness=skill.readiness.value,
                score=skill.score,
                missing_capabilities=skill.missing_capabilities,
                degraded_capabilities=skill.degraded_capabilities,
                references_loaded=skill.references_loaded,
                semantic_score=skill.semantic_score,
                lexical_score=skill.lexical_score,
                reason=skill.reason,
                source_file=skill.source_file,
                excerpt=text_summary(skill.content_excerpt),
            )
        primary = (
            selected[0].skill_id
            if selected and selected[0].readiness.value != "blocked"
            else requested_skill_name
        )
        log_event(
            self._logger,
            "skill.route.complete",
            session_id=session_id,
            depth=depth,
            requested_skill_name=requested_skill_name,
            primary_skill_name=primary,
            selected_skill_ids=[skill.skill_id for skill in selected],
            selected_readiness=[skill.readiness.value for skill in selected],
        )
        return artifact_state.model_copy(update={"selected_skills": selected}), primary

    @staticmethod
    def _role_input(
        task,
        rubric,
        role,
        prior_output,
        composed_state,
        turn,
        session_id,
        depth,
        inject_diversity,
        prior_verdict_critique,
    ):
        return RoleInput(
            task=task,
            rubric=rubric,
            role=role,
            prior_output=prior_output,
            composed_state=composed_state,
            turn=turn,
            session_id=session_id,
            depth=depth,
            inject_diversity=inject_diversity,
            prior_verdict_critique=prior_verdict_critique,
            original_task=task,
        )

    @staticmethod
    def _should_inject_diversity(loop_turns: list[LoopTurnRecord]) -> bool:
        if len(loop_turns) < 2:
            return False
        recent_scores = [
            turn.verdict.score for turn in loop_turns[-2:] if turn.verdict is not None
        ]
        return (
            len(recent_scores) == 2 and max(recent_scores) - min(recent_scores) < 0.05
        )

    def _token_budget_exhausted(
        self, total_tokens_input: int, total_tokens_output: int
    ) -> bool:
        return (
            total_tokens_input + total_tokens_output
        ) > self.max_total_tokens_per_session

    @staticmethod
    def _budget_verdict(rubric: list[RubricCriterion]) -> EvalVerdict:
        return EvalVerdict(
            passed=False,
            score=0.0,
            per_criterion={criterion.label: False for criterion in rubric},
            critique="Session token budget exhausted.",
            root_causes="Cumulative token usage exceeded max_total_tokens_per_session.",
            suggested_fix="Reduce state size, max_turns, recursion, or candidate search.",
        )

    @staticmethod
    def _result(
        session_id,
        parent_session_id,
        task,
        final_output,
        status,
        loop_turns,
        rules,
        total_tokens_input,
        total_tokens_output,
    ):
        return LoopResult(
            session_id=session_id,
            parent_session_id=parent_session_id,
            task=task,
            final_output=final_output,
            status=status,
            turns_used=len(loop_turns),
            final_score=(
                loop_turns[-1].verdict.score
                if loop_turns and loop_turns[-1].verdict
                else 0.0
            ),
            turns=loop_turns,
            memory_rules_added=rules,
            total_tokens_input=total_tokens_input,
            total_tokens_output=total_tokens_output,
        )

    def _log_session_complete(self, result: LoopResult, depth: int) -> None:
        log_event(
            self._logger,
            "session.complete",
            session_id=result.session_id,
            depth=depth,
            status=result.status.value,
            turns_used=result.turns_used,
            final_score=result.final_score,
            parent_session_id=result.parent_session_id,
            task=text_summary(result.task),
            final_output=text_summary(result.final_output),
            memory_rules_added_count=len(result.memory_rules_added),
            total_tokens_input=result.total_tokens_input,
            total_tokens_output=result.total_tokens_output,
            success=result.status == LoopStatus.PASSED,
        )


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^# {re.escape(heading)}\n(?P<body>.*?)(?=^# |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group("body").strip() if match else ""


def _document_section_title(text: str) -> str:
    match = re.search(r"^# Document Section (?P<title>.+)$", text, re.MULTILINE)
    return _clean_query(match.group("title")) if match else ""


def _context_keywords(text: str) -> list[str]:
    context = _extract_section(text, "Document Section") or text
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{3,}", context[:6000])
    stopwords = {
        "about",
        "after",
        "also",
        "attached",
        "before",
        "being",
        "chunk",
        "document",
        "from",
        "have",
        "mode",
        "original",
        "request",
        "section",
        "task",
        "that",
        "their",
        "there",
        "this",
        "user",
        "verify",
        "with",
        "words",
        "would",
    }
    counts = Counter(word.lower() for word in words if word.lower() not in stopwords)
    return [word for word, _ in counts.most_common(8)]


def _clean_query(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip().strip("#`).:- ")
        if not stripped:
            continue
        if stripped.lower().startswith(
            ("mode", "chunk id", "words", "format", "sha256")
        ):
            continue
        lines.append(stripped)
    return " ".join(" ".join(lines).split())


def _extract_text(response) -> str:
    """Extract text content from a chat completion response (SDK or dict-like)."""
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            return str(getattr(message, "content", "") or "")
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            return str(message.get("content", ""))
        return str(response.get("content") or response.get("output_text") or "")
    for attr in ("content", "output_text", "text"):
        value = getattr(response, attr, None)
        if value:
            return str(value)
    return ""
