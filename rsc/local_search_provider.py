"""Local content search provider.

Implements the SearchProvider protocol using the VectorIndex to search
across all previously persisted chat content. Returns results in the same
markdown format as web search providers so they integrate seamlessly
into the prompt assembly pipeline.
"""

from __future__ import annotations

import time
from pathlib import Path

from .chat_store import ChatStore
from .contracts import SearchRecord
from .observability import get_logger, log_event, text_summary
from .vector_index import VectorIndex


class LocalSearchProvider:
    """Searches locally persisted chat content using dense embeddings.

    Implements a search(query, max_results) interface compatible with the
    existing SearchProvider protocol used by RoleSearchPlanner.
    """

    name = "local"

    def __init__(
        self,
        vector_index: VectorIndex,
        min_score: float = 0.15,
    ) -> None:
        self.vector_index = vector_index
        self.min_score = min_score
        self._logger = get_logger("local_search")

    def search(self, query: str, *, max_results: int = 5) -> str:
        """Return markdown-structured local content matching the query."""
        if not self.vector_index.is_loaded:
            return ""

        started = time.perf_counter()
        results = self.vector_index.search(query, top_k=max_results)
        elapsed = time.perf_counter() - started

        # Filter by minimum score
        results = [r for r in results if r.score >= self.min_score]

        if not results:
            log_event(
                self._logger,
                "local_search.empty",
                session_id="",
                depth=0,
                query=text_summary(query),
                elapsed_seconds=elapsed,
            )
            return ""

        # Format as markdown, similar to web search results
        sections: list[str] = []
        for result in results:
            chunk = result.chunk
            header = f"### [{chunk.role.title()}] Session {chunk.session_id[:8]}… (turn {chunk.turn}, score {result.score:.3f})"
            sections.append(f"{header}\n\n{chunk.text}")

        markdown = "\n\n---\n\n".join(sections)

        log_event(
            self._logger,
            "local_search.complete",
            session_id="",
            depth=0,
            query=text_summary(query),
            result_count=len(results),
            top_score=results[0].score if results else 0,
            elapsed_seconds=elapsed,
            chunk_count=self.vector_index.chunk_count,
        )

        return markdown

    def search_as_records(
        self,
        query: str,
        *,
        max_results: int = 5,
        turn: int = 0,
    ) -> list[SearchRecord]:
        """Return SearchRecord instances for direct injection into ArtifactState."""
        if not self.vector_index.is_loaded:
            return []

        results = self.vector_index.search(query, top_k=max_results)
        results = [r for r in results if r.score >= self.min_score]

        records: list[SearchRecord] = []
        for result in results:
            chunk = result.chunk
            records.append(
                SearchRecord(
                    query=query,
                    content=chunk.text,
                    provider="local",
                    turn=turn,
                    metadata={
                        "source": "local",
                        "session_id": chunk.session_id,
                        "original_role": chunk.role,
                        "source_type": chunk.source_type,
                        "score": result.score,
                    },
                )
            )

        return records
