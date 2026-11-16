# SocraticAI — Socratic Dialogue Architecture

## Overview

The Socratic Dialogue subsystem is designed to implement active, inquiry-based learning. Instead of directly giving away solutions to complex problems, SocraticAI guides students through structured problem decomposition, evaluates their intermediate reasoning, and provides progressive scaffolding when they struggle.

---

## 1. Core Principles

1. **No Answer Leakage**: The engine explicitly prohibits exposing the final numerical or conceptual answer in early turns. It guides the student to derive the answer independently.
2. **Step Decomposition**: Multi-step problems are divided into discrete sub-questions ($S_1, S_2, \dots, S_N$).
3. **Bounded Dialogue**: Each step has a maximum mistake tolerance. If a student remains stuck, the system escalates scaffolding rather than entering an infinite conversational loop.
4. **Progressive Hint Escalation**: 4 distinct scaffolding tiers:
   - **Tier 1 (Conceptual Direction)**: Re-orient the student toward the foundational concept or relevant law.
   - **Tier 2 (Explicit Guidance / Formula)**: Identify the exact formula, variable, or theorem to apply.
   - **Tier 3 (Partial Solution / Setup)**: Substitute known values or solve the initial algebraic step.
   - **Tier 4 (Full Solution Walkthrough)**: Reveal the step solution with a complete explanation.
5. **Stuck Student Detection**: When `consecutive_mistakes` $\ge 3$ or hint tier reaches Level 4, `is_stuck` is flagged, alerting the orchestrator and human educators.

---

## 2. State Machine and Escalation Lifecycle

```mermaid
stateDiagram-v2
    [*] --> InProgress: Start Socratic Session
    
    state InProgress {
        [*] --> PoseStepQuestion
        PoseStepQuestion --> EvaluateAnswer: Student Submits Reasoning
        
        EvaluateAnswer --> StepCorrect: Answer Correct / Valid Reasoning
        StepCorrect --> NextStep: Has Next Step?
        NextStep --> PoseStepQuestion: Advance Step Index
        NextStep --> SessionCompleted: All Steps Complete
        
        EvaluateAnswer --> StepIncorrect: Answer Incorrect / Partial
        StepIncorrect --> EscalateHint: Increment Mistakes
        
        state EscalateHint {
            [*] --> Level1: Mistake 1 (Conceptual)
            Level1 --> Level2: Mistake 2 (Formula/Guidance)
            Level2 --> Level3: Mistake 3 (Partial Setup)
            Level3 --> Level4: Mistake >= 4 (Full Walkthrough)
        }
        
        EscalateHint --> FlagStuck: Level >= 3 or Mistakes >= 3
        FlagStuck --> PoseStepQuestion: Provide Scaffolding
    }
    
    SessionCompleted --> [*]: Record Mastery Evidence
```

---

## 3. Hint Escalation Ladder

```mermaid
flowchart TD
    Mistake0["Initial Prompt / New Step"] -->|"Incorrect Attempt"| Tier1["Tier 1: Conceptual Direction\n'Think about conservation of energy...'"]
    Tier1 -->|"Still Incorrect"| Tier2["Tier 2: Explicit Guidance & Formula\n'Recall that KE = 1/2 * m * v^2...'"]
    Tier2 -->|"Still Incorrect"| Tier3["Tier 3: Partial Solution Setup\n'Substitute m=2 and v=3: KE = 0.5 * 2 * 9...'"]
    Tier3 -->|"Still Incorrect"| Tier4["Tier 4: Full Walkthrough\n'Here is the complete derivation: 9 Joules. Now let us reflect on why...'"]
    
    Tier3 -.->|"Flag is_stuck=True"| StuckAlert["Teacher / System Notification"]
    Tier4 -.->|"Flag is_stuck=True"| StuckAlert
```

---

## 4. Multi-Turn Session Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Student
    participant Router as API / Graph Orchestrator
    participant SocraticRepo as SocraticRepository
    participant SocraticEng as SocraticEngine
    participant MasteryRepo as MasteryRepository

    Student->>Router: POST /api/v1/socratic/start (problem_statement, concept_id)
    Router->>SocraticRepo: create_session(student_id, concept_id, problem, steps)
    SocraticRepo-->>Router: SocraticDialogueSession (session_id, step 0)
    Router->>SocraticEng: generate_initial_turn(session)
    SocraticEng-->>Router: SocraticTurnResponse(step=0, question="What is the first step?")
    Router-->>Student: Display Step 1 Inquiry

    Student->>Router: POST /api/v1/socratic/turn (session_id, student_response="Is it X?")
    Router->>SocraticRepo: get_session(session_id)
    Router->>SocraticEng: evaluate_step_turn(session, student_response)
    
    alt Answer is Incorrect
        SocraticEng->>SocraticRepo: record_turn(session, is_correct=False, hint_tier=1)
        SocraticEng-->>Router: SocraticTurnResponse(hint_level=1, hint="Consider...")
        Router-->>Student: Deliver Tier 1 Hint
    else Answer is Correct
        SocraticEng->>SocraticRepo: record_turn(session, is_correct=True, advance_step=True)
        opt All Steps Completed
            SocraticEng->>MasteryRepo: record_evidence(student_id, concept_id, score=1.0)
            SocraticEng-->>Router: SocraticTurnResponse(session_completed=True)
        end
        Router-->>Student: Congratulate and Advance / Finish
    end
```

---

## 5. Persistence and Recovery

Each Socratic dialogue session is backed by the `socratic_dialogue_sessions` table in SQLite:
- `session_id`: UUID primary key.
- `student_id`: Student foreign key.
- `concept_id`: Linked curriculum concept.
- `current_step`: Zero-indexed current step.
- `total_steps`: Number of steps defined for this problem.
- `hint_level`: Currently escalated hint tier (0 to 4).
- `consecutive_mistakes`: Number of consecutive incorrect submissions on the current step.
- `is_stuck`: Boolean flag indicating whether the student is blocked.
- `history_turns`: JSON-encoded transcript of all student submissions and tutor feedback.

When network interruptions or page reloads occur, the session can be retrieved via `GET /api/v1/socratic/session/{session_id}`, enabling seamless resumption of the guided dialogue.
