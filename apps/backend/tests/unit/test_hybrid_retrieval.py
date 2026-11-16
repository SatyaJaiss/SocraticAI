"""Unit tests for Hybrid retrieval and Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import HybridRetrievalSettings
from app.rag.retrieval.hybrid import HybridRetriever, compute_rrf_score
from app.schemas.domain import RetrievedChunk


class TestHybridRetriever:
    def test_compute_rrf_score(self):
        # Item ranked 1st in system 1 and 2nd in system 2 with k=60
        score = compute_rrf_score([1, 2], k=60)
        expected = (1.0 / 61.0) + (1.0 / 62.0)
        assert abs(score - expected) < 1e-6

    def test_hybrid_merging_and_deduplication(self):
        settings = HybridRetrievalSettings(
            enabled=True,
            rrf_k=60,
            dense_candidates=5,
            bm25_candidates=5,
            final_top_k=3,
        )
        mock_vector_store = MagicMock()
        mock_bm25 = MagicMock()

        # Dense candidates
        chunk_a = RetrievedChunk(
            content="Cellular respiration produces ATP.",
            source="bio.pdf",
            page=1,
            score=0.95,
            chunk_id="chunk_a",
            document_id="doc_bio",
        )
        chunk_b = RetrievedChunk(
            content="Glycolysis breaks down glucose.",
            source="bio.pdf",
            page=2,
            score=0.80,
            chunk_id="chunk_b",
            document_id="doc_bio",
        )
        mock_vector_store.search.return_value = [chunk_a, chunk_b]

        # BM25 candidates: chunk_b ranked 1st, chunk_c ranked 2nd
        chunk_c = RetrievedChunk(
            content="Krebs cycle generates NADH.",
            source="bio.pdf",
            page=3,
            score=0.90,
            chunk_id="chunk_c",
            document_id="doc_bio",
        )
        mock_bm25.search.return_value = [chunk_b, chunk_c]

        retriever = HybridRetriever(mock_vector_store, mock_bm25, settings)
        results = retriever.search("respiration glucose", student_id="student_1", top_k=3)

        assert len(results) == 3
        # chunk_b appeared in both dense (rank 2) and BM25 (rank 1), so its RRF score should be highest!
        # chunk_b RRF = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = ~0.0325
        # chunk_a RRF = 1/61 = ~0.01639
        # chunk_c RRF = 1/62 = ~0.01612
        assert results[0].chunk_id == "chunk_b"
        assert results[0].rrf_score > results[1].rrf_score
        assert results[0].dense_score == 0.80
        assert results[0].bm25_score > 0.0

    def test_dense_only_baseline_mode(self):
        settings = HybridRetrievalSettings(enabled=True)
        mock_vector_store = MagicMock()
        mock_bm25 = MagicMock()
        mock_vector_store.search.return_value = [
            RetrievedChunk(content="Dense only", source="d.txt", score=0.9)
        ]

        retriever = HybridRetriever(mock_vector_store, mock_bm25, settings)
        res = retriever.search("query", student_id="s1", mode="dense")
        assert len(res) == 1
        assert res[0].content == "Dense only"
        mock_bm25.search.assert_not_called()
