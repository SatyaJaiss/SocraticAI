# SocraticAI — Milestone 3: Adaptive Tutoring & Learning Intelligence Verification

**Document Version:** 1.0.0  
**Status:** Verification Complete — Architecture & Design Confirmed  
**Date:** November 2026  
**Target Repository:** SocraticAI  

---

## 1. Executive Summary

Milestone 1 established foundational security, authentication, session persistence, and LangGraph lifecycle integrity. Milestone 1.5 implemented layered memory (working, episodic, semantic), Jev/Gemini Decisions provider routing, caching, and token-aware context building. Milestone 2 modernized the RAG subsystem into a multi-modal hybrid retrieval engine with section-aware chunking, Reciprocal Rank Fusion, Cross-Encoder reranking, decision relevance grading, and citation verification.

This verification report audits the existing educational capabilities of SocraticAI to guide the implementation of **Milestone 3: Adaptive Tutoring & Learning Intelligence**.

---

## 2. Audit of Existing Capabilities

### 2.1 Existing Tutoring Capabilities
- **Current State**: Handled primarily by `TeacherAgent` in [`apps/backend/app/agents/teacher/agent.py`](file:///d:/ML/EduAgent-master/apps/backend/app/agents/teacher/agent.py).
- **Behavior**: The agent renders an explanation with `topic`, `summary`, `explanation`, `examples`, `analogies`, and `recap` formatted in Markdown.
- **Confirmed Limitation**:
  - Rigid "lecture" format: Every tutoring request yields an identical structured explanation regardless of whether the student is asking for a direct answer, stuck on a problem, seeking a hint, or exploring through Socratic questioning.
  - Lack of multi-turn guided dialogue: The teacher does not engage in back-and-forth Socratic inquiry or progressive hints.
  - No adaptation of pedagogical depth (e.g., beginner vs mathematical vs intuitive vs exam-oriented).

### 2.2 Existing Educational Assessment Capabilities
- **Current State**: Split between `QuizAgent` (`apps/backend/app/agents/quiz/agent.py`) and `EvaluationAgent` (`apps/backend/app/agents/evaluation/agent.py`).
- **Behavior**: Evaluates quiz submissions deterministically for MCQs and numerical questions, and invokes an LLM for subjective written questions.
- **Confirmed Limitation**:
  - Subjective grading relies on free-form LLM output without an explicit structured rubric.
  - Numerical evaluation uses a hardcoded float comparison without configurable tolerances or unit handling.
  - True/False and multi-select questions lack dedicated validation logic.

### 2.3 Existing Quiz Functionality
- **Current State**: `QuizAgent` produces a fixed composition: 5 MCQs + 2 Numerical + 1 Subjective question.
- **Confirmed Limitation**:
  - Static composition: Regardless of student level, weak areas, or topic complexity, the composition is fixed.
  - Does not adapt difficulty dynamically based on rolling student mastery or prior assessment history.
  - Does not enforce document-specific grounding for quizzes generated from uploaded course materials.

### 2.4 Current Student Mastery Representation
- **Current State**: Handled in `StudentRepository` (`ConceptScoreRow` in `orm.py`).
- **Fields**: `concept: str`, `proficiency: float`, `attempts: int`.
- **Update Rule**: Exponential moving average:
  $$\text{proficiency}_{new} = (1 - \alpha) \cdot \text{proficiency}_{old} + \alpha \cdot \text{score}$$
  with default $\alpha = 0.6$.
- **Confirmed Limitation**:
  - Coarse-grained: Concepts are flat string labels without hierarchical or prerequisite relationships.
  - No confidence estimation: A single quiz attempt immediately shifts proficiency to 60%.
  - No distinction between attempted, partially understood, and mastered concepts.
  - No audit trail or evidence provenance associating specific questions/exercises with mastery changes.

### 2.5 Existing Misconception Tracking
- **Current State**: `StudentMisconception` ORM model added in Milestone 1.5, managed by `SemanticMemoryStore`.
- **Fields**: `student_id`, `concept`, `description`, `severity`, `status`, `confidence`, `provenance`, `created_at`, `resolved_at`.
- **Confirmed Limitation**:
  - Disconnected from the real-time tutoring loop: `SemanticMemoryStore.record_misconception` is available, but neither `TeacherAgent` nor `EvaluationAgent` actively detects misconceptions during conversation turns or verifies resolution during subsequent assessments.
  - Risk of false positives: A single wrong answer could be misclassified as a conceptual misconception rather than a calculation slip.

### 2.6 Existing Recommendation Logic
- **Current State**: `RecommendationAgent` in [`apps/backend/app/agents/recommendation/agent.py`](file:///d:/ML/EduAgent-master/apps/backend/app/agents/recommendation/agent.py).
- **Behavior**: Generates `next_topic`, `rationale`, `revision_schedule`, `daily_plan`, `weak_areas`, and `suggested_quiz_topics` via single LLM prompt.
- **Confirmed Limitation**:
  - LLM hallucination risk: The LLM invents next topics without verifying whether prerequisites have been satisfied.
  - No structural concept graph: No dependency validation (e.g., recommending Backpropagation before Chain Rule).

---

## 3. Reusable Components & Architectural Assets

1. **BaseDecisionProvider & Composite Engine** (`apps/backend/app/decision/`):
   - High-performance, calibrated categorical choice and boolean evaluation. Can be utilized for pedagogical strategy selection, student response classification, and recommendation gating without incurring generative LLM latency.
2. **ContextBuilder** (`apps/backend/app/context/builder.py`):
   - Strict token budgeting and section-aware context assembly.
3. **CitationVerifier** (`apps/backend/app/rag/citation/verifier.py`):
   - Deterministic ownership, page existence, and semantic claim support validation for generated learning materials.
4. **StudentRepository & SemanticMemoryStore**:
   - Solid foundation for student profiles, session persistence, and misconception records.

---

## 4. Required Schema & Database Changes

To satisfy the requirements of Milestone 3 without introducing a graph database:

1. **`ConceptPrerequisite` (ORM Model & Table)**:
   - Relational adjacency representation of concept dependencies.
   - Fields: `id`, `concept` (str), `prerequisite_concept` (str), `relationship_type` (str: `"direct"`, `"weak"`, `"co_requisite"`), `description` (str).
2. **`LearningEvidence` (ORM Model & Table)**:
   - Traceable evidence ledger capturing every assessment, dialogue demonstration, or problem-solving attempt.
   - Fields: `id`, `student_id`, `concept`, `evidence_type` (`"quiz"`, `"dialogue"`, `"problem_solving"`), `score` (float), `demonstrated` (bool), `confidence` (float), `provenance` (JSON), `timestamp` (str).
3. **`ConceptMastery` (ORM Model & Table - Enhanced from `ConceptScoreRow`)**:
   - Fields: `student_id`, `concept`, `mastery_level` (float), `confidence` (float), `status` (`"attempted"`, `"partially_understood"`, `"mastered"`, `"needs_revision"`), `attempt_count` (int), `last_assessed_at` (str), `decay_factor` (float).
4. **`SocraticDialogueState` (Dialogue Tracking)**:
   - Tracks ongoing Socratic problem-solving sessions, current step, current hint level (1..4), target concept, and student responses.

---

## 5. Proposed Workflow Changes in LangGraph

1. **Tutoring Workflow Evolution**:
   - `Router` -> `StrategySelector` (Dynamic Pedagogical Strategy Selection):
     - `Direct Explanation`
     - `Socratic Dialogue` (Guided Questioning & Problem Solving)
     - `Hint Generation` (Bounded Levels 1..4)
     - `Conceptual Analogy / Worked Example`
     - `Knowledge Checking / Revision`
2. **Socratic Dialogue Node**:
   - Manages progressive scaffolding, evaluates student responses against target reasoning steps, bounds hint escalation to Level 4 (revealing the full solution only when requested or when further questioning is unproductive).
3. **Misconception Detection Node / Hook**:
   - Analyzes student answers for recurring conceptual errors, registers evidence in `StudentMisconception`, and adjusts prerequisite revision paths.
4. **Prerequisite-Aware Recommendation Node**:
   - Deterministically queries the concept dependency graph to ensure recommended concepts have satisfied prerequisites.

---

## 6. Verification Conclusion

The existing architecture provides strong modularity and clean abstractions. All requirements for Milestone 3 can be implemented cleanly via additive schema extensions, specialized agent nodes, and deterministic evaluation engines while preserving 100% of Milestone 1, 1.5, and 2 guarantees.
