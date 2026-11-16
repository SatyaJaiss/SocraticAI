# SocraticAI — Concept-Level Learning State Architecture

## Overview

Traditional learning management systems track coarse metrics such as total questions answered or overall course completion percentages. SocraticAI introduces a **fine-grained, concept-level learning state model**.

Every curriculum domain is modeled as a set of atomic concepts (e.g., `derivatives`, `chain_rule`, `gradient_descent`, `backpropagation`). Each student maintains an independent learning state for every concept.

---

## 1. Learning State Schema

```mermaid
erDiagram
    STUDENT ||--o{ CONCEPT_MASTERY : maintains
    STUDENT ||--o{ LEARNING_EVIDENCE : generates
    CONCEPT ||--o{ CONCEPT_PREREQUISITE : requires
    CONCEPT ||--o{ CONCEPT_MASTERY : assessed_in
    CONCEPT ||--o{ LEARNING_EVIDENCE : observed_for

    CONCEPT_MASTERY {
        int id PK
        string student_id FK
        string concept_id
        float mastery_score
        float confidence
        int attempts_count
        int success_count
        string status
        datetime last_attempted_at
    }

    LEARNING_EVIDENCE {
        int id PK
        string student_id FK
        string concept_id
        string evidence_type
        float score
        float weight
        json context_meta
        datetime created_at
    }

    CONCEPT_PREREQUISITE {
        string concept_id PK
        string prerequisite_concept_id PK
        string relation_type
    }
```

---

## 2. Learning State Machine

```mermaid
stateDiagram-v2
    [*] --> not_attempted: New Student / Concept Initialized

    not_attempted --> attempted: First interaction (n=1)
    
    state attempted {
        [*] --> EvaluateFirstAttempt
        EvaluateFirstAttempt --> partially_understood: Score < 0.80 or n < 3
    }

    partially_understood --> partially_understood: n < 3 or Score in [0.60, 0.79]
    partially_understood --> mastered: n >= 3 AND Score >= 0.80 AND Confidence >= 0.70
    partially_understood --> needs_revision: n >= 2 AND Score < 0.60

    needs_revision --> partially_understood: Score improves to >= 0.60
    needs_revision --> mastered: n >= 3 AND Score >= 0.80 AND Confidence >= 0.70

    mastered --> needs_revision: Score drops < 0.60 (e.g. repeated retention quiz failure)
    mastered --> [*]
```

### State Definitions

| State | Criteria | Meaning | Recommended Strategy |
| :--- | :--- | :--- | :--- |
| `not_attempted` | $n = 0$ attempts | The student has never interacted with this concept. | Direct Instruction / Overview |
| `attempted` | $n = 1$ attempt, score $< 0.80$ | Initial engagement recorded; insufficient evidence for mastery. | Guided Practice / Worked Example |
| `partially_understood` | $n \ge 1$, score $\ge 0.60$, but $n < 3$ or confidence $< 0.70$ | Student demonstrates partial understanding, but needs reinforcement. | Socratic Questioning / Practice |
| `mastered` | $n \ge 3$, score $\ge 0.80$, confidence $\ge 0.70$ | High demonstrated competence with statistical confidence. | Advanced Applications / New Topics |
| `needs_revision` | $n \ge 2$, score $< 0.60$ | Demonstrates persistent struggle, confusion, or regressions. | Remedial Instruction / Prerequisite Review |

---

## 3. Evidence Collection & Types

The system ingests structured evidence from multiple modalities:

| Evidence Type | Default Weight | Description |
| :--- | :---: | :--- |
| `quiz_submission` | $1.0$ | Direct evaluation from adaptive quizzes (MCQ, True/False, Numerical). |
| `socratic_turn` | $0.8$ | Independent problem-solving step validation during Socratic dialogue. |
| `practice_problem` | $0.7$ | Ungraded or guided exercises. |
| `teacher_observation` | $0.9$ | Automated pedagogical evaluation from conversational responses. |
| `self_assessment` | $0.3$ | Student-reported confidence ratings. |

Evidence items are logged append-only into `learning_evidence` to preserve an immutable audit trail of learning progression.
