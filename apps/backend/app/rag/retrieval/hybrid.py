"""Hybrid retrieval combining dense vector search and BM25 lexical search via Reciprocal Rank Fusion (RRF).

Design rationale
----------------
* Merges semantic understanding from dense embeddings with exact keyword precision
  from BM25 lexical indexing.
* Reciprocal Rank Fusion (RRF) combines ranked lists without requiring score scale
  calibration:
      RRF_score(d) = Σ [ 1 / (k + rank_i(d)) ]
* Provides independent dense-only and lexical-only baselines for rigorous benchmarking.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import HybridRetrievalSettings
from app.schemas.domain import RetrievedChunk

if TYPE_CHECKING:
    from app.rag.retrieval.bm25 import BM25Index
    from app.rag.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


def compute_rrf_score(ranks: list[int], k: int = 60) -> float:
    """Calculate the Reciprocal Rank Fusion score across multiple ranking systems.

    ranks is a list of 1-based ranks (e.g. [1, 3] if item was rank 1 in dense and rank 3 in BM25).
    """
    return sum(1.0 / (k + r) for r in ranks)


class HybridRetriever:
    """Orchestrates multi-modal candidate retrieval and RRF score fusion."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        settings: HybridRetrievalSettings,
    ) -> None:
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.settings = settings

    def _chunk_identity(self, chunk: RetrievedChunk) -> str:
        """Derive a stable, collision-free identity key for deduplicating candidates across modalities."""
        norm_content = " ".join(chunk.content.strip().split())
        source = chunk.source or chunk.document_id or "unknown"
        page = chunk.page or 1
        return f"{source}::p{page}::{hash(norm_content)}"

    def search(
        self,
        query: str,
        student_id: str | None = None,
        top_k: int | None = None,
        *,
        mode: str = "hybrid",  # "hybrid", "dense", "bm25"
    ) -> list[RetrievedChunk]:
        """Perform candidate retrieval according to configured mode.

        * mode='dense': Dense vector search only.
        * mode='bm25': BM25 lexical search only.
        * mode='hybrid': Dense + BM25 merged with Reciprocal Rank Fusion.
        """
        final_k = top_k or self.settings.final_top_k

        # 1. Dense Baseline
        if mode == "dense" or not self.settings.enabled:
            return self.vector_store.search(query, top_k=final_k, student_id=student_id)

        # 2. BM25 Baseline
        if mode == "bm25":
            if not student_id:
                return []
            return self.bm25_index.search(query, student_id=student_id, top_k=final_k)

        # 3. Hybrid Fusion Mode (Dense + BM25 + RRF)
        dense_k = self.settings.dense_candidates
        bm25_k = self.settings.bm25_candidates
        rrf_k = self.settings.rrf_k

        dense_candidates = self.vector_store.search(query, top_k=dense_k, student_id=student_id)

        bm25_candidates = (
            self.bm25_index.search(query, student_id=student_id, top_k=bm25_k) if student_id else []
        )

        # Map identity -> (chunk, [rank_dense, rank_bm25])
        candidate_map: dict[str, dict] = {}

        for rank, chunk in enumerate(dense_candidates, start=1):
            cid = self._chunk_identity(chunk)
            candidate_map[cid] = {
                "chunk": chunk,
                "dense_rank": rank,
                "bm25_rank": None,
                "dense_score": chunk.score,
                "bm25_score": 0.0,
            }

        for rank, chunk in enumerate(bm25_candidates, start=1):
            cid = self._chunk_identity(chunk)
            if cid in candidate_map:
                candidate_map[cid]["bm25_rank"] = rank
                candidate_map[cid]["bm25_score"] = chunk.bm25_score or chunk.score
            else:
                candidate_map[cid] = {
                    "chunk": chunk,
                    "dense_rank": None,
                    "bm25_rank": rank,
                    "dense_score": 0.0,
                    "bm25_score": chunk.bm25_score or chunk.score,
                }

        # Calculate RRF scores and assemble unified candidates
        fused_candidates: list[RetrievedChunk] = []

        for _cid, entry in candidate_map.items():
            ranks: list[int] = []
            if entry["dense_rank"] is not None:
                ranks.append(entry["dense_rank"])
            if entry["bm25_rank"] is not None:
                ranks.append(entry["bm25_rank"])

            rrf_score = compute_rrf_score(ranks, k=rrf_k)
            chunk: RetrievedChunk = entry["chunk"]

            # Populate detailed diagnostic scores
            chunk.rrf_score = round(rrf_score, 6)
            chunk.dense_score = entry["dense_score"]
            chunk.bm25_score = entry["bm25_score"]
            # Set primary score to rrf_score
            chunk.score = round(rrf_score, 6)

            fused_candidates.append(chunk)

        # Sort by fused RRF score descending
        fused_candidates.sort(key=lambda c: c.score, reverse=True)

        logger.debug(
            "Hybrid RRF fused %d dense + %d bm25 -> %d unique candidates (top_k=%d)",
            len(dense_candidates),
            len(bm25_candidates),
            len(fused_candidates),
            final_k,
        )
        return fused_candidates[:final_k]
