"""BM25 lexical retrieval component with student isolation and disk persistence.

Design rationale
----------------
* Dense vector search can struggle on exact keywords, technical terms, equations,
  and acronyms (e.g. ``torch.nn.CrossEntropyLoss``, ``O(n log n)``).
* BM25Okapi provides complementary lexical scoring.
* Per-student index partitioning enforces strict student data isolation.
* Disk persistence in JSON / pickle allows fast restart without recalculation.
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any

from app.core.config import BM25Settings
from app.schemas.domain import RetrievedChunk

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi

    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    BM25Okapi = None
    _BM25_AVAILABLE = False


def tokenize_text(text: str) -> list[str]:
    """Tokenize text into lowercased tokens, preserving alphanumeric technical terms."""
    if not text:
        return []
    # Match words, alphanumeric identifiers, and dotted symbols
    tokens = re.findall(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", text.lower())
    return tokens


class StudentBM25Index:
    """In-memory BM25 index and chunk repository for a single student."""

    def __init__(self, student_id: str, k1: float = 1.5, b: float = 0.75) -> None:
        self.student_id = student_id
        self.k1 = k1
        self.b = b
        self.chunks: list[dict[str, Any]] = []
        self.tokenized_corpus: list[list[str]] = []
        self._model: BM25Okapi | None = None

    def rebuild(self) -> None:
        """Reconstruct BM25 model from current tokenized corpus."""
        if not _BM25_AVAILABLE or not self.tokenized_corpus:
            self._model = None
            return
        self._model = BM25Okapi(self.tokenized_corpus, k1=self.k1, b=self.b)

    def add_chunks(self, doc_id: str, new_chunks: list[dict[str, Any]]) -> None:
        """Add chunks for a document, replacing previous chunks for the same doc_id."""
        # Remove existing chunks for this doc_id (idempotent re-ingestion)
        keep_indices = [i for i, c in enumerate(self.chunks) if c.get("doc_id") != doc_id]
        self.chunks = [self.chunks[i] for i in keep_indices]
        self.tokenized_corpus = [self.tokenized_corpus[i] for i in keep_indices]

        # Add new chunks
        for i, c in enumerate(new_chunks):
            c_copy = dict(c)
            if not c_copy.get("chunk_id"):
                c_copy["chunk_id"] = f"{doc_id}::{i}"
            if not c_copy.get("doc_id"):
                c_copy["doc_id"] = doc_id
            self.chunks.append(c_copy)
            self.tokenized_corpus.append(tokenize_text(c_copy.get("text", "")))

        self.rebuild()

    def remove_document(self, doc_id: str) -> int:
        """Remove all chunks associated with doc_id."""
        before = len(self.chunks)
        keep_indices = [i for i, c in enumerate(self.chunks) if c.get("doc_id") != doc_id]
        self.chunks = [self.chunks[i] for i in keep_indices]
        self.tokenized_corpus = [self.tokenized_corpus[i] for i in keep_indices]
        removed = before - len(self.chunks)
        if removed > 0:
            self.rebuild()
        return removed

    def search(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        """Score query against corpus and return top_k RetrievedChunks."""
        if not self._model or not self.chunks:
            return []

        tokens = tokenize_text(query)
        if not tokens:
            return []

        scores = self._model.get_scores(tokens)
        token_set = set(tokens)
        scored_indices: list[tuple[int, float]] = []
        for idx, score in enumerate(scores):
            raw_s = float(score)
            doc_tokens = set(self.tokenized_corpus[idx])
            overlap = token_set.intersection(doc_tokens)
            if overlap:
                # When N is small, BM25Okapi raw score can be negative. Ensure positive score on term overlap.
                effective_score = max(raw_s, 0.1 * len(overlap))
                scored_indices.append((idx, effective_score))
        scored_indices.sort(key=lambda x: x[1], reverse=True)

        # Normalize scores to [0.0, 1.0] relative to top score for fair comparison
        max_score = scored_indices[0][1] if scored_indices else 1.0
        results: list[RetrievedChunk] = []

        for idx, raw_score in scored_indices[:top_k]:
            chunk_data = self.chunks[idx]
            norm_score = round(raw_score / max(max_score, 1e-6), 4)

            results.append(
                RetrievedChunk(
                    content=str(chunk_data.get("text", "")),
                    source=str(chunk_data.get("source", "unknown")),
                    page=int(chunk_data["page"]) if chunk_data.get("page") is not None else None,
                    score=norm_score,
                    bm25_score=round(raw_score, 4),
                    chunk_id=str(chunk_data.get("chunk_id", "")),
                    document_id=str(chunk_data.get("doc_id", "")),
                    student_id=self.student_id,
                    section_title=str(chunk_data.get("section_title") or ""),
                    section_path=str(chunk_data.get("section_path") or ""),
                    chunk_index=int(chunk_data.get("chunk_index", idx)),
                    content_hash=str(chunk_data.get("content_hash") or ""),
                )
            )
        return results


class BM25Index:
    """Manages student-partitioned BM25 indices with automated disk persistence."""

    def __init__(self, settings: BM25Settings) -> None:
        self.settings = settings
        self.index_dir = Path(settings.index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._student_indices: dict[str, StudentBM25Index] = {}

    def _get_student_file(self, student_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", student_id or "default")
        return self.index_dir / f"{safe_id}.pkl"

    def _get_or_load_index(self, student_id: str) -> StudentBM25Index:
        """Retrieve in-memory student index or load from disk cache."""
        if student_id in self._student_indices:
            return self._student_indices[student_id]

        file_path = self._get_student_file(student_id)
        if file_path.exists():
            try:
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
                    index = StudentBM25Index(student_id, k1=self.settings.k1, b=self.settings.b)
                    index.chunks = data.get("chunks", [])
                    index.tokenized_corpus = data.get("tokenized_corpus", [])
                    index.rebuild()
                    self._student_indices[student_id] = index
                    logger.debug(
                        "Loaded BM25 index for student %s (%d chunks)",
                        student_id,
                        len(index.chunks),
                    )
                    return index
            except Exception as exc:
                logger.warning(
                    "Failed to load BM25 index file %s: %s; starting fresh", file_path, exc
                )

        index = StudentBM25Index(student_id, k1=self.settings.k1, b=self.settings.b)
        self._student_indices[student_id] = index
        return index

    def _persist_student_index(self, student_id: str) -> None:
        """Persist student index state to disk."""
        index = self._student_indices.get(student_id)
        if not index:
            return
        file_path = self._get_student_file(student_id)
        if not index.chunks:
            file_path.unlink(missing_ok=True)
            return

        try:
            with open(file_path, "wb") as f:
                pickle.dump(
                    {
                        "student_id": student_id,
                        "chunks": index.chunks,
                        "tokenized_corpus": index.tokenized_corpus,
                    },
                    f,
                )
        except Exception as exc:
            logger.error("Failed to persist BM25 index for student %s: %s", student_id, exc)

    def add_document(self, doc_id: str, student_id: str, chunks: list[dict[str, Any]]) -> int:
        """Index chunks into the student's BM25 index and save to disk."""
        if not self.settings.enabled or not chunks:
            return 0
        index = self._get_or_load_index(student_id)
        index.add_chunks(doc_id, chunks)
        self._persist_student_index(student_id)
        logger.info(
            "BM25 indexed %d chunks for document %s (student=%s)",
            len(chunks),
            doc_id,
            student_id,
        )
        return len(chunks)

    def delete_document(self, doc_id: str, student_id: str) -> int:
        """Remove document chunks from student's BM25 index and save to disk."""
        index = self._get_or_load_index(student_id)
        removed = index.remove_document(doc_id)
        self._persist_student_index(student_id)
        return removed

    def search(self, query: str, student_id: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Search student's BM25 index with strict tenant isolation."""
        if not self.settings.enabled or not query or not student_id:
            return []
        k = top_k or self.settings.candidate_count
        index = self._get_or_load_index(student_id)
        return index.search(query, top_k=k)

    def count(self, student_id: str) -> int:
        index = self._get_or_load_index(student_id)
        return len(index.chunks)
