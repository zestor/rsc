"""Generic role-aware search planner.

Takes arbitrary context, deconstructs it into short web search queries using a
role-specific lens, executes those queries against a configured
:class:`~rsc.search_provider.SearchProvider`, and returns
:class:`~rsc.contracts.SearchRecord` instances ready for injection into
``ArtifactState.search_results``.

The planner is harness-owned: the LLM is used only to *generate queries*, never
to invoke search directly. This respects ``design.md`` §0.4 ("The LLM never
directly calls the search service and never mutates search state.").

Feature switch: ``RSCConfig.role_search_enabled`` (env: ``ROLE_SEARCH_ENABLED``,
default off). When off, :meth:`RoleSearchPlanner.plan_and_execute` returns an
empty list without side effects.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

from .contracts import RoleType, SearchRecord
from .observability import get_logger, log_event, text_summary
from .retry import retry_call

# ---------------------------------------------------------------------------
# Role-specific deconstruction lenses
# ---------------------------------------------------------------------------

#: Shared shell appended to every role lens. Enforces short, search-engine
#: style queries with the most important terms first (so truncation, if it
#: fires, is lossless in practice).
_QUERY_FORMAT_CLAUSE = (
    "One query per line. No numbering, no commentary, no quotes. "
    "Aim for short, search-engine-style queries under 12 words — noun "
    "phrases, not full sentences, with stop words dropped. The system will "
    "truncate any longer query to 11 words, so put the most important terms "
    "first."
)

ROLE_SEARCH_LENSES: dict[RoleType, str] = {
    RoleType.PLANNER: (
        "You are generating web search queries to gather evidence and "
        "background needed to decompose the task into a correct plan. "
        "Explore supporting evidence, prior art, canonical implementations, "
        "and background context. Prefer authoritative sources, current "
        "versions, and official docs for any named libraries, APIs, or "
        "standards.\n\n" + _QUERY_FORMAT_CLAUSE
    ),
    RoleType.CRITIC: (
        "You are generating adversarial web search queries that look for "
        "reasons the proposed plan could be wrong, not reasons it is right. "
        "Explore known failure modes, deprecations, breaking changes, "
        "security advisories, common bugs, and counter-evidence to the "
        "proposed approach. Include opposing viewpoints and recent incident "
        "reports.\n\n" + _QUERY_FORMAT_CLAUSE
    ),
    RoleType.VERIFIER: (
        "You are generating fact-checking web search queries for the "
        "specific claims in the output. For each factual claim, version "
        "number, API behavior, or rubric requirement that could be wrong, "
        "produce one targeted query. Prioritize official docs, specs, and "
        "release notes over secondary commentary.\n\n" + _QUERY_FORMAT_CLAUSE
    ),
    RoleType.REVISER: (
        "You are generating targeted web search queries to resolve each "
        "specific open issue in the plan. One query per concrete issue. "
        "Look for the fix, the canonical pattern, or the authoritative "
        "reference that closes the issue.\n\n" + _QUERY_FORMAT_CLAUSE
    ),
    RoleType.SYNTHESIZER: (
        "You are generating citation-resolution web search queries for the "
        "named entities in the revised output. Explore canonical URLs, "
        "official documentation pages, spec sections, and authoritative "
        "references for named libraries, standards, APIs, and cited claims, "
        "so the final deliverable can link primary sources. One query per "
        "distinct named entity worth citing.\n\n" + _QUERY_FORMAT_CLAUSE
    ),
}


# ---------------------------------------------------------------------------
# Trigger policies (harness-side predicates; LLM never decides)
# ---------------------------------------------------------------------------

# Cheap regex for "names a specific library/API/version/standard" detection.
# Matches things like "Python 3.12", "react@18", "RFC 7231", "numpy 2.0".
_NAMED_ENTITY_PATTERN = __import__("re").compile(
    r"\b(?:"
    r"(?:[A-Z][a-zA-Z0-9]*\.)+[A-Z][a-zA-Z0-9]*"  # dotted names: org.Library
    r"|[A-Z][a-zA-Z]+\s*v?\d+(?:\.\d+)*"  # Name 1.2 / Name v1.2
    r"|RFC\s*\d+"
    r"|ISO\s*\d+"
    r"|[a-z][a-zA-Z]+(?:-[a-z]+)+\s*\d"  # kebab-name 1.0
    r"|[a-z][a-zA-Z]+@\s*\d+"
    r")\b"
)
_HIGH_MED_PATTERN = __import__("re").compile(
    r"\[SEVERITY:\s*(?:HIGH|MED)\]", __import__("re").IGNORECASE
)
_FAIL_PATTERN = __import__("re").compile(r"\|\s*FAIL\s*\|")
_UNCERTAIN_PATTERN = __import__("re").compile(r"\|\s*UNCERTAIN\s*\|")
_SENTENCE_PATTERN = __import__("re").compile(r"[.!?](?:\s|$)")


def planner_should_search(
    role: RoleType,
    *,
    task: str,  # noqa: ARG001 - reserved for future planner-specific logic
    planner_output: str | None,
    critic_output: str | None,
    verifier_output: str | None,
    revised_output: str | None,
    prior_verdict_critique: str | None,
    turn: int,
    rubric_has_accuracy: bool,
) -> bool:
    """Return True if role-scoped search should run for ``role`` this turn.

    These are harness-side predicates over prior role outputs. The LLM never
    decides whether to search.
    """
    if role is RoleType.PLANNER:
        # Always on turn 1; on later turns only if prior critique cites a gap.
        if turn <= 1:
            return True
        return bool(prior_verdict_critique) and any(
            word in (prior_verdict_critique or "").lower()
            for word in ("gap", "research", "evidence", "missing", "source")
        )
    if role is RoleType.CRITIC:
        # Run if the planner output contains substantive content worth
        # adversarial-checking. Triggers on any plan with 3+ sentences, OR
        # any plan mentioning specific named entities (libraries, standards, etc).
        if not planner_output:
            return False
        # Named entity match: technical content
        if _NAMED_ENTITY_PATTERN.search(planner_output):
            return True
        # Substantive plan: any plan with enough content to benefit from
        # adversarial verification. Use sentence count as a proxy.
        sentences = _SENTENCE_PATTERN.findall(planner_output)
        return len(sentences) >= 5
    if role is RoleType.VERIFIER:
        # Run iff the verifier's own prior pass produced UNCERTAIN/FAIL rows,
        # or the rubric explicitly values factual accuracy.
        if rubric_has_accuracy:
            return True
        if verifier_output and (
            _UNCERTAIN_PATTERN.search(verifier_output)
            or _FAIL_PATTERN.search(verifier_output)
        ):
            return True
        # For research questions: trigger if the planner produced a
        # substantive plan worth fact-checking.
        if planner_output:
            sentences = _SENTENCE_PATTERN.findall(planner_output)
            if len(sentences) >= 5:
                return True
        return False
    if role is RoleType.REVISER:
        # Run iff Critic produced HIGH/MED or Verifier produced FAIL.
        return bool(
            (critic_output and _HIGH_MED_PATTERN.search(critic_output or ""))
            or (verifier_output and _FAIL_PATTERN.search(verifier_output or ""))
        )
    if role is RoleType.SYNTHESIZER:
        # Run iff the revised output names an entity and the rubric values
        # citations.
        return rubric_has_accuracy and bool(
            revised_output and _NAMED_ENTITY_PATTERN.search(revised_output or "")
        )
    return False


# ---------------------------------------------------------------------------
# LLM client protocol (duck-typed; matches OpenAI/OpenRouter adapters)
# ---------------------------------------------------------------------------


class _ChatClient(Protocol):
    def chat(self):  # pragma: no cover - structural only
        ...


# ---------------------------------------------------------------------------
# RoleSearchPlanner
# ---------------------------------------------------------------------------


class RoleSearchPlanner:
    """Generic context → queries → searches → SearchRecords pipeline.

    The core is role-agnostic; the only role-specific part is the
    deconstruction prompt selected from :data:`ROLE_SEARCH_LENSES`.
    """

    def __init__(
        self,
        *,
        search_provider,
        client,
        model: str,
        max_queries_per_call: int = 3,
        max_results_per_query: int = 5,
        max_concurrency: int = 2,
        temperature: float = 0.65,
        max_tokens: int = 1024,
        max_query_words: int = 11,
        enabled: bool = False,
        local_search_provider=None,
    ) -> None:
        self.search_provider = search_provider
        self.client = client
        self.model = model
        self.max_queries_per_call = max_queries_per_call
        self.max_results_per_query = max_results_per_query
        self.max_concurrency = max(1, max_concurrency)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_query_words = max(1, max_query_words)
        self.enabled = enabled
        self.local_search_provider = local_search_provider
        self._logger = get_logger("role_search_planner")

    def plan_and_execute(
        self,
        *,
        context: str,
        role: RoleType,
        trigger: str,
        session_id: str,
        depth: int,
        turn: int,
        source_label: str | None = None,
        max_queries_override: int | None = None,
    ) -> list[SearchRecord]:
        """Deconstruct ``context`` into queries, execute them, return records.

        Returns an empty list when disabled, when there is no search provider,
        or when query generation yields no usable queries. Never raises on
        provider/LLM errors — they are logged and treated as zero results.
        """
        if not self.enabled:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                reason="role_search_disabled",
            )
            return []
        if self.search_provider is None:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                reason="no_search_provider",
            )
            return []

        max_queries = max_queries_override or self.max_queries_per_call
        lens = ROLE_SEARCH_LENSES.get(role, ROLE_SEARCH_LENSES[RoleType.PLANNER])
        prompt = (
            f"{lens}\n\n"
            f"Generate up to {max_queries} diverse queries.\n\n"
            f"Context:\n{context}\n\nQueries:"
        )
        started = time.perf_counter()
        raw_queries = self._generate_queries(prompt, session_id=session_id, depth=depth)
        queries = self._validate_and_truncate(raw_queries, max_queries)

        provider_name = getattr(
            self.search_provider, "name", self.search_provider.__class__.__name__
        )
        log_event(
            self._logger,
            "search.plan",
            session_id=session_id,
            depth=depth,
            role=role.value,
            trigger=trigger,
            source_label=source_label or "",
            provider=provider_name,
            query_count=len(queries),
            queries=[text_summary(q) for q in queries],
            query_word_counts=[len(q.split()) for q in queries],
            queries_truncated=sum(
                1 for q in queries if len(q.split()) >= self.max_query_words
            ),
            query_temperature=self.temperature,
            query_max_tokens=self.max_tokens,
            context_chars=len(context),
            context_hash=text_summary(context),
        )

        if not queries:
            log_event(
                self._logger,
                "search.skip",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                reason="no_valid_queries",
            )
            return []

        records = self._execute_queries(
            queries=queries,
            role=role,
            trigger=trigger,
            source_label=source_label,
            provider_name=provider_name,
            session_id=session_id,
            depth=depth,
            turn=turn,
        )
        elapsed = time.perf_counter() - started
        log_event(
            self._logger,
            "search.role_batch.complete",
            session_id=session_id,
            depth=depth,
            role=role.value,
            trigger=trigger,
            query_count=len(queries),
            record_count=len(records),
            elapsed_seconds=elapsed,
            success=True,
        )

        # Also search local chat content if available
        if self.local_search_provider is not None:
            local_records = self._search_local(
                context=context,
                role=role,
                trigger=trigger,
                session_id=session_id,
                depth=depth,
                turn=turn,
            )
            records.extend(local_records)

        return records

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    def _generate_queries(
        self, prompt: str, *, session_id: str, depth: int
    ) -> list[str]:
        """Call the LLM to produce raw query lines. Never raises."""
        log_event(
            self._logger,
            "search.query_generation.start",
            session_id=session_id,
            depth=depth,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate concise web search queries. "
                    "Return ONLY short noun-phrase queries, one per line. "
                    "No numbering, no commentary, no quotes."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        started = time.perf_counter()
        try:
            response = retry_call(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            )
            raw = _extract_text(response)
            elapsed = time.perf_counter() - started
            queries = [line for line in raw.splitlines() if line.strip()]
            log_event(
                self._logger,
                "search.query_generation.complete",
                session_id=session_id,
                depth=depth,
                elapsed_seconds=elapsed,
                query_count=len(queries),
                success=True,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            log_event(
                self._logger,
                "search.query_generation.failed",
                session_id=session_id,
                depth=depth,
                elapsed_seconds=elapsed,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            return []
        return queries

    def _validate_and_truncate(
        self, raw_lines: list[str], max_queries: int
    ) -> list[str]:
        """Clean, truncate-to-N-words (never drop), dedupe, cap.

        Per the agreed policy: queries longer than ``max_query_words`` are
        truncated to that many words, never dropped. Every generated query
        survives to execution.
        """
        validated: list[str] = []
        seen: set[str] = set()
        for raw in raw_lines:
            cleaned = _clean_query_line(raw)
            if not cleaned:
                continue
            words = cleaned.split()
            if len(words) > self.max_query_words:
                cleaned = " ".join(words[: self.max_query_words])
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            validated.append(cleaned)
            if len(validated) >= max_queries:
                break
        return validated

    # ------------------------------------------------------------------
    # Local content search
    # ------------------------------------------------------------------

    def _search_local(
        self,
        *,
        context: str,
        role: RoleType,
        trigger: str,
        session_id: str,
        depth: int,
        turn: int,
    ) -> list[SearchRecord]:
        """Search locally persisted chat content using the query context."""
        if self.local_search_provider is None:
            return []
        log_event(
            self._logger,
            "local_search.start",
            session_id=session_id,
            depth=depth,
            role=role.value,
            trigger=trigger,
            query_chars=min(len(context), 500),
        )
        try:
            records = self.local_search_provider.search_as_records(
                context[:500],
                max_results=self.max_results_per_query,
                turn=turn,
            )
            log_event(
                self._logger,
                "local_search.complete",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                result_count=len(records),
            )
            return records
        except Exception as exc:
            log_event(
                self._logger,
                "local_search.error",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            return []

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def _execute_queries(
        self,
        *,
        queries: list[str],
        role: RoleType,
        trigger: str,
        source_label: str | None,
        provider_name: str,
        session_id: str,
        depth: int,
        turn: int,
    ) -> list[SearchRecord]:
        """Execute queries concurrently under the concurrency limit."""
        records: list[SearchRecord] = []
        for query_index, query in enumerate(queries, start=1):
            log_event(
                self._logger,
                "search.start",
                session_id=session_id,
                depth=depth,
                role=role.value,
                trigger=trigger,
                provider=provider_name,
                query=text_summary(query),
                query_index=query_index,
                query_count=len(queries),
                max_results=self.max_results_per_query,
            )
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = {
                executor.submit(self._run_one, query, index, len(queries)): query
                for index, query in enumerate(queries, start=1)
            }
            for future in as_completed(futures):
                query = futures[future]
                try:
                    content = future.result()
                except Exception as exc:
                    log_event(
                        self._logger,
                        "search.complete",
                        session_id=session_id,
                        depth=depth,
                        role=role.value,
                        trigger=trigger,
                        provider=provider_name,
                        query=text_summary(query),
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                        success=False,
                    )
                    continue
                record = SearchRecord(
                    query=query,
                    content=content,
                    provider=provider_name,
                    turn=turn,
                    metadata={
                        "role": role.value,
                        "trigger": trigger,
                        "source_label": source_label or "",
                    },
                )
                records.append(record)
                log_event(
                    self._logger,
                    "search.complete",
                    session_id=session_id,
                    depth=depth,
                    role=role.value,
                    trigger=trigger,
                    provider=provider_name,
                    query=text_summary(query),
                    content_chars=len(content),
                    content=text_summary(content),
                    success=True,
                )
        return records

    def _run_one(
        self, query: str, index: int = 0, count: int = 0
    ) -> str:  # noqa: ARG002
        """Execute a single search query with retry. Raises on non-retryable."""
        return retry_call(
            lambda: self.search_provider.search(
                query, max_results=self.max_results_per_query
            )
        )


# ---------------------------------------------------------------------------
# Helpers (mirrors loop_orchestrator._clean_query / _extract_text but kept
# local so this module is self-contained and testable in isolation)
# ---------------------------------------------------------------------------


def _clean_query_line(line: str) -> str:
    """Strip numbering, bullets, quotes, bold markers, and surrounding whitespace."""
    import re

    stripped = line.strip()
    # Remove leading numbering like "1." or "2)"
    stripped = re.sub(r"^\d+[\.\)]\s*", "", stripped)
    # Remove leading bullets like "-" or "*"
    stripped = re.sub(r"^[\*\-]\s*", "", stripped)
    # Strip surrounding quotes and bold markers
    stripped = stripped.strip('"').strip("'").strip("*").strip("-").strip()
    # Remove inline bold markers **text** -> text
    stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
    return stripped.strip()


def _extract_text(response) -> str:
    """Extract text content from a chat completion response (SDK or dict)."""
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            return str(getattr(message, "content", "") or "")
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", "") or "")
    return ""
