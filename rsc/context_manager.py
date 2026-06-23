"""Context window management with tiered LLM summarization.

Enforces the 80% rule: input tokens ≤ floor(0.8 × LLM_CONTEXT_WINDOW_TOKENS),
leaving 20% for output tokens. When the threshold is exceeded, summarizes
system prompt data sections in order of compressibility, starting with
search results.

Key guarantees:
- System and user messages are never summarized or truncated after rendering.
- Summarization operates on underlying data (SearchRecord.content,
  SkillState.domain_knowledge, etc.) *before* rendering.
- Reasoning is never included in chat history or downstream prompts.
- The user message data is never modified by the context manager — only
  composed state (system prompt data) is compressed.
"""

from __future__ import annotations

import hashlib
import time
from copy import deepcopy

from .contracts import ComposedState, RoleType, SearchRecord
from .observability import get_logger, log_event, text_summary
from .retry import retry_call

# ---------------------------------------------------------------------------
# Summarization prompts — generous targets, "precise and concise without
# missing key details"
# ---------------------------------------------------------------------------

SEARCH_SUMMARY_PROMPT = (
    "Summarize the following web search result to create precise and concise "
    "search context without missing key details. Preserve: key facts, dates, "
    "version numbers, named entities, API signatures, code examples, and claims "
    "relevant to the query. Discard: navigation, headers, footers, boilerplate, "
    "repetition, and unrelated content."
)

SEARCH_RE_SUMMARY_PROMPT = (
    "Compress this search summary further to create precise and concise search "
    "context without missing key details. Preserve: the most important fact, "
    "any version numbers or named entities, and the source. Discard everything "
    "else."
)

DOMAIN_KNOWLEDGE_SUMMARY_PROMPT = (
    "Summarize the following domain knowledge to create precise and concise "
    "reference context without missing key details. Preserve: key APIs, data "
    "structures, patterns, constraints, gotchas, and critical examples. "
    "Discard: verbose tutorials, introductory text, and repetition."
)

DOMAIN_KNOWLEDGE_RE_SUMMARY_PROMPT = (
    "Compress this domain reference further to create precise and concise "
    "context without missing key details. Preserve: critical API signatures, "
    "hard constraints, and top gotchas. Discard: examples and explanations."
)

HISTORY_SUMMARY_PROMPT = (
    "Compress this history summary to create precise and concise context "
    "without missing key details. Preserve: recurring patterns, stable "
    "preferences, and key lessons. Discard: one-off details and resolved issues."
)


# ---------------------------------------------------------------------------
# ContextManager
# ---------------------------------------------------------------------------


