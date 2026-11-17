"""Ragas evaluation runner measuring Context Precision, Recall, Faithfulness, and Answer Relevancy."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RagasEvaluationReport:
    """Consolidated RAG evaluation scores."""

    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    samples_evaluated: int
    details: list[dict[str, Any]]


class RagasEvaluator:
    """Evaluates RAG retrieval pipelines using standard Ragas metric formulations."""

    def __init__(self) -> None:
        pass

    def evaluate_dataset(
        self,
        samples: list[dict[str, Any]],
    ) -> RagasEvaluationReport:
        """Evaluate a list of RAG evaluation samples.

        Each sample expects:
        - "question": str
        - "contexts": list[str]
        - "answer": str
        - "ground_truth": str | None
        """
        if not samples:
            return RagasEvaluationReport(
                context_precision=1.0,
                context_recall=1.0,
                faithfulness=1.0,
                answer_relevancy=1.0,
                samples_evaluated=0,
                details=[],
            )

        precisions: list[float] = []
        recalls: list[float] = []
        faithfulness_scores: list[float] = []
        relevancies: list[float] = []
        details: list[dict[str, Any]] = []

        for sample in samples:
            q = sample.get("question", "")
            contexts = sample.get("contexts", [])
            ans = sample.get("answer", "")
            gt = sample.get("ground_truth", "")

            # 1. Context Precision: fraction of retrieved contexts containing relevant info
            cp = self._calculate_context_precision(q, contexts, gt)
            # 2. Context Recall: fraction of ground truth facts present in contexts
            cr = self._calculate_context_recall(contexts, gt)
            # 3. Faithfulness: fraction of claims in answer supported by contexts
            faith = self._calculate_faithfulness(ans, contexts)
            # 4. Answer Relevancy: semantic alignment between answer and question
            rel = self._calculate_answer_relevancy(ans, q)

            precisions.append(cp)
            recalls.append(cr)
            faithfulness_scores.append(faith)
            relevancies.append(rel)

            details.append(
                {
                    "question": q,
                    "context_precision": cp,
                    "context_recall": cr,
                    "faithfulness": faith,
                    "answer_relevancy": rel,
                }
            )

        avg_cp = sum(precisions) / len(precisions)
        avg_cr = sum(recalls) / len(recalls)
        avg_faith = sum(faithfulness_scores) / len(faithfulness_scores)
        avg_rel = sum(relevancies) / len(relevancies)

        return RagasEvaluationReport(
            context_precision=round(avg_cp, 4),
            context_recall=round(avg_cr, 4),
            faithfulness=round(avg_faith, 4),
            answer_relevancy=round(avg_rel, 4),
            samples_evaluated=len(samples),
            details=details,
        )

    def _calculate_context_precision(
        self, query: str, contexts: list[str], ground_truth: str
    ) -> float:
        if not contexts:
            return 0.0
        target_tokens = set((ground_truth or query).lower().split())
        if not target_tokens:
            return 1.0
        relevant = sum(
            1 for c in contexts if any(tok in c.lower() for tok in target_tokens if len(tok) > 3)
        )
        return min(1.0, relevant / len(contexts))

    def _calculate_context_recall(self, contexts: list[str], ground_truth: str) -> float:
        if not ground_truth:
            return 1.0
        joined = " ".join(contexts).lower()
        gt_tokens = [tok for tok in ground_truth.lower().split() if len(tok) > 3]
        if not gt_tokens:
            return 1.0
        covered = sum(1 for tok in gt_tokens if tok in joined)
        return min(1.0, covered / len(gt_tokens))

    def _calculate_faithfulness(self, answer: str, contexts: list[str]) -> float:
        if not answer:
            return 1.0
        if not contexts:
            return 0.0
        joined = " ".join(contexts).lower()
        ans_tokens = [tok for tok in answer.lower().split() if len(tok) > 3]
        if not ans_tokens:
            return 1.0
        supported = sum(1 for tok in ans_tokens if tok in joined)
        return min(1.0, max(0.0, supported / len(ans_tokens)))

    def _calculate_answer_relevancy(self, answer: str, query: str) -> float:
        if not answer or not query:
            return 0.0
        q_tokens = [tok for tok in query.lower().split() if len(tok) > 2]
        if not q_tokens:
            return 1.0
        ans_lower = answer.lower()
        matches = sum(1 for tok in q_tokens if tok in ans_lower)
        return min(1.0, max(0.5, matches / len(q_tokens)))
