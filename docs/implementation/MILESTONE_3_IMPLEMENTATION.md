# SocraticAI — Milestone 3 Implementation Report

## Executive Summary

Milestone 3, **Adaptive Tutoring & Learning Intelligence**, transforms SocraticAI from a conversational RAG platform into an intelligent, adaptive educational system. This milestone introduces:

1. **Concept-Level Learning State & Evidence-Based Mastery Tracking**: Asymptotic confidence growth ($C(n) = 1.0 - e^{-0.45n}$), exponential moving average score smoothing ($\alpha = 0.30$), and state machine transitions (`not_attempted` $\rightarrow$ `attempted` / `partially_understood` $\rightarrow$ `mastered` / `needs_revision`).
2. **Socratic Dialogue & Guided Problem-Solving Engine**: Bounded multi-turn guided inquiries preventing direct answer leakage, reasoning evaluation, stuck detection, and a 4-tier progressive hint escalation ladder (Conceptual $\rightarrow$ Explicit Guidance $\rightarrow$ Partial Solution $\rightarrow$ Full Walkthrough).
3. **Misconception Detection & Tracking**: Rule-based heuristic and LLM-assisted diagnostic reasoning, deduplication, and resolution tracking.
4. **Adaptive Explanation Engine**: Multi-dimensional adaptation across 6 pedagogical modes (`beginner`, `intermediate`, `advanced`, `mathematical`, `intuitive`, `exam_oriented`).
5. **Adaptive Quiz Generation & Deterministic Evaluation**: Objective question grading (MCQ, True/False, Numerical with relative $\le 1.0\%$ and absolute tolerances) and rubric-based subjective scoring.
6. **Prerequisite-Aware Recommendations**: Relational SQLite DAG traversal identifying knowledge gaps, unsatisfied prerequisites, and next optimal concepts.
7. **Learning Analytics Service**: Separation of activity metrics, assessment metrics, mastery metrics, and normalized learning improvement score.
8. **LangGraph Workflow Integration**: Dynamic routing to `Routes.SOCRATIC` (`socratic` node) alongside `teach`, `quiz`, `evaluate`, and `recommend`.

All implementations maintain strict student isolation, layered conversation memory, hybrid RAG with citation verification, and offline test reliability.

---

## 1. Domain Schemas and Enums

### 1.1 Enums (`apps/backend/app/schemas/enums.py`)
- `TutoringStrategy`: `direct_instruction`, `socratic_questioning`, `guided_problem_solving`, `worked_example`, `inquiry_based`, `remedial_instruction`, `review`.
- `ExplanationMode`: `beginner`, `intermediate`, `advanced`, `mathematical`, `intuitive`, `exam_oriented`.
- `MasteryStatus`: `not_attempted`, `attempted`, `partially_understood`, `mastered`, `needs_revision`.
- `EvidenceType`: `quiz_submission`, `socratic_turn`, `practice_problem`, `self_assessment`, `teacher_observation`.
- `PrerequisiteRelation`: `requires`, `recommends`, `extends`, `part_of`.
- `QuestionType`: Expanded with `true_false`, `conceptual`, `application`, `scenario`.
- `DifficultyLevel`: Expanded with `expert`.

### 1.2 Domain Models (`apps/backend/app/schemas/domain.py`)
- `ConceptPrerequisiteSchema`: Models directed concept dependencies (`concept_id`, `prerequisite_concept_id`, `relation_type`).
- `LearningEvidenceSchema`: Individual learning interaction evidence with weights, scores, and context.
- `ConceptMasterySchema`: Complete mastery snapshot including `mastery_score`, `confidence`, `attempts_count`, `success_count`, `last_attempted_at`, and `status`.
- `StrategySelectionResult`: Strategy recommendation with rationale, mode, target concept, and prerequisite satisfaction flag.
- `SocraticTurnResponse`: Multi-turn response with `turn_type`, `step_index`, `total_steps`, `current_question`, `hint_level`, `is_stuck`, and `session_completed`.
- `SubjectiveRubric` & `SubjectiveGradingResult`: Criteria-based evaluation with score breakdowns and actionable feedback.
- `RecommendationWithPrerequisites`: Recommendation model containing prerequisite chain, status, and gap indicators.
- `LearningAnalyticsSummary`: Unified reporting model covering activity, assessments, mastery, misconceptions, and improvement score.

---

## 2. Database Models and Persistence

### 2.1 ORM Models (`apps/backend/app/models/orm.py`)
- `ConceptPrerequisite`: Stores the adjacency matrix of concepts in SQLite:
  - `(concept_id, prerequisite_concept_id)` compound primary key.
  - Foreign keys with `ondelete="CASCADE"`.
- `LearningEvidence`: Persistent evidence log:
  - `student_id`, `concept_id`, `evidence_type`, `score`, `weight`, `context_meta`, `created_at`.
- `ConceptMasteryRow`: Current concept mastery state for each student:
  - Unique constraint on `(student_id, concept_id)`.
  - Tracks `mastery_score`, `confidence`, `attempts_count`, `success_count`, `status`.
- `SocraticDialogueSession`: Persistent state machine for multi-turn Socratic problem-solving:
  - `session_id`, `student_id`, `concept_id`, `problem_statement`, `current_step`, `total_steps`, `hint_level`, `consecutive_mistakes`, `is_stuck`, `status`, `history_turns`.

---

## 3. Repositories

### 3.1 Mastery Repository (`apps/backend/app/repositories/mastery_repository.py`)
- **Evidence Ingestion**: Records evidence and automatically updates mastery score using exponential smoothing:
  $$\text{Score}_{t} = (1 - \alpha) \cdot \text{Score}_{t-1} + \alpha \cdot \text{NewScore}$$
