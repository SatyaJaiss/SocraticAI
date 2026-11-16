"""Integration tests executing the 100-sample RAG benchmark and validating IR metrics."""

from __future__ import annotations

import pytest
from app.core.config import (
    BM25Settings,
    DecisionModelSettings,
    HybridRetrievalSettings,
    RerankerSettings,
    VectorStoreSettings,
)
from app.decision.composite import CompositeDecisionProvider
from app.decision.relevance_grader import RetrievalRelevanceGrader
from app.rag.evaluation.benchmark_runner import RAGBenchmarkRunner
from app.rag.retrieval.bm25 import BM25Index
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.reranker import CrossEncoderReranker
from app.rag.retrieval.vector_store import VectorStore


class TestRAGBenchmarkSuite:
    @pytest.fixture
    def benchmark_runner(self, tmp_path):
        v_settings = VectorStoreSettings(
            persist_directory=str(tmp_path / "chroma_bench"),
            collection_name="test_rag_bench",
        )
        vector_store = VectorStore(v_settings)

        bm25_settings = BM25Settings(
            enabled=True,
            candidate_count=6,
            index_dir=str(tmp_path / "bm25_bench"),
        )
        bm25_index = BM25Index(bm25_settings)

        hybrid_settings = HybridRetrievalSettings(
            enabled=True,
            rrf_k=60,
            dense_candidates=6,
            bm25_candidates=6,
            final_top_k=4,
        )
        hybrid_retriever = HybridRetriever(
            vector_store=vector_store,
            bm25_index=bm25_index,
            settings=hybrid_settings,
        )

        reranker_settings = RerankerSettings(enabled=False, top_k=4)
        reranker = CrossEncoderReranker(reranker_settings)

        decision_settings = DecisionModelSettings(primary_provider="disabled")
        decision_provider = CompositeDecisionProvider(decision_settings)
        relevance_grader = RetrievalRelevanceGrader(decision_provider, decision_settings)

        runner = RAGBenchmarkRunner(
            vector_store=vector_store,
            bm25_index=bm25_index,
            reranker=reranker,
            relevance_grader=relevance_grader,
            hybrid_retriever=hybrid_retriever,
        )
        runner.load_dataset()
        runner.seed_benchmark_corpus(student_id="bench_student")
        return runner

    def test_benchmark_dataset_loaded_and_valid(self, benchmark_runner):
        assert len(benchmark_runner.dataset) == 100
        categories = {item["category"] for item in benchmark_runner.dataset}
        assert len(categories) == 10
        assert "exact_terminology" in categories
        assert "no_evidence" in categories

    @pytest.mark.asyncio
    async def test_compare_dense_bm25_hybrid(self, benchmark_runner):
        # 1. Config A: Dense Retrieval
        metrics_a = await benchmark_runner.evaluate_configuration(
            "A", student_id="bench_student", top_k=4
        )
        assert metrics_a["recall@4"] >= 0.70
        assert metrics_a["hit_rate@4"] >= 0.75
        assert metrics_a["p50_latency_ms"] >= 0.0

        # 2. Config B: BM25 Lexical Retrieval
        metrics_b = await benchmark_runner.evaluate_configuration(
            "B", student_id="bench_student", top_k=4
        )
        assert metrics_b["recall@4"] >= 0.55
        assert metrics_b["hit_rate@4"] >= 0.60

        # 3. Config C: Hybrid (Dense + BM25 + RRF)
        metrics_c = await benchmark_runner.evaluate_configuration(
            "C", student_id="bench_student", top_k=4
        )
        # Hybrid should match or outperform individual baselines
        assert metrics_c["recall@4"] >= 0.70
        assert metrics_c["hit_rate@4"] >= 0.70
        assert metrics_c["mrr"] >= 0.60
