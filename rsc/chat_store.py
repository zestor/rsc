"""Cross-chat content persistence.

After each RSC run, chunks all valuable content (role outputs, search results,
final synthesis) into ~500-token segments and persists them as JSONL files.
Each chunk carries metadata (session_id, turn, role, source_type, timestamp)
so the vector index can retrieve and rank them later.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import LoopResult, LoopTurnRecord, SearchRecord
from .observability import get_logger, log_event, text_summary

# Chunk sizing targets (in characters; ~4 chars/token for English prose)
_TARGET_CHUNK_CHARS = 2000  # ~500 tokens
_OVERLAP_CHARS = 200  # ~50 tokens overlap
_MIN_CHUNK_CHARS = 100  # discard trivially short fragments


@dataclass(frozen=True)
class ChunkRecord:
    """A single persisted content chunk."""

    chunk_id: str
    session_id: str
    turn: int
    role: str  # "planner", "synthesizer", "search", "final", etc.
    source_type: str  # "role_output", "search_result", "final_output"
    text: str
    timestamp: str  # ISO-8601
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "chunk_id": self.chunk_id,
                "session_id": self.session_id,
                "turn": self.turn,
                "role": self.role,
                "source_type": self.source_type,
                "text": self.text,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @classmethod
    def from_json_line(cls, line: str) -> "ChunkRecord":
        data = json.loads(line)
        return cls(**data)


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks targeting ~500 tokens each."""
    if len(text) < _MIN_CHUNK_CHARS:
        return [text] if text.strip() else []

    # Split on paragraph boundaries first
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        if len(buffer) + len(para) + 2 > _TARGET_CHUNK_CHARS and buffer:
            chunks.append(buffer.strip())
            # Keep overlap from end of current buffer
            overlap_start = max(0, len(buffer) - _OVERLAP_CHARS)
            buffer = buffer[overlap_start:] + "\n\n" + para
        else:
            buffer = buffer + "\n\n" + para if buffer else para

    if buffer.strip():
        # If remaining buffer is huge, split it further
        while len(buffer) > _TARGET_CHUNK_CHARS * 1.5:
            split_point = _find_sentence_boundary(buffer, _TARGET_CHUNK_CHARS)
            chunks.append(buffer[:split_point].strip())
            buffer = buffer[max(0, split_point - _OVERLAP_CHARS) :]
        if buffer.strip():
            chunks.append(buffer.strip())

    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]


def _find_sentence_boundary(text: str, target: int) -> int:
    """Find the nearest sentence end (.!?) before target position."""
    # Search backwards from target for a sentence-ending punctuation
    for i in range(min(target, len(text)) - 1, max(0, target - 200), -1):
        if text[i] in ".!?" and i + 1 < len(text) and text[i + 1] in " \n":
            return i + 1
    return target


class ChatStore:
    """Persists run content as chunked JSONL files for cross-chat retrieval."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self._chat_content_dir = self.base_dir / "chat_content"
        self._sessions_dir = self._chat_content_dir / "sessions"
        self._index_path = self._chat_content_dir / "index.jsonl"
        self._logger = get_logger("chat_store")

    def ensure_dirs(self) -> None:
        self._chat_content_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def persist_run(self, result: LoopResult) -> list[ChunkRecord]:
        """Chunk and persist all content from a completed run."""
        self.ensure_dirs()
        now = datetime.now(timezone.utc).isoformat()
        session_id = result.session_id
        chunks: list[ChunkRecord] = []
        chunk_counter = 0

        # 1. Chunk role outputs from each turn
        for turn_record in result.turns:
            for role, content in turn_record.role_outputs.items():
                if not content or not content.strip():
                    continue
                source_type = "final_output" if role == "synthesizer" else "role_output"
                for chunk_text in _chunk_text(content):
                    chunk_counter += 1
                    chunks.append(
                        ChunkRecord(
                            chunk_id=f"{session_id}-{chunk_counter:05d}",
                            session_id=session_id,
                            turn=turn_record.turn,
                            role=role,
                            source_type=source_type,
                            text=chunk_text,
                            timestamp=now,
                        )
                    )

        # 2. Chunk the final output
        if result.final_output and result.final_output.strip():
            for chunk_text in _chunk_text(result.final_output):
                chunk_counter += 1
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{session_id}-{chunk_counter:05d}",
                        session_id=session_id,
                        turn=result.turns_used,
                        role="final",
                        source_type="final_output",
                        text=chunk_text,
                        timestamp=now,
                        metadata={
                            "status": result.status.value,
                            "score": result.final_score,
                        },
                    )
                )

        # 3. Chunk the original task
        if result.task and result.task.strip():
            for chunk_text in _chunk_text(result.task):
                chunk_counter += 1
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{session_id}-{chunk_counter:05d}",
                        session_id=session_id,
                        turn=0,
                        role="user",
                        source_type="task",
                        text=chunk_text,
                        timestamp=now,
                    )
                )

        # Write to session file and global index
        if chunks:
            session_path = self._sessions_dir / f"{session_id}.jsonl"
            lines = [c.to_json_line() for c in chunks]
            session_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with self._index_path.open("a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

            log_event(
                self._logger,
                "chat_store.persist",
                session_id=session_id,
                depth=0,
                chunk_count=len(chunks),
                turns=result.turns_used,
                roles=list({c.role for c in chunks}),
                session_path=str(session_path),
            )

        return chunks

    def load_all_chunks(self) -> list[ChunkRecord]:
        """Load all chunks from the global index."""
        if not self._index_path.exists():
            return []
        chunks: list[ChunkRecord] = []
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(ChunkRecord.from_json_line(line))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return chunks

    def load_session_chunks(self, session_id: str) -> list[ChunkRecord]:
        """Load chunks for a specific session."""
        session_path = self._sessions_dir / f"{session_id}.jsonl"
        if not session_path.exists():
            return []
        chunks: list[ChunkRecord] = []
        for line in session_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(ChunkRecord.from_json_line(line))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return chunks

    def chunk_count(self) -> int:
        """Return total number of chunks in the global index."""
        if not self._index_path.exists():
            return 0
        count = 0
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                count += 1
        return count

    def persist_search_results(
        self,
        session_id: str,
        search_records: list[SearchRecord],
    ) -> list[ChunkRecord]:
        """Persist web search results from a run as retrievable chunks."""
        self.ensure_dirs()
        now = datetime.now(timezone.utc).isoformat()
        chunks: list[ChunkRecord] = []
        chunk_counter = 0

        for record in search_records:
            if not record.content or not record.content.strip():
                continue
            for chunk_text in _chunk_text(record.content):
                chunk_counter += 1
                chunks.append(
                    ChunkRecord(
                        chunk_id=f"{session_id}-sr-{chunk_counter:05d}",
                        session_id=session_id,
                        turn=record.turn,
                        role=record.metadata.get("role", "search"),
                        source_type="search_result",
                        text=chunk_text,
                        timestamp=now,
                        metadata={
                            "query": record.query,
                            "provider": record.provider,
                            **{k: v for k, v in record.metadata.items() if k != "role"},
                        },
                    )
                )

        if chunks:
            with self._index_path.open("a", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(chunk.to_json_line() + "\n")

            log_event(
                self._logger,
                "chat_store.persist_search",
                session_id=session_id,
                depth=0,
                chunk_count=len(chunks),
                query_count=len(search_records),
            )

        return chunks