class ContextManager:
    """Manages context window budget with tiered LLM summarization.

    The 80% rule: input_tokens ≤ floor(0.8 × context_window_tokens).
    When exceeded, summarizes system prompt data sections in order:
    1. Search results (re-summarize to tighter target)
    2. Domain knowledge (re-summarize to tighter target)
    3. Learned rules (trim to top-5, no LLM call)
    4. Ongoing context (drop entirely)
    5. History summary (drop entirely)
    6. Hard abort (exhausted)
    """

    def __init__(
        self,
        *,
        prompt_assembler,
        client,
        model: str,
        context_window_tokens: int = 1_000_000,
        output_tokens: int = 65_536,
        budget_ratio: float = 0.8,
        search_summary_target_tokens: int = 500,
        domain_knowledge_target_tokens: int = 2000,
        history_summary_threshold: int = 1000,
        learned_rules_threshold: int = 15,
    ) -> None:
        self.prompt_assembler = prompt_assembler
        self.client = client
        self.model = model
        self.context_window_tokens = context_window_tokens
        self.output_tokens = output_tokens
        self.budget_ratio = budget_ratio
        self.search_summary_target_tokens = search_summary_target_tokens
        self.domain_knowledge_target_tokens = domain_knowledge_target_tokens
        self.history_summary_threshold = history_summary_threshold
        self.learned_rules_threshold = learned_rules_threshold
        self._cache: dict[str, str] = {}
        self._logger = get_logger("context_manager")

    @property
    def input_budget(self) -> int:
        return int(self.budget_ratio * self.context_window_tokens)

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def summarize(
        self,
        content: str,
        *,
        instruction: str,
        target_tokens: int,
        session_id: str,
        depth: int,
        section: str = "context",
    ) -> str:
        """Summarize content via LLM, cached by content hash.

        On LLM error, returns the original content unchanged (fail open).
        """
        if not content.strip():
            return content
        key = self._hash(content)
        if key in self._cache:
            return self._cache[key]
        prompt = (
            f"{instruction}\n\n"
            f"Aim for approximately {target_tokens} tokens. "
            f"Do not exceed {target_tokens * 2} tokens.\n\n"
            f"Content:\n{content}"
        )
        tokens_before = self.prompt_assembler.count_tokens(content)
        log_event(
            self._logger,
            "context.summarize",
            session_id=session_id,
            depth=depth,
            section=section,
            content_hash=key,
            tokens_before=tokens_before,
            target_tokens=target_tokens,
            cache_hit=False,
            success=True,
        )
        try:
            response = retry_call(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You create precise and concise summaries without missing key details.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                )
            )
            raw = response.choices[0].message.content or content
        except Exception as exc:
            log_event(
                self._logger,
                "context.summarize.failed",
                session_id=session_id,
                depth=depth,
                section=section,
                content_hash=key,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            return content
        tokens_after = self.prompt_assembler.count_tokens(raw)
        log_event(
            self._logger,
            "context.summarize.complete",
            session_id=session_id,
            depth=depth,
            section=section,
            content_hash=key,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            cache_hit=False,
            success=True,
        )
        self._cache[key] = raw
        return raw

    def enforce_budget(
        self,
        *,
        composed_state: ComposedState,
        role: RoleType,
        session_id: str,
        depth: int,
        turn: int,
    ) -> tuple[ComposedState, bool]:
        """Enforce the 80% input budget on the composed state.

        Returns (possibly_summarized_state, exhausted). When exhausted=True,
        the caller should abort the role call and return an error RoleOutput.

        Only modifies composed_state (system prompt data). The user message
        is never touched.
        """
        state = deepcopy(composed_state)
        input_tokens_before = self._measure_input(state, role)
        budget = self.input_budget
        if input_tokens_before <= budget:
            return composed_state, False

        steps_fired: list[str] = []
        search_summarized = 0
        domain_summarized = False
        rules_trimmed = False
        ongoing_dropped = False
        history_dropped = False

        # Step 1: Re-summarize search results (first to compress)
        if self._has_search_results(state, role):
            search_summarized = self._re_summarize_search(
                state, role, session_id, depth
            )
            if search_summarized > 0:
                steps_fired.append("search_results")
                if self._measure_input(state, role) <= budget:
                    return self._finish(
                        composed_state,
                        state,
                        role,
                        session_id,
                        depth,
                        input_tokens_before,
                        steps_fired,
                        search_summarized,
                        domain_summarized,
                        rules_trimmed,
                        ongoing_dropped,
                        history_dropped,
                        exhausted=False,
                    )

        # Step 2: Re-summarize domain knowledge
        if state.skill.domain_knowledge:
            original = state.skill.domain_knowledge
            summarized = self.summarize(
                original,
                instruction=DOMAIN_KNOWLEDGE_RE_SUMMARY_PROMPT,
                target_tokens=300,
                session_id=session_id,
                depth=depth,
                section="domain_knowledge",
            )
            if summarized != original:
                state.skill.domain_knowledge = summarized
                domain_summarized = True
                steps_fired.append("domain_knowledge")
                if self._measure_input(state, role) <= budget:
                    return self._finish(
                        composed_state,
                        state,
                        role,
                        session_id,
                        depth,
                        input_tokens_before,
                        steps_fired,
                        search_summarized,
                        domain_summarized,
                        rules_trimmed,
                        ongoing_dropped,
                        history_dropped,
                        exhausted=False,
                    )

        # Step 3: Trim learned rules to top-5 (no LLM call)
        if len(state.memory.distilled_rules) > 5:
            state.memory.distilled_rules = state.memory.distilled_rules[-5:]
            rules_trimmed = True
            steps_fired.append("learned_rules")
            if self._measure_input(state, role) <= budget:
                return self._finish(
                    composed_state,
                    state,
                    role,
                    session_id,
                    depth,
                    input_tokens_before,
                    steps_fired,
                    search_summarized,
                    domain_summarized,
                    rules_trimmed,
                    ongoing_dropped,
                    history_dropped,
                    exhausted=False,
                )

        # Step 4: Drop ongoing context
        if state.memory.ongoing_context:
            state.memory.ongoing_context = ""
            ongoing_dropped = True
            steps_fired.append("ongoing_context")
            if self._measure_input(state, role) <= budget:
                return self._finish(
                    composed_state,
                    state,
                    role,
                    session_id,
                    depth,
                    input_tokens_before,
                    steps_fired,
                    search_summarized,
                    domain_summarized,
                    rules_trimmed,
                    ongoing_dropped,
                    history_dropped,
                    exhausted=False,
                )

        # Step 5: Drop history summary
        if state.memory.history_summary:
            state.memory.history_summary = ""
            history_dropped = True
            steps_fired.append("history_summary")

        input_tokens_after = self._measure_input(state, role)
        if input_tokens_after <= budget:
            return self._finish(
                composed_state,
                state,
                role,
                session_id,
                depth,
                input_tokens_before,
                steps_fired,
                search_summarized,
                domain_summarized,
                rules_trimmed,
                ongoing_dropped,
                history_dropped,
                exhausted=False,
            )

        # Step 6: Hard abort
        log_event(
            self._logger,
            "context.exhausted",
            session_id=session_id,
            depth=depth,
            role=role.value,
            turn=turn,
            input_tokens_before=input_tokens_before,
            input_tokens_after_all_steps=input_tokens_after,
            input_budget=budget,
            steps_fired=steps_fired,
        )
        return composed_state, True

    # ------------------------------------------------------------------
    # Proactive summarization (called at injection/load time)
    # ------------------------------------------------------------------

    def summarize_search_record(
        self,
        record: SearchRecord,
        *,
        session_id: str,
        depth: int,
    ) -> SearchRecord:
        """Proactively summarize a search record at injection time."""
        if record.metadata.get("summarized"):
            return record
        tokens = self.prompt_assembler.count_tokens(record.content)
        if tokens <= self.search_summary_target_tokens:
            return record
        summarized = self.summarize(
            record.content,
            instruction=SEARCH_SUMMARY_PROMPT,
            target_tokens=self.search_summary_target_tokens,
            session_id=session_id,
            depth=depth,
            section="search_results",
        )
        new_metadata = dict(record.metadata)
        new_metadata["summarized"] = True
        new_metadata["original_tokens"] = tokens
        return SearchRecord(
            query=record.query,
            content=summarized,
            provider=record.provider,
            turn=record.turn,
            metadata=new_metadata,
        )

    def summarize_domain_knowledge(
        self,
        domain_knowledge: str,
        *,
        session_id: str,
        depth: int,
    ) -> str:
        """Proactively summarize domain knowledge at skill load time."""
        if not domain_knowledge.strip():
            return domain_knowledge
        tokens = self.prompt_assembler.count_tokens(domain_knowledge)
        if tokens <= self.domain_knowledge_target_tokens:
            return domain_knowledge
        return self.summarize(
            domain_knowledge,
            instruction=DOMAIN_KNOWLEDGE_SUMMARY_PROMPT,
            target_tokens=self.domain_knowledge_target_tokens,
            session_id=session_id,
            depth=depth,
            section="domain_knowledge",
        )

    def maybe_summarize_history(
        self,
        history_summary: str,
        *,
        session_id: str,
        depth: int,
    ) -> str:
        """Re-compress history summary when it exceeds the threshold."""
        if not history_summary.strip():
            return history_summary
        tokens = self.prompt_assembler.count_tokens(history_summary)
        if tokens <= self.history_summary_threshold:
            return history_summary
        return self.summarize(
            history_summary,
            instruction=HISTORY_SUMMARY_PROMPT,
            target_tokens=500,
            session_id=session_id,
            depth=depth,
            section="history_summary",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _measure_input(self, state: ComposedState, role: RoleType) -> int:
        """Measure the token count of the system prompt for this role."""
        system = self.prompt_assembler.build_role_system_prompt_for_role(state, role)
        return self.prompt_assembler.count_tokens(system)

    def _has_search_results(self, state: ComposedState, role: RoleType) -> bool:
        role_value = role.value
        for result in state.artifact.search_results:
            if result.metadata.get("role", "planner") == role_value:
                return True
        return False

    def _re_summarize_search(
        self,
        state: ComposedState,
        role: RoleType,
        session_id: str,
        depth: int,
    ) -> int:
        """Re-summarize role-specific search results to a tighter target."""
        role_value = role.value
        count = 0
        new_results: list[SearchRecord] = []
        for result in state.artifact.search_results:
            if result.metadata.get("role", "planner") != role_value:
                new_results.append(result)
                continue
            re_summarized = self.summarize(
                result.content,
                instruction=SEARCH_RE_SUMMARY_PROMPT,
                target_tokens=100,
                session_id=session_id,
                depth=depth,
            )
            new_metadata = dict(result.metadata)
            new_metadata["re_summarized"] = True
            new_results.append(
                SearchRecord(
                    query=result.query,
                    content=re_summarized,
                    provider=result.provider,
                    turn=result.turn,
                    metadata=new_metadata,
                )
            )
            count += 1
        state.artifact.search_results = new_results
        return count

    def _finish(
        self,
        original_state: ComposedState,
        summarized_state: ComposedState,
        role: RoleType,
        session_id: str,
        depth: int,
        input_tokens_before: int,
        steps_fired: list[str],
        search_summarized: int,
        domain_summarized: bool,
        rules_trimmed: bool,
        ongoing_dropped: bool,
        history_dropped: bool,
        *,
        exhausted: bool,
    ) -> tuple[ComposedState, bool]:
        input_tokens_after = self._measure_input(summarized_state, role)
        log_event(
            self._logger,
            "context.enforce",
            session_id=session_id,
            depth=depth,
            role=role.value,
            input_tokens_before=input_tokens_before,
            input_tokens_after=input_tokens_after,
            input_budget=self.input_budget,
            steps_fired=steps_fired,
            search_results_re_summarized=search_summarized,
            domain_knowledge_re_summarized=domain_summarized,
            learned_rules_trimmed=rules_trimmed,
            ongoing_context_dropped=ongoing_dropped,
            history_summary_dropped=history_dropped,
            exhausted=exhausted,
            success=not exhausted,
        )
        return summarized_state, exhausted
