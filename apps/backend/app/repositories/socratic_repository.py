"""Socratic dialogue session repository — stateful multi-turn guided problem solving."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from app.models.orm import SocraticDialogueSession
from app.repositories.base_repository import BaseRepository
from app.utils.helpers import generate_id, utc_now_iso


class SocraticRepository(BaseRepository):
    """Persistence and state transitions for multi-turn Socratic problem solving."""

    def _ensure_student(self, session, student_id: str) -> None:
        """Ensure student record exists to satisfy foreign key constraints."""
        from app.models.orm import StudentProfileRow

        if session.get(StudentProfileRow, student_id) is None:
            now = utc_now_iso()
            session.add(
                StudentProfileRow(
                    id=student_id,
                    name="Learner",
                    level="beginner",
                    learning_style="reading_writing",
                    learning_speed="normal",
                    preferred_difficulty="beginner",
                    topics_learned=[],
                    weak_concepts=[],
                    quiz_scores=[],
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()

    def create_session(
        self,
        *,
        student_id: str,
        conversation_id: str,
        concept: str,
        problem_statement: str,
        target_solution: str = "",
        total_steps: int = 3,
        max_hint_level: int = 4,
    ) -> SocraticDialogueSession:
        """Initialize a new Socratic problem-solving dialogue session."""
        now = utc_now_iso()
        session_id = generate_id("soc")

        with self.session() as session:
            self._ensure_student(session, student_id)
            # Mark any prior in-progress session for this conversation as abandoned
            prior = (
                session.execute(
                    select(SocraticDialogueSession).where(
                        SocraticDialogueSession.student_id == student_id,
                        SocraticDialogueSession.conversation_id == conversation_id,
                        SocraticDialogueSession.status == "in_progress",
                    )
                )
                .scalars()
                .all()
            )
            for p in prior:
                p.status = "abandoned"
                p.updated_at = now

            row = SocraticDialogueSession(
                id=session_id,
                student_id=student_id,
                conversation_id=conversation_id,
                concept=concept.strip(),
                problem_statement=problem_statement.strip(),
                current_step=1,
                total_steps=max(1, total_steps),
                current_hint_level=0,
                max_hint_level=max_hint_level,
                status="in_progress",
                turn_count=0,
                target_solution=target_solution.strip(),
                history_json=[],
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return row

    def get_session(self, session_id: str) -> SocraticDialogueSession | None:
        """Fetch session by ID."""
        with self.session() as session:
            return session.get(SocraticDialogueSession, session_id)

    def get_active_session(
        self,
        student_id: str,
        conversation_id: str,
    ) -> SocraticDialogueSession | None:
        """Retrieve the currently active in-progress Socratic session for this dialogue thread."""
        with self.session() as session:
            return session.execute(
                select(SocraticDialogueSession)
                .where(
                    SocraticDialogueSession.student_id == student_id,
                    SocraticDialogueSession.conversation_id == conversation_id,
                    SocraticDialogueSession.status == "in_progress",
                )
                .order_by(desc(SocraticDialogueSession.created_at))
                .limit(1)
            ).scalar_one_or_none()

    def advance_step(self, session_id: str, step_note: str = "") -> SocraticDialogueSession | None:
        """Advance student to the next intermediate step, resetting current hint level for the new step."""
        now = utc_now_iso()
        with self.session() as session:
            row = session.get(SocraticDialogueSession, session_id)
            if row is None:
                return None

            row.current_step += 1
            row.current_hint_level = 0  # Reset hint escalation for the new step
            row.turn_count += 1
            row.updated_at = now

            history = list(row.history_json or [])
            history.append(
                {"event": "advance_step", "step": row.current_step, "note": step_note, "time": now}
            )
            row.history_json = history

            if row.current_step > row.total_steps:
                row.status = "completed"

            session.flush()
            return row

    def escalate_hint(self, session_id: str, hint_text: str = "") -> int:
        """Escalate progressive hint level (1 -> 2 -> 3 -> 4), capped at max_hint_level."""
        now = utc_now_iso()
        with self.session() as session:
            row = session.get(SocraticDialogueSession, session_id)
            if row is None:
                return 0

            new_level = min(row.current_hint_level + 1, row.max_hint_level)
            row.current_hint_level = new_level
            row.turn_count += 1
            row.updated_at = now

            history = list(row.history_json or [])
            history.append({"event": "hint", "level": new_level, "hint": hint_text, "time": now})
            row.history_json = history

            session.flush()
            return new_level

    def record_turn(
        self,
        session_id: str,
        student_input: str,
        tutor_response: str,
        step_assessment: dict[str, Any] | None = None,
    ) -> None:
        """Record an interactive dialogue turn in session history."""
        now = utc_now_iso()
        with self.session() as session:
            row = session.get(SocraticDialogueSession, session_id)
            if row is None:
                return
            row.turn_count += 1
            row.updated_at = now

            history = list(row.history_json or [])
            history.append(
                {
                    "turn": row.turn_count,
                    "student": student_input,
                    "tutor": tutor_response,
                    "assessment": step_assessment or {},
                    "time": now,
                }
            )
            row.history_json = history
            session.flush()

    def complete_session(
        self,
        session_id: str,
        *,
        solution_revealed: bool = False,
    ) -> SocraticDialogueSession | None:
        """Mark session as successfully completed or concluded with revealed solution."""
        now = utc_now_iso()
        with self.session() as session:
            row = session.get(SocraticDialogueSession, session_id)
            if row is None:
                return None

            row.status = "resolved_with_solution" if solution_revealed else "completed"
            row.updated_at = now
            session.flush()
            return row
