"""TF-IDF vector index for cross-chat content retrieval.

Uses scikit-learn's TfidfVectorizer to build sparse TF-IDF vectors from
chunk text. Runs entirely locally — no API calls, no GPU, no external deps
beyond numpy and sklearn.

Storage layout:
    state/chat_content/vectors/
        vectorizer.joblib      # fitted TfidfVectorizer (vocabulary + IDF weights)
        tfidf_matrix.npz       # sparse (N, D) TF-IDF matrix in scipy CSC format
        chunk_ids.json         # ordered list of chunk_ids matching rows
        meta.json              # vocabulary size, chunk count, last_updated
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from .chat_store import ChunkRecord
from .observability import get_logger, log_event


@dataclass
class VectorSearchResult:
    """A chunk returned from vector search."""

    chunk: ChunkRecord
    score: float  # cosine similarity, 0-1


class VectorIndex:
    """Sparse TF-IDF vector index for semantic content retrieval.

    Uses TfidfVectorizer (sublinear TF, IDF weighting, L2-normalized rows)
    to produce sparse vectors. Cosine similarity between a query vector and
    the document matrix is a simple sparse matrix-vector multiply.

    All computation is local — zero API cost, instant startup.
    """

    def __init__(
        self,
        base_dir: str | Path | None = None,
        max_features: int = 262144,
        ngram_range: tuple[int, int] = (1, 2),
        sublinear_tf: bool = True,
    ) -> None:
        self._base_dir = Path(base_dir) if base_dir else None
        self._max_features = max_features
        self._ngram_range = ngram_range
        self._sublinear_tf = sublinear_tf
        self._logger = get_logger("vector_index")

        # Core state
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix: sparse.csc_matrix | None = None  # (N, D) sparse
        self._chunk_ids: list[str] = []
        self._chunks: dict[str, ChunkRecord] = {}

        # Try loading persisted index
        if self._base_dir:
            self._load_from_disk()

    @property
    def chunk_count(self) -> int:
        return len(self._chunk_ids)

    @property
    def is_loaded(self) -> bool:
        return self._matrix is not None and len(self._chunk_ids) > 0

    def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Add new chunks to the index. Rebuilds the vectorizer on all data."""
        if not chunks:
            return

        # Filter out already-indexed chunks
        existing = set(self._chunk_ids)
        new_chunks = [c for c in chunks if c.chunk_id not in existing]
        if not new_chunks:
            return

        # Merge old + new chunks
        all_chunks: list[ChunkRecord] = []
        for cid in self._chunk_ids:
            if cid in self._chunks:
                all_chunks.append(self._chunks[cid])
        all_chunks.extend(new_chunks)

        # Store chunk objects
        for chunk in new_chunks:
            self._chunks[chunk.chunk_id] = chunk

        # Rebuild vectorizer on all text
        all_texts = [c.text for c in all_chunks]
        try:
            self._vectorizer = TfidfVectorizer(
                max_features=self._max_features,
                ngram_range=self._ngram_range,
                sublinear_tf=self._sublinear_tf,
                strip_accents="unicode",
                stop_words="english",
                dtype=np.float32,
            )
            self._matrix = self._vectorizer.fit_transform(all_texts)
        except ValueError:
            # fit_transform raises ValueError if all docs are empty
            return

        # Update chunk_ids in order
        self._chunk_ids = [c.chunk_id for c in all_chunks]

        # Persist
        if self._base_dir:
            self._save_to_disk()

        log_event(
            self._logger,
            "vector_index.add",
            session_id="",
            depth=0,
            new_count=len(new_chunks),
            total_count=len(self._chunk_ids),
            vocabulary_size=(
                self._vectorizer.max_features or len(self._vectorizer.vocabulary_)
            ),
        )

    def search(self, query: str, top_k: int = 5) -> list[VectorSearchResult]:
        """Find the most similar chunks to the query using cosine similarity."""
        if not self.is_loaded or not query.strip() or self._vectorizer is None:
            return []

        # Transform query using the fitted vectorizer
        query_vec = self._vectorizer.transform([query])  # (1, D) sparse
        if query_vec.nnz == 0:
            return []

        # Cosine similarity: rows of _matrix are L2-normalized by TfidfVectorizer,
        # and query_vec is also L2-normalized. So dot product = cosine similarity.
        scores = (self._matrix @ query_vec.T).toarray().ravel()  # (N,)

        # Top-k indices
        k = min(top_k, len(self._chunk_ids))
        if k <= 0:
            return []
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        results: list[VectorSearchResult] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            chunk_id = self._chunk_ids[idx]
            chunk = self._chunks.get(chunk_id)
            if chunk:
                results.append(VectorSearchResult(chunk=chunk, score=score))

        return results

    def rebuild_from_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Rebuild the entire index from a chunk list."""
        self._chunk_ids = []
        self._chunks = {}
        self._matrix = None
        self._vectorizer = None
        self.add_chunks(chunks)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_to_disk(self) -> None:
        if self._base_dir is None or self._vectorizer is None or self._matrix is None:
            return
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(self._vectorizer, str(self._base_dir / "vectorizer.joblib"))
            sparse.save_npz(str(self._base_dir / "tfidf_matrix.npz"), self._matrix)
            (self._base_dir / "chunk_ids.json").write_text(
                json.dumps(self._chunk_ids, ensure_ascii=False),
                encoding="utf-8",
            )
            (self._base_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "vocabulary_size": len(self._vectorizer.vocabulary_),
                        "chunk_count": len(self._chunk_ids),
                        "max_features": self._max_features,
                        "ngram_range": list(self._ngram_range),
                        "last_updated": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            log_event(
                self._logger,
                "vector_index.save.error",
                session_id="",
                depth=0,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )

    def _load_from_disk(self) -> None:
        if self._base_dir is None:
            return
        vec_path = self._base_dir / "vectorizer.joblib"
        mat_path = self._base_dir / "tfidf_matrix.npz"
        ids_path = self._base_dir / "chunk_ids.json"
        if not vec_path.exists() or not mat_path.exists() or not ids_path.exists():
            return
        try:
            self._vectorizer = joblib.load(str(vec_path))
            self._matrix = sparse.load_npz(str(mat_path))
            self._chunk_ids = json.loads(ids_path.read_text(encoding="utf-8"))
            self._load_chunk_objects()
            log_event(
                self._logger,
                "vector_index.load",
                session_id="",
                depth=0,
                chunk_count=len(self._chunk_ids),
                vocabulary_size=len(self._vectorizer.vocabulary_),
                matrix_shape=(self._matrix.shape if self._matrix is not None else None),
            )
        except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
            log_event(
                self._logger,
                "vector_index.load.error",
                session_id="",
                depth=0,
                error=str(exc),
                error_type=exc.__class__.__name__,
                success=False,
            )
            self._chunk_ids = []
            self._vectorizer = None
            self._matrix = None

    def _load_chunk_objects(self) -> None:
        """Load chunk text from the JSONL index file."""
        if self._base_dir is None:
            return
        chat_content_dir = self._base_dir.parent
        index_path = chat_content_dir / "index.jsonl"
        if not index_path.exists():
            return
        needed = set(self._chunk_ids)
        for line in index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                chunk_id = data["chunk_id"]
                if chunk_id in needed:
                    self._chunks[chunk_id] = ChunkRecord(**data)
                    needed.discard(chunk_id)
                    if not needed:
                        break
            except (json.JSONDecodeError, TypeError, KeyError, ValueError):
                continue
