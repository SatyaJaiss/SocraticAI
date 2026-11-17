"""Adversarial security evaluation module measuring precision, recall, and error rates."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.guardrails.execution_rails import ExecutionRails
from app.guardrails.input_rails import InputRails
from app.guardrails.output_rails import OutputRails
from app.guardrails.retrieval_rails import RetrievalRails
from app.security.pii.service import PIIProtectionService

logger = logging.getLogger(__name__)


@dataclass
class SecurityMetricsSummary:
    """Statistical confusion matrix and performance rates for security guardrails."""

    category: str
    total_samples: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    false_positive_rate: float
    false_negative_rate: float
    accuracy: float


class SecurityEvaluator:
    """Runs automated security evaluations against adversarial test datasets."""

    def __init__(self) -> None:
        self.input_rails = InputRails()
        self.retrieval_rails = RetrievalRails()
        self.execution_rails = ExecutionRails()
        self.output_rails = OutputRails()
        self.pii_service = PIIProtectionService()

    def evaluate_dataset(self, dataset_path: str | Path) -> dict[str, SecurityMetricsSummary]:
        """Execute all adversarial categories in dataset and compute performance rates."""
        path = Path(dataset_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        results: dict[str, SecurityMetricsSummary] = {}

        # 1. Prompt Injection Evaluation
        if "prompt_injections" in data:
            results["prompt_injections"] = self._eval_prompt_injections(data["prompt_injections"])

        # 2. Retrieval Injection Evaluation
        if "malicious_retrieval_passages" in data:
            results["retrieval_injections"] = self._eval_retrieval_passages(
                data["malicious_retrieval_passages"]
            )

        # 3. Cross-Student Access Evaluation
        if "cross_student_access_cases" in data:
            results["cross_student_access"] = self._eval_cross_student(
                data["cross_student_access_cases"]
            )

        # 4. Unauthorized Tools Evaluation
        if "unauthorized_tools" in data:
            results["unauthorized_tools"] = self._eval_unauthorized_tools(
                data["unauthorized_tools"]
            )

        # 5. Unsafe Output Evaluation
        if "unsafe_outputs" in data:
            results["unsafe_outputs"] = self._eval_unsafe_outputs(data["unsafe_outputs"])

        # 6. PII Redaction Evaluation
        if "pii_leakage_cases" in data:
            results["pii_redaction"] = self._eval_pii_cases(data["pii_leakage_cases"])

        return results

    def _eval_prompt_injections(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            res = self.input_rails.validate(item["prompt"])
            blocked = not res.allowed
            expected = item["expected_blocked"]
            if expected and blocked:
                tp += 1
            elif not expected and blocked:
                fp += 1
            elif not expected and not blocked:
                tn += 1
            elif expected and not blocked:
                fn += 1
        return self._calc_summary("prompt_injections", len(cases), tp, fp, tn, fn)

    def _eval_retrieval_passages(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            res = self.retrieval_rails.validate_passage(item["content"])
            blocked = not res.allowed
            expected = item["expected_blocked"]
            if expected and blocked:
                tp += 1
            elif not expected and blocked:
                fp += 1
            elif not expected and not blocked:
                tn += 1
            elif expected and not blocked:
                fn += 1
        return self._calc_summary("retrieval_injections", len(cases), tp, fp, tn, fn)

    def _eval_cross_student(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            res = self.execution_rails.validate_tool_invocation(
                tool_name=item["tool_name"],
                tool_args=item["tool_args"],
                student_id=item["calling_student_id"],
            )
            blocked = not res.allowed
            expected = item["expected_blocked"]
            if expected and blocked:
                tp += 1
            elif not expected and blocked:
                fp += 1
            elif not expected and not blocked:
                tn += 1
            elif expected and not blocked:
                fn += 1
        return self._calc_summary("cross_student_access", len(cases), tp, fp, tn, fn)

    def _eval_unauthorized_tools(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            res = self.execution_rails.validate_tool_invocation(
                tool_name=item["tool_name"],
                tool_args=item["tool_args"],
                student_id=item["calling_student_id"],
            )
            blocked = not res.allowed
            expected = item["expected_blocked"]
            if expected and blocked:
                tp += 1
            elif not expected and blocked:
                fp += 1
            elif not expected and not blocked:
                tn += 1
            elif expected and not blocked:
                fn += 1
        return self._calc_summary("unauthorized_tools", len(cases), tp, fp, tn, fn)

    def _eval_unsafe_outputs(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            res = self.output_rails.validate(item["response"])
            blocked = not res.allowed
            expected = item["expected_blocked"]
            if expected and blocked:
                tp += 1
            elif not expected and blocked:
                fp += 1
            elif not expected and not blocked:
                tn += 1
            elif expected and not blocked:
                fn += 1
        return self._calc_summary("unsafe_outputs", len(cases), tp, fp, tn, fn)

    def _eval_pii_cases(self, cases: list[dict[str, Any]]) -> SecurityMetricsSummary:
        tp = fp = tn = fn = 0
        for item in cases:
            _, _, entities = self.pii_service.redact_user_input(
                item["input"], student_id="eval_student"
            )
            detected = len(entities) > 0
            expected = item["expected_redacted"]
            if expected and detected:
                tp += 1
            elif not expected and detected:
                fp += 1
            elif not expected and not detected:
                tn += 1
            elif expected and not detected:
                fn += 1
        return self._calc_summary("pii_redaction", len(cases), tp, fp, tn, fn)

    def _calc_summary(
        self,
        category: str,
        total: int,
        tp: int,
        fp: int,
        tn: int,
        fn: int,
    ) -> SecurityMetricsSummary:
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        accuracy = (tp + tn) / total if total > 0 else 1.0

        return SecurityMetricsSummary(
            category=category,
            total_samples=total,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4),
            accuracy=round(accuracy, 4),
        )
