"""Information retrieval and context quality evaluation metrics."""

from __future__ import annotations

import math
from typing import Any


def hit_rate_at_k(retrieved_ids: list[str], ground_truth_ids: list[str], k: int = 4) -> float:
    """Return 1.0 if at least one ground truth ID appears in top-k, else 0.0."""
    if not ground_truth_ids:
        # Negative example: true hit if nothing retrieved or negative query
        return 1.0 if not retrieved_ids else 0.0
    top_k_set = set(retrieved_ids[:k])
    return 1.0 if any(gt in top_k_set for gt in ground_truth_ids) else 0.0


def recall_at_k(retrieved_ids: list[str], ground_truth_ids: list[str], k: int = 4) -> float:
    """Proportion of relevant items retrieved in top-k."""
    if not ground_truth_ids:
        return 1.0
    top_k_set = set(retrieved_ids[:k])
    hits = sum(1 for gt in ground_truth_ids if gt in top_k_set)
    return hits / len(ground_truth_ids)


def precision_at_k(retrieved_ids: list[str], ground_truth_ids: list[str], k: int = 4) -> float:
    """Proportion of top-k retrieved items that are relevant."""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    gt_set = set(ground_truth_ids)
    hits = sum(1 for r in top_k if r in gt_set)
    return hits / len(top_k)


def mrr(retrieved_ids: list[str], ground_truth_ids: list[str]) -> float:
    """Mean Reciprocal Rank: reciprocal of the rank of the first relevant item."""
    if not ground_truth_ids:
        return 1.0
    gt_set = set(ground_truth_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in gt_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], ground_truth_ids: list[str], k: int = 4) -> float:
    """Normalized Discounted Cumulative Gain at rank k."""
    if not ground_truth_ids:
        return 1.0
    gt_set = set(ground_truth_ids)
    top_k = retrieved_ids[:k]

    dcg = 0.0
    for i, rid in enumerate(top_k):
        rel = 1.0 if rid in gt_set else 0.0
        dcg += rel / math.log2(i + 2)

    # Ideal DCG
    ideal_hits = min(len(ground_truth_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def evaluate_retrieval_batch(
    retrieved_results: list[list[str]],
    ground_truth_batch: list[list[str]],
    k: int = 4,
) -> dict[str, float]:
    """Calculate average IR metrics across a dataset batch."""
    n = len(ground_truth_batch)
    if n == 0:
        return {"recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0, "hit_rate": 0.0}

    recalls = [
        recall_at_k(ret, gt, k=k)
        for ret, gt in zip(retrieved_results, ground_truth_batch, strict=False)
    ]
    precisions = [
        precision_at_k(ret, gt, k=k)
        for ret, gt in zip(retrieved_results, ground_truth_batch, strict=False)
    ]
    mrrs = [mrr(ret, gt) for ret, gt in zip(retrieved_results, ground_truth_batch, strict=False)]
    ndcgs = [
        ndcg_at_k(ret, gt, k=k)
        for ret, gt in zip(retrieved_results, ground_truth_batch, strict=False)
    ]
    hit_rates = [
        hit_rate_at_k(ret, gt, k=k)
        for ret, gt in zip(retrieved_results, ground_truth_batch, strict=False)
    ]

    return {
        f"recall@{k}": round(sum(recalls) / n, 4),
        f"precision@{k}": round(sum(precisions) / n, 4),
        "mrr": round(sum(mrrs) / n, 4),
        f"ndcg@{k}": round(sum(ndcgs) / n, 4),
        f"hit_rate@{k}": round(sum(hit_rates) / n, 4),
    }


def context_quality_metrics(
    retrieved_chunks: list[dict[str, Any]],
    relevant_chunk_ids: list[str],
) -> dict[str, float]:
    """Measure context precision, duplicate rate, and irrelevant passage rate."""
    if not retrieved_chunks:
        return {
            "context_precision": 0.0,
            "context_recall": 0.0,
            "duplicate_rate": 0.0,
            "irrelevant_rate": 0.0,
        }

    total = len(retrieved_chunks)
    rel_set = set(relevant_chunk_ids)

    # Duplicates by content hash or text
    seen_hashes = set()
    dup_count = 0
    relevant_count = 0

    for c in retrieved_chunks:
        h = c.get("content_hash") or hash(c.get("content", ""))
        if h in seen_hashes:
            dup_count += 1
        else:
            seen_hashes.add(h)

        cid = c.get("chunk_id") or ""
        if cid in rel_set:
            relevant_count += 1

    precision = relevant_count / max(total, 1)
    recall = relevant_count / max(len(rel_set), 1) if rel_set else 1.0
    irrelevant_count = total - relevant_count

    return {
        "context_precision": round(precision, 4),
        "context_recall": round(min(recall, 1.0), 4),
        "duplicate_rate": round(dup_count / max(total, 1), 4),
        "irrelevant_rate": round(irrelevant_count / max(total, 1), 4),
    }