- **Asymptotic Confidence Growth**:
  $$C(n) = 1.0 - e^{-0.45n}$$
  - $n=1 \implies C(1) \approx 0.362$
  - $n=2 \implies C(2) \approx 0.593$
  - $n=3 \implies C(3) \approx 0.741 \ge 0.70$
- **State Transition Logic**:
  - `mastered`: Requires $\text{attempts} \ge 3$, $\text{score} \ge 0.80$, $\text{confidence} \ge 0.70$.
  - `needs_revision`: If $\text{score} < 0.60$ and $\text{attempts} \ge 2$.
  - `partially_understood`: If attempted but not qualifying for mastered or revision.
- **DAG Prerequisite Validation**: Checks `check_prerequisites_satisfied(student_id, concept_id)` by querying the prerequisite graph and verifying each prerequisite has status `mastered`.

### 3.2 Socratic Repository (`apps/backend/app/repositories/socratic_repository.py`)
- Manages multi-turn session creation, step advancement, hint escalation, turn appending, and session termination.
- Resilient foreign-key handling ensures student profile creation if omitted.

---

## 4. Adaptive Tutoring Engines

### 4.1 Strategy Selector (`apps/backend/app/tutoring/strategy_selector.py`)
- Analyzes student prompt keywords, active Socratic sessions, concept mastery, and prerequisite satisfaction.
- Routes to `socratic_questioning`, `guided_problem_solving`, `remedial_instruction`, `worked_example`, or `direct_instruction`.
- Selects pedagogical explanation modes (`beginner`, `mathematical`, `exam_oriented`, etc.).

### 4.2 Socratic Engine (`apps/backend/app/tutoring/socratic_engine.py`)
- Formulates step-by-step questions without providing the direct answer.
- Evaluates student answers against step rubrics.
- Escalates hints progressively:
  - Level 1: Conceptual Direction.
  - Level 2: Explicit Guidance / Formula.
  - Level 3: Partial Solution / Setup.
  - Level 4: Full Solution Walkthrough.
- Detects stuck students (`consecutive_mistakes` $\ge$ threshold or hint level 4) and sets `is_stuck=True`.

### 4.3 Adaptive Explanation Engine (`apps/backend/app/tutoring/explanation_engine.py`)
- Tailors explanations across depth, analogies, concrete examples, and mathematical formulas depending on student profile and selected mode.

### 4.4 Misconception Detector (`apps/backend/app/tutoring/misconception_detector.py`)
- Detects common conceptual pitfalls (e.g., confusing bias and variance, correlation vs causation, overfitting vs underfitting).
- Deduplicates misconceptions and logs resolution status.

### 4.5 Adaptive Quiz Engine (`apps/backend/app/tutoring/quiz_engine.py`)
- Supports MCQ, True/False, Numerical, and Subjective questions.
- **Numerical Tolerance Checking**: Accepts answers within absolute ($|\text{actual} - \text{target}| \le \text{tol}$) or relative ($|\text{actual} - \text{target}| / |\text{target}| \le 0.01$) tolerances.
- **Subjective Rubric Evaluation**: Grades conceptual answers against multi-criteria rubrics.

### 4.6 Prerequisite Recommendation Engine (`apps/backend/app/tutoring/recommendation_engine.py`)
- Inspects SQLite concept graph, identifies missing prerequisite dependencies, and prioritizes remedial prerequisites before advanced concepts.

### 4.7 Learning Analytics Service (`apps/backend/app/tutoring/analytics_service.py`)
- Computes activity metrics, assessment metrics, mastery metrics, and an empirical learning improvement score:
  $$\text{Improvement Score} = \min(1.0, \max(0.0, \frac{\text{Recent Assessment Avg} - \text{Baseline}}{1.0 - \text{Baseline}}))$$

---

## 5. LangGraph and Multi-Agent Orchestration

- **Planner Agent**: Added detection of Socratic intents and routing to `Routes.SOCRATIC`.
- **Teacher Agent**: Integrated `StrategySelector` and `AdaptiveExplanationEngine` to adapt responses dynamically.
- **Evaluation Agent**: Integrated `AdaptiveQuizEngine`, recording evidence into `MasteryRepository` and tracking misconceptions.
- **Recommendation Agent**: Integrated `PrerequisiteRecommendationEngine` for curriculum gap analysis.
- **Workflow Graph**: Added `socratic` node and conditional edges from planner to socratic, routing directly to `memory` upon turn completion.

---

## 6. REST API Endpoints

- `GET /api/v1/analytics/progress/{student_id}`: Comprehensive learning analytics.
- `GET /api/v1/analytics/mastery/{student_id}`: List of concept masteries.
- `GET /api/v1/analytics/recommendations/{student_id}`: Prerequisite-aware recommendations.
- `POST /api/v1/socratic/start`: Start a new guided problem-solving session.
- `POST /api/v1/socratic/turn`: Submit student reasoning and receive next guided question or hint.
- `GET /api/v1/socratic/session/{session_id}`: Inspect Socratic session status.

---

## 7. Verification and Testing

- **30 New Unit & Integration Tests**:
  - `test_concept_mastery.py` (5 tests)
  - `test_socratic_dialogue.py` (3 tests)
  - `test_misconception_detection.py` (5 tests)
  - `test_adaptive_quiz.py` (4 tests)
  - `test_prerequisite_recommendations.py` (4 tests)
  - `test_adaptive_tutoring_workflow.py` (3 tests)
  - `test_learning_analytics_api.py` (6 tests)
- **Zero Regressions**: All 248 test suite tests pass completely.
