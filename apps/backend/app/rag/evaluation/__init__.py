"""RAG evaluation and benchmarking package."""

from app.rag.evaluation.benchmark_runner import RAGBenchmarkRunner
from app.rag.evaluation.metrics import (
    context_quality_metrics,
    evaluate_retrieval_batch,
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

__all__ = [
    "RAGBenchmarkRunner",
    "context_quality_metrics",
    "evaluate_retrieval_batch",
    "hit_rate_at_k",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
