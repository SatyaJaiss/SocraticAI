"""Persistence for the conversation transcript and multi-session threads."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.models.orm import Conversation, ConversationSession
from app.repositories.base_repository import BaseRepository
from app.schemas.domain import ConversationSessionView
from app.utils.helpers import generate_id, utc_now_iso


class ConversationRepository(BaseRepository):
    """Transcript and session management for student <-> tutor dialogues."""

    # ------------------------------------------------------------- sessions --
    def create_session(
        self,
        student_id: str,
        title: str = "Tutoring Session",
        conversation_id: str | None = None,
    ) -> ConversationSessionView:
        """Create a new independent conversation session for the student."""
        cid = conversation_id or generate_id("conv")
        now = utc_now_iso()
        with self.session() as session:
            row = ConversationSession(
                id=cid,
                student_id=student_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return ConversationSessionView(
                id=row.id,
                student_id=row.student_id,
                title=row.title,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def get_session(self, conversation_id: str) -> ConversationSessionView | None:
        """Retrieve conversation session metadata by conversation_id."""
        with self.session() as session:
            row = session.get(ConversationSession, conversation_id)
            if row is None:
                return None
            return ConversationSessionView(
                id=row.id,
                student_id=row.student_id,
                title=row.title,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def list_sessions(self, student_id: str, limit: int = 50) -> list[ConversationSessionView]:
        """List all conversation sessions for a student, newest updated first."""
        with self.session() as session:
            rows = session.execute(
                select(ConversationSession)
                .where(ConversationSession.student_id == student_id)
                .order_by(ConversationSession.updated_at.desc())
                .limit(limit)
            ).scalars().all()
            return [
                ConversationSessionView(
                    id=r.id,
                    student_id=r.student_id,
                    title=r.title,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    def delete_session(self, student_id: str, conversation_id: str) -> bool:
        """Delete a conversation session and all its message records.

        Returns True if deleted, False if session did not exist or did not belong to student.
        """
        with self.session() as session:
            session_row = session.get(ConversationSession, conversation_id)
            if session_row is None or session_row.student_id != student_id:
                return False

            # Delete child messages
            session.execute(
                delete(Conversation).where(
                    Conversation.student_id == student_id,
                    Conversation.conversation_id == conversation_id,
                )
            )
            session.delete(session_row)
            return True

    # ------------------------------------------------------------- messages --
    def add_message(
        self,
        student_id: str,
        role: str,
        content: str,
        conversation_id: str = "",
        metadata_json: dict | None = None,
    ) -> int:
        """Append one message to the conversation transcript."""
        now = utc_now_iso()
        with self.session() as session:
            # If conversation_id is provided, ensure session exists or auto-create it
            if conversation_id:
                sess = session.get(ConversationSession, conversation_id)
                if sess is None:
                    sess = ConversationSession(
                        id=conversation_id,
                        student_id=student_id,
                        title=content[:40].strip() or "Tutoring Session",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(sess)
                else:
                    sess.updated_at = now

            row = Conversation(
                student_id=student_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata_json=metadata_json or {},
                created_at=now,
            )
            session.add(row)
            session.flush()
            return row.id

    def list_messages(
        self,
        student_id: str,
        conversation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return the most recent ``limit`` messages, oldest first.

        If ``conversation_id`` is supplied, filters messages to that conversation.
        """
        with self.session() as session:
            query = select(Conversation).where(Conversation.student_id == student_id)
            if conversation_id is not None:
                query = query.where(Conversation.conversation_id == conversation_id)

            rows = session.execute(
                query.order_by(Conversation.id.desc()).limit(limit)
            ).scalars().all()
            rows = list(reversed(rows))
            return [
                {
                    "id": r.id,
                    "student_id": r.student_id,
                    "conversation_id": r.conversation_id,
                    "role": r.role,
                    "content": r.content,
                    "metadata": r.metadata_json or {},
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def count(self, student_id: str, conversation_id: str | None = None) -> int:
        """Count total messages for a student, optionally filtered by conversation_id."""
        with self.session() as session:
            query = select(func.count()).select_from(Conversation).where(
                Conversation.student_id == student_id
            )
            if conversation_id is not None:
                query = query.where(Conversation.conversation_id == conversation_id)
            return session.execute(query).scalar_one()
