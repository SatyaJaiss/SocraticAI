# SocraticAI — Educational Evaluation & Benchmarking

## Overview

Milestone 3 establishes a standardized, reproducible educational evaluation framework to empirically measure the pedagogical capabilities of SocraticAI. The benchmark evaluates tutoring strategy selection, concept mastery tracking, multi-turn Socratic scaffolding, misconception diagnosis, and prerequisite DAG resolution.

---

## 1. Curated Benchmark Dataset

The benchmark is defined in `apps/backend/tests/fixtures/educational_evaluation_dataset.json`. It comprises verified educational ground-truth items across 6 categories:

### 1.1 Dataset Composition

| Category | Cases | Description |
| :--- | :---: | :--- |
| `concept_mastery_cases` | 2 | Multi-turn sequence verifying asymptotic confidence $C(n)$ and state transitions from `not_attempted` to `mastered` ($n \ge 3$, score $\ge 0.80$, confidence $\ge 0.70$). |
| `socratic_dialogue_cases` | 2 | Step-by-step problem-solving scenarios validating progressive hint escalation (Tier 1 $\rightarrow$ 4) and stuck student detection (`is_stuck=True`). |
| `misconception_cases` | 3 | Common student misunderstandings (e.g. high variance vs high bias in overfitting, correlation implying causation, p-value misconceptions). |
| `numerical_tolerance_cases` | 3 | Numerical calculation tests with acceptable tolerances (e.g., $1.618$ golden ratio with relative error $\le 0.01$). |
| `subjective_rubric_cases` | 1 | Open-ended conceptual explanations evaluated against weighted criteria. |
| `prerequisite_graph_cases` | 1 | Curated concept dependency DAG (`linear_algebra` $\rightarrow$ `matrices` $\rightarrow$ `eigenvalues`) with student mastery states verifying gap detection. |

---

## 2. Evaluation Metrics and Verification Results

### 2.1 Numerical Assessment Tolerance Accuracy
- **Target**: Ensure minor student rounding errors do not trigger false negatives, while out-of-tolerance answers are rejected.
- **Result**: **100% Accuracy**. Correct answers within 1% relative error or absolute tolerance pass deterministically; values outside tolerance fail.

### 2.2 Socratic Dialogue Bounded Turns & Escalation
- **Target**: Verify hints escalate monotonically without answer leakage, and `is_stuck=True` flags at Tier 3/4 or $\ge 3$ consecutive errors.
- **Result**: **100% Compliance**. All hint ladders progress strictly from Conceptual $\rightarrow$ Explicit $\rightarrow$ Partial $\rightarrow$ Full Walkthrough.

### 2.3 Misconception Detection & Deduplication
- **Target**: Accurately diagnose known conceptual traps from student submissions, log them with unique IDs, and avoid duplicate entries.
- **Result**: **100% Pass Rate**. Detected misconceptions match ground truth; existing misconceptions are not duplicated.

### 2.4 Prerequisite DAG Resolution
- **Target**: Prevent forward curriculum recommendations when prerequisite concepts are unmastered.
- **Result**: **100% Correctness**. The recommendation engine accurately flags unmet prerequisites and prioritizes foundational topics.

---

## 3. Automated Test Suite Summary

All 30 unit and integration tests written for Milestone 3 run fully offline without paid LLM API calls:

| Test Module | Tests | Status | Focus |
| :--- | :---: | :---: | :--- |
| `test_concept_mastery.py` | 5 | PASSED | EMA smoothing, asymptotic confidence, state transitions, prerequisites. |
| `test_socratic_dialogue.py` | 3 | PASSED | Step advancement, hint escalation, stuck student flag. |
| `test_misconception_detection.py` | 5 | PASSED | Keyword/LLM detection, deduplication, resolution status. |
| `test_adaptive_quiz.py` | 4 | PASSED | MCQ, True/False, numerical tolerances, rubric grading. |
| `test_prerequisite_recommendations.py` | 4 | PASSED | Graph traversal, gap prioritization, legacy schema conversion. |
| `test_adaptive_tutoring_workflow.py` | 3 | PASSED | LangGraph teacher, evaluation, and recommendation routing. |
| `test_learning_analytics_api.py` | 6 | PASSED | Progress, mastery, recommendation, and Socratic REST endpoints. |

**Total Regression Test Suite**: **248 passed, 0 failed, 100% pass rate**.
