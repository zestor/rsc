"""Tests for chat_store, vector_index, and local_search_provider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rsc.chat_store import ChatStore, ChunkRecord, _chunk_text
from rsc.contracts import LoopResult, LoopStatus, LoopTurnRecord, SearchRecord
from rsc.vector_index import VectorIndex, VectorSearchResult
from rsc.local_search_provider import LocalSearchProvider

# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "Hello world, this is a short text."
        chunks = _chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text_returns_empty(self):
        assert _chunk_text("") == []
        assert _chunk_text("   ") == []

    def test_long_text_splits_on_paragraphs(self):
        paragraphs = [f"Paragraph {i}. " * 20 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = _chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) >= 100 or chunk == chunks[-1]

    def test_single_huge_paragraph_splits_on_sentences(self):
        text = "This is sentence number {}. ".format(0) * 500
        chunks = _chunk_text(text)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# ChunkRecord
# ---------------------------------------------------------------------------


class TestChunkRecord:
    def test_roundtrip_json(self):
        chunk = ChunkRecord(
            chunk_id="test-001",
            session_id="sess-1",
            turn=1,
            role="planner",
            source_type="role_output",
            text="Some content here",
            timestamp="2025-01-01T00:00:00Z",
            metadata={"key": "value"},
        )
        line = chunk.to_json_line()
        restored = ChunkRecord.from_json_line(line)
        assert restored.chunk_id == chunk.chunk_id
        assert restored.text == chunk.text
        assert restored.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# ChatStore
# ---------------------------------------------------------------------------


def _make_result(session_id: str = "test-session") -> LoopResult:
    return LoopResult(
        session_id=session_id,
        task="What is RSC?",
        final_output="# RSC\n\nRecursive Scaffolded Cognition is a framework.",
        status=LoopStatus.PASSED,
        turns_used=1,
        final_score=0.9,
        turns=[
            LoopTurnRecord(
                turn=1,
                role_outputs={
                    "planner": "Plan: investigate RSC architecture.",
                    "critic": "Issues: none found.",
                    "verifier": "Pass: claims verified.",
                    "reviser": "No revisions needed.",
                    "synthesizer": "RSC is a recursive scaffolded cognition framework.",
                },
            )
        ],
        total_tokens_input=1000,
        total_tokens_output=500,
    )


class TestChatStore:
    def test_persist_and_load(self, tmp_path):
        store = ChatStore(tmp_path)
        result = _make_result()
        chunks = store.persist_run(result)
        assert len(chunks) > 0

        session_files = list((tmp_path / "chat_content" / "sessions").glob("*.jsonl"))
        assert len(session_files) == 1

        index_path = tmp_path / "chat_content" / "index.jsonl"
        assert index_path.exists()

        loaded = store.load_all_chunks()
        assert len(loaded) == len(chunks)
        assert loaded[0].session_id == "test-session"

    def test_load_session_chunks(self, tmp_path):
        store = ChatStore(tmp_path)
        result = _make_result("sess-abc")
        store.persist_run(result)

        loaded = store.load_session_chunks("sess-abc")
        assert len(loaded) > 0
        assert all(c.session_id == "sess-abc" for c in loaded)

    def test_chunk_count(self, tmp_path):
        store = ChatStore(tmp_path)
        assert store.chunk_count() == 0
        store.persist_run(_make_result())
        assert store.chunk_count() > 0

    def test_persist_search_results(self, tmp_path):
        store = ChatStore(tmp_path)
        records = [
            SearchRecord(
                query="test query",
                content="Search result content about testing.",
                provider="firecrawl",
                turn=1,
                metadata={"role": "planner"},
            )
        ]
        chunks = store.persist_search_results("sess-1", records)
        assert len(chunks) >= 1
        assert chunks[0].source_type == "search_result"

    def test_multiple_runs(self, tmp_path):
        store = ChatStore(tmp_path)
        store.persist_run(_make_result("run-1"))
        store.persist_run(_make_result("run-2"))
        assert store.chunk_count() > 0
        loaded = store.load_all_chunks()
        session_ids = {c.session_id for c in loaded}
        assert "run-1" in session_ids
        assert "run-2" in session_ids


# ---------------------------------------------------------------------------
# VectorIndex (TF-IDF, no client needed)
# ---------------------------------------------------------------------------


class TestVectorIndex:
    def test_add_and_search(self, tmp_path):
        index = VectorIndex(base_dir=tmp_path / "vectors")

        chunks = [
            ChunkRecord(
                chunk_id="c1",
                session_id="s1",
                turn=1,
                role="planner",
                source_type="role_output",
                text="Recursive scaffolded cognition uses planning and critique.",
                timestamp="2025-01-01T00:00:00Z",
            ),
            ChunkRecord(
                chunk_id="c2",
                session_id="s1",
                turn=1,
                role="critic",
                source_type="role_output",
                text="The insurance industry uses loyalty lists to exploit customers.",
                timestamp="2025-01-01T00:00:00Z",
            ),
            ChunkRecord(
                chunk_id="c3",
                session_id="s2",
                turn=1,
                role="planner",
                source_type="role_output",
                text="Planning involves decomposing tasks into verifiable steps.",
                timestamp="2025-01-01T00:00:00Z",
            ),
        ]
        index.add_chunks(chunks)
        assert index.chunk_count == 3
        assert index.is_loaded

        results = index.search("task planning and decomposition", top_k=2)
        assert len(results) > 0
        # c1 and c3 should rank higher than c2 for a planning query
        result_ids = [r.chunk.chunk_id for r in results]
        assert "c2" not in result_ids or len(results) == 1

    def test_persistence(self, tmp_path):
        base_dir = tmp_path / "vectors"
        index1 = VectorIndex(base_dir=base_dir)
        index1.add_chunks(
            [
                ChunkRecord(
                    chunk_id="persist-1",
                    session_id="s1",
                    turn=1,
                    role="planner",
                    source_type="role_output",
                    text="Persistent chunk about cognition.",
                    timestamp="2025-01-01T00:00:00Z",
                )
            ]
        )

        # Write chunk data to the expected location
        chat_dir = base_dir.parent
        chat_dir.mkdir(parents=True, exist_ok=True)
        (chat_dir / "index.jsonl").write_text(
            json.dumps(
                {
                    "chunk_id": "persist-1",
                    "session_id": "s1",
                    "turn": 1,
                    "role": "planner",
                    "source_type": "role_output",
                    "text": "Persistent chunk about cognition.",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "metadata": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        index2 = VectorIndex(base_dir=base_dir)
        assert index2.chunk_count == 1
        assert "persist-1" in index2._chunks

    def test_empty_search(self, tmp_path):
        index = VectorIndex(base_dir=tmp_path / "vectors")
        assert index.search("anything") == []

    def test_add_skips_duplicates(self, tmp_path):
        index = VectorIndex(base_dir=tmp_path / "vectors")
        chunk = ChunkRecord(
            chunk_id="dup-1",
            session_id="s1",
            turn=1,
            role="planner",
            source_type="role_output",
            text="Duplicate chunk about testing.",
            timestamp="2025-01-01T00:00:00Z",
        )
        index.add_chunks([chunk])
        assert index.chunk_count == 1
        index.add_chunks([chunk])
        assert index.chunk_count == 1  # not doubled


# ---------------------------------------------------------------------------
# LocalSearchProvider
# ---------------------------------------------------------------------------


class TestLocalSearchProvider:
    def test_search_returns_markdown(self, tmp_path):
        index = VectorIndex(base_dir=tmp_path / "vectors")
        index.add_chunks(
            [
                ChunkRecord(
                    chunk_id="ls-1",
                    session_id="s1",
                    turn=1,
                    role="planner",
                    source_type="role_output",
                    text="RSC uses recursive loops for planning and critique.",
                    timestamp="2025-01-01T00:00:00Z",
                ),
                ChunkRecord(
                    chunk_id="ls-2",
                    session_id="s1",
                    turn=1,
                    role="critic",
                    source_type="role_output",
                    text="Insurance companies exploit customer loyalty.",
                    timestamp="2025-01-01T00:00:00Z",
                ),
            ]
        )

        provider = LocalSearchProvider(vector_index=index, min_score=0.0)
        result = provider.search("RSC recursive planning")
        assert result  # non-empty
        assert "RSC" in result or "recursive" in result

    def test_search_as_records(self, tmp_path):
        index = VectorIndex(base_dir=tmp_path / "vectors")
        index.add_chunks(
            [
                ChunkRecord(
                    chunk_id="rec-1",
                    session_id="s1",
                    turn=1,
                    role="planner",
                    source_type="role_output",
                    text="Content about testing frameworks and verification.",
                    timestamp="2025-01-01T00:00:00Z",
                ),
            ]
        )

        provider = LocalSearchProvider(vector_index=index, min_score=0.0)
        records = provider.search_as_records("testing", max_results=5)
        assert len(records) == 1
        assert records[0].provider == "local"
        assert records[0].metadata["source"] == "local"

    def test_empty_when_not_loaded(self, tmp_path):
        provider = LocalSearchProvider(
            vector_index=VectorIndex(base_dir=tmp_path / "vectors"),
            min_score=0.0,
        )
        assert provider.search("anything") == ""
        assert provider.search_as_records("anything") == []
