"""Adaptive quiz generation and deterministic evaluation engine."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import AssessmentSettings
from app.llm.clients.client import LLMClient
from app.schemas.domain import (
    QuizQuestion,
    SubjectiveGradingResult,
    SubjectiveRubric,
)
from app.schemas.enums import QuestionType

logger = logging.getLogger(__name__)


class AdaptiveQuizEngine:
    """Handles adaptive question generation and deterministic & rubric-based grading."""

    def __init__(
        self,
        assessment_settings: AssessmentSettings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = assessment_settings or AssessmentSettings()
        self.llm = llm

    # ------------------------------------------------------------- Grading -- #

    def grade_question(
        self,
        question: QuizQuestion,
        student_answer: str | None,
    ) -> tuple[bool, float, str, dict[str, Any]]:
        """Grade a single quiz question.

        Returns: (is_correct: bool, score_earned: float, feedback: str, metadata: dict)
        """
        if student_answer is None or not student_answer.strip():
            return False, 0.0, "No answer submitted.", {"type": question.type.value, "empty": True}

        submitted = student_answer.strip()
        points = float(question.points)

        # 1. Objective: MCQ
        if question.type == QuestionType.MCQ:
            is_ok = self._evaluate_mcq(question, submitted)
            earned = points if is_ok else 0.0
            feedback = (
                "Correct!"
                if is_ok
                else f"Incorrect. The correct answer was {question.correct_answer}."
            )
            return is_ok, earned, feedback, {"type": "mcq"}

        # 2. Objective: True / False
        if question.type == QuestionType.TRUE_FALSE:
            is_ok = self._evaluate_true_false(question.correct_answer, submitted)
            earned = points if is_ok else 0.0
            feedback = (
                "Correct!"
                if is_ok
                else f"Incorrect. The correct answer was {question.correct_answer}."
            )
            return is_ok, earned, feedback, {"type": "true_false"}

        # 3. Objective: Numerical
        if question.type == QuestionType.NUMERICAL:
            is_ok, diff = self._evaluate_numerical(
                question.correct_answer,
                submitted,
                rel_tol=question.numerical_tolerance or self.settings.numerical_relative_tolerance,
                abs_tol=self.settings.numerical_absolute_tolerance,
            )
            earned = points if is_ok else 0.0
            feedback = (
                "Correct calculation!"
                if is_ok
                else f"Incorrect. Expected ~{question.correct_answer}."
            )
            return is_ok, earned, feedback, {"type": "numerical", "delta": diff}

        # 4. Subjective / Conceptual / Application / Scenario
        rubric_res = self.grade_subjective_rubric(question, submitted)
        earned = round(points * rubric_res.score, 3)
        return rubric_res.passed, earned, rubric_res.feedback, rubric_res.model_dump()

    def _evaluate_mcq(self, question: QuizQuestion, submitted: str) -> bool:
        """Evaluate multiple-choice response deterministically."""
        sub = submitted.strip().lower()
        correct = question.correct_answer.strip().lower()

        # Direct string equality
        if sub == correct:
            return True

        # Check option letter index (e.g. "A", "B", "C", "D")
        options = [opt.strip().lower() for opt in question.options] if question.options else []
        letter_match = re.match(r"^([a-d])[\)\.\:\s]?", sub)
        if letter_match and options:
            letter_idx = ord(letter_match.group(1)) - ord("a")
            if 0 <= letter_idx < len(options):
                chosen_opt = options[letter_idx]
                return chosen_opt == correct or correct in (
                    chr(ord("a") + letter_idx),
                    chr(ord("A") + letter_idx),
                )

        # Check if student typed the exact option text that matches the correct answer
        for opt in options:
            if opt == sub and opt == correct:
                return True

        return False

    def _evaluate_true_false(self, correct: str, submitted: str) -> bool:
        """Deterministic True/False normalization and check."""
        true_aliases = {"true", "t", "1", "yes", "correct"}
        false_aliases = {"false", "f", "0", "no", "incorrect"}

        s = submitted.strip().lower()
        c = correct.strip().lower()

        c_bool = c in true_aliases
        s_bool = s in true_aliases
        s_is_false = s in false_aliases

        if not (s_bool or s_is_false):
            return False  # Unrecognized input

        return c_bool == s_bool

    def _evaluate_numerical(
        self,
        correct_str: str,
        submitted_str: str,
        rel_tol: float = 0.01,
        abs_tol: float = 1e-4,
    ) -> tuple[bool, float]:
        """Extract float numbers and evaluate with relative and absolute tolerances."""
        c_val = self._parse_number(correct_str)
        s_val = self._parse_number(submitted_str)

        if c_val is None or s_val is None:
            return False, float("inf")

        diff = abs(s_val - c_val)
        denom = max(abs(c_val), 1e-9)
        rel_diff = diff / denom

        is_correct = (rel_diff <= rel_tol) or (diff <= abs_tol)
        return is_correct, diff

    @staticmethod
    def _parse_number(text: str) -> float | None:
        """Extract first numeric representation from string (supports scientific notation, decimals, negatives)."""
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text.strip())
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None

    def grade_subjective_rubric(
        self,
        question: QuizQuestion,
        submitted: str,
    ) -> SubjectiveGradingResult:
        """Evaluate subjective answer using structured rubric criteria."""
        rubric = question.rubric or SubjectiveRubric()
        sub_text = submitted.strip()
        if not sub_text:
            return SubjectiveGradingResult(
                score=0.0,
                passed=False,
                conceptual_score=0.0,
                reasoning_score=0.0,
                completeness_score=0.0,
                missing_key_points=rubric.key_points,
                feedback="No answer provided.",
                detected_misconceptions=[],
            )

        # If LLM is available, evaluate with rubric
        if self.llm is not None:
            prompt = (
                "You are an expert grading rubric evaluator.\n"
                f"Question: {question.question}\n"
                f"Topic: {question.topic}\n"
                f"Model Answer: {question.correct_answer}\n"
                f"Key Points Expected: {', '.join(rubric.key_points) if rubric.key_points else 'Accurate explanation'}\n"
                f"Student Answer: {sub_text}\n\n"
                "Grade using these weights:\n"
                f"- Conceptual Correctness (Weight: {rubric.conceptual_correctness_weight})\n"
                f"- Reasoning & Justification (Weight: {rubric.reasoning_weight})\n"
                f"- Completeness (Weight: {rubric.completeness_weight})\n\n"
                "Return valid JSON matching this schema:\n"
                "{\n"
                '  "conceptual_score": <float 0.0-1.0>,\n'
                '  "reasoning_score": <float 0.0-1.0>,\n'
                '  "completeness_score": <float 0.0-1.0>,\n'
                '  "missing_key_points": [<string>],\n'
                '  "feedback": "<concise actionable feedback>",\n'
                '  "detected_misconceptions": [<string>]\n'
                "}"
            )
            try:
                result = self.llm.generate(prompt)
                raw = getattr(result, "content", str(result))
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    import json

                    data = json.loads(match.group(0))
                    c_score = float(data.get("conceptual_score", 0.7))
                    r_score = float(data.get("reasoning_score", 0.7))
                    comp_score = float(data.get("completeness_score", 0.7))
                    overall = round(
                        rubric.conceptual_correctness_weight * c_score
                        + rubric.reasoning_weight * r_score
                        + rubric.completeness_weight * comp_score,
                        3,
                    )
                    passed = overall >= self.settings.subjective_passing_score
                    return SubjectiveGradingResult(
                        score=overall,
                        passed=passed,
                        conceptual_score=c_score,
                        reasoning_score=r_score,
                        completeness_score=comp_score,
                        missing_key_points=data.get("missing_key_points", []),
                        feedback=data.get("feedback", "Good effort."),
                        detected_misconceptions=data.get("detected_misconceptions", []),
                    )
            except Exception as e:
                logger.warning(
                    f"LLM rubric grading failed: {e}; falling back to heuristic grading."
                )

        # Heuristic fallback grading
        words = sub_text.split()
        word_count = len(words)
        completeness = min(1.0, max(0.2, word_count / 15.0))
        conceptual = 0.8 if word_count >= 8 else 0.4
        reasoning = (
            0.75
            if any(
                k in sub_text.lower()
                for k in ["because", "therefore", "since", "due to", "thus", "leads to"]
            )
            else 0.5
        )

        overall = round(
            rubric.conceptual_correctness_weight * conceptual
            + rubric.reasoning_weight * reasoning
            + rubric.completeness_weight * completeness,
            3,
        )
        passed = overall >= self.settings.subjective_passing_score

        missing_pts = []
        for kp in rubric.key_points:
            if kp.lower() not in sub_text.lower():
                missing_pts.append(kp)

        return SubjectiveGradingResult(
            score=overall,
            passed=passed,
            conceptual_score=conceptual,
            reasoning_score=reasoning,
            completeness_score=completeness,
            missing_key_points=missing_pts,
            feedback="Your response demonstrates reasonable understanding of the core concepts."
            if passed
            else "Please provide more detail and explicit reasoning.",
            detected_misconceptions=[],
        )
