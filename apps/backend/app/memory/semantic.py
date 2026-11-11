"""Semantic memory store managing student misconceptions and profile knowledge."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from app.db.connection import Database
from app.models.orm import ConceptScoreRow, Student, StudentMisconception, Topic
from app.schemas.domain import Misconception
from app.utils.helpers import utc_now_iso

logger = logging.getLogger(__name__)


class SemanticMemoryStore:
    """Manages student misconceptions and structured conceptual proficiency state."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # --------------------------------------------------- Misconceptions -- #
    def record_misconception(
        self,
        student_id: str,
        concept: str,
        description: str,
        *,
        severity: str = "medium",
        confidence: float = 0.8,
        provenance: dict[str, Any] | None = None,
    ) -> Misconception:
        """Record or update an active misconception for a student."""
        now = utc_now_iso()
        with self._db.session() as session:
            # Check if active misconception for concept already exists
            existing = session.execute(
                select(StudentMisconception).where(
                    StudentMisconception.student_id == student_id,
                    StudentMisconception.concept == concept,
                    StudentMisconception.status == "active",
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.description = description
                existing.severity = severity
                existing.confidence = max(existing.confidence, confidence)
                if provenance:
                    existing.provenance = {**(existing.provenance or {}), **provenance}
                session.flush()
                return self._to_domain(existing)

            row = StudentMisconception(
                student_id=student_id,
                concept=concept,
                description=description,
                severity=severity,
                status="active",
                confidence=confidence,
                provenance=provenance or {},
                created_at=now,
            )
            session.add(row)
            session.flush()
            return self._to_domain(row)

    def resolve_misconception(self, misconception_id: int) -> bool:
        """Mark a misconception as resolved."""
        now = utc_now_iso()
        with self._db.session() as session:
            row = session.get(StudentMisconception, misconception_id)
            if row is None:
                return False
            row.status = "resolved"
            row.resolved_at = now
            session.flush()
            return True

    def list_active_misconceptions(self, student_id: str, limit: int = 10) -> list[Misconception]:
        """List active misconceptions ordered by severity and recency."""
        with self._db.session() as session:
            rows = (
                session.execute(
                    select(StudentMisconception)
                    .where(
                        StudentMisconception.student_id == student_id,
                        StudentMisconception.status == "active",
                    )
                    .order_by(desc(StudentMisconception.created_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [self._to_domain(r) for r in rows]

    # ------------------------------------------------- Semantic Profile -- #
    def get_semantic_profile(self, student_id: str) -> dict[str, Any]:
        """Aggregate semantic learning profile (mastered concepts, weak concepts, misconceptions)."""
        with self._db.session() as session:
            student = session.get(Student, student_id)
            level = student.level if student else "beginner"

            scores = (
                session.execute(
                    select(ConceptScoreRow)
                    .where(ConceptScoreRow.student_id == student_id)
                    .order_by(ConceptScoreRow.proficiency.asc())
                )
                .scalars()
                .all()
            )

            weak_concepts = [s.concept for s in scores if s.proficiency < 0.6]
            strong_concepts = [s.concept for s in scores if s.proficiency >= 0.8]

            mastered_topics = (
                session.execute(
                    select(Topic.name).where(
                        Topic.student_id == student_id,
                        Topic.mastered.is_(True),
                    )
                )
                .scalars()
                .all()
            )

            active_misconceptions = self.list_active_misconceptions(student_id)

            return {
                "student_id": student_id,
                "level": level,
                "weak_concepts": weak_concepts,
                "strong_concepts": strong_concepts,
                "mastered_topics": list(dict.fromkeys(mastered_topics)),
                "active_misconceptions": [
                    {"concept": m.concept, "description": m.description, "severity": m.severity}
                    for m in active_misconceptions
                ],
            }

    @staticmethod
    def _to_domain(row: StudentMisconception) -> Misconception:
        return Misconception(
            id=row.id,
            student_id=row.student_id,
            concept=row.concept,
            description=row.description,
            severity=row.severity,
            status=row.status,
            confidence=row.confidence,
            provenance=row.provenance or {},
            created_at=row.created_at,
            resolved_at=row.resolved_at,
        )
