"""Mastery repository — evidence ledger, Bayesian-smoothed mastery updates, and prerequisite graph."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import desc, select

from app.core.config import MasterySettings
from app.models.orm import ConceptMasteryRow, ConceptPrerequisite, LearningEvidence
from app.repositories.base_repository import BaseRepository
from app.schemas.domain import (
    ConceptMasterySchema,
    ConceptPrerequisiteSchema,
    LearningEvidenceSchema,
)
from app.schemas.enums import EvidenceType, MasteryStatus, PrerequisiteRelation
from app.utils.helpers import utc_now_iso


class MasteryRepository(BaseRepository):
    """Manages concept learning evidence, smoothed mastery transitions, and dependency graphs."""

    def __init__(self, db, settings: MasterySettings | None = None) -> None:
        super().__init__(db)
        self.settings = settings or MasterySettings()

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

    # ------------------------------------------------------------- Evidence -- #
    def record_evidence(
        self,
        *,
        student_id: str,
        concept: str,
        evidence_type: EvidenceType | str,
        score: float,
        demonstrated: bool,
        confidence: float = 0.5,
        provenance: dict[str, Any] | None = None,
    ) -> LearningEvidenceSchema:
        """Append an assessment or dialogue observation to the student's learning audit ledger."""
        ev_type_val = (
            evidence_type.value if isinstance(evidence_type, EvidenceType) else str(evidence_type)
        )
        clamped_score = max(0.0, min(1.0, float(score)))
        clamped_conf = max(0.0, min(1.0, float(confidence)))
        now = utc_now_iso()

        with self.session() as session:
            self._ensure_student(session, student_id)
            row = LearningEvidence(
                student_id=student_id,
                concept=concept.strip(),
                evidence_type=ev_type_val,
                score=clamped_score,
                demonstrated=demonstrated,
                confidence=clamped_conf,
                provenance=provenance or {},
                created_at=now,
            )
            session.add(row)
            session.flush()

            evidence_schema = LearningEvidenceSchema(
                id=row.id,
                student_id=row.student_id,
                concept=row.concept,
                evidence_type=EvidenceType(row.evidence_type),
                score=row.score,
                demonstrated=row.demonstrated,
                confidence=row.confidence,
                provenance=row.provenance or {},
                created_at=row.created_at,
            )

        # Automatically update concept mastery using evidence update policy
        self.update_mastery_from_evidence(
            student_id=student_id,
            concept=concept.strip(),
            evidence_score=clamped_score,
            evidence_confidence=clamped_conf,
        )

        return evidence_schema

    def list_evidence(
        self,
        student_id: str,
        concept: str | None = None,
        limit: int = 50,
    ) -> list[LearningEvidenceSchema]:
        """Fetch chronological evidence entries for a student and optional concept."""
        with self.session() as session:
            stmt = select(LearningEvidence).where(LearningEvidence.student_id == student_id)
            if concept:
                stmt = stmt.where(LearningEvidence.concept == concept)
            stmt = stmt.order_by(desc(LearningEvidence.created_at)).limit(limit)

            rows = session.execute(stmt).scalars().all()
            return [
                LearningEvidenceSchema(
                    id=r.id,
                    student_id=r.student_id,
                    concept=r.concept,
                    evidence_type=EvidenceType(r.evidence_type),
                    score=r.score,
                    demonstrated=r.demonstrated,
                    confidence=r.confidence,
                    provenance=r.provenance or {},
                    created_at=r.created_at,
                )
                for r in rows
            ]

    # -------------------------------------------------------------- Mastery -- #
    def update_mastery_from_evidence(
        self,
        *,
        student_id: str,
        concept: str,
        evidence_score: float,
        evidence_confidence: float,
    ) -> ConceptMasterySchema:
        """Apply smoothed, evidence-weighted updates to the student's concept mastery."""
        now = utc_now_iso()
        with self.session() as session:
            self._ensure_student(session, student_id)
            row = session.execute(
                select(ConceptMasteryRow).where(
                    ConceptMasteryRow.student_id == student_id,
                    ConceptMasteryRow.concept == concept,
                )
            ).scalar_one_or_none()

            if row is None:
                # First attempt: single evidence confidence C(1) = 1.0 - exp(-0.45) approx 0.36
                initial_confidence = round(1.0 - math.exp(-0.45), 4)
                status = (
                    MasteryStatus.PARTIALLY_UNDERSTOOD
                    if evidence_score >= self.settings.partial_understanding_threshold
                    else MasteryStatus.ATTEMPTED
                )
                row = ConceptMasteryRow(
                    student_id=student_id,
                    concept=concept,
                    mastery_score=round(evidence_score, 4),
                    confidence=initial_confidence,
                    status=status.value,
                    attempts=1,
                    last_assessed_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                return self._row_to_mastery(row)

            # Iterative evidence update
            row.attempts += 1
            n = row.attempts

            # Effective update weight modulated by evidence confidence
            weight = min(1.0, max(0.1, self.settings.evidence_weight * evidence_confidence))
            new_score = round((1.0 - weight) * row.mastery_score + weight * evidence_score, 4)

            # Asymptotic confidence growth: C(n) = 1.0 - exp(-0.45 * n)
            new_confidence = round(1.0 - math.exp(-0.45 * n), 4)

            # State transition policy
            if n < self.settings.min_evidence_count:
                # Inconclusive evidence count: cap at PARTIALLY_UNDERSTOOD
                if new_score >= self.settings.partial_understanding_threshold:
                    new_status = MasteryStatus.PARTIALLY_UNDERSTOOD
                else:
                    new_status = MasteryStatus.ATTEMPTED
            else:
                # Sufficient evidence count: qualify for MASTERED or NEEDS_REVISION
                if (
                    new_score >= self.settings.mastery_threshold
                    and new_confidence >= self.settings.confidence_threshold
                ):
                    new_status = MasteryStatus.MASTERED
                elif new_score >= self.settings.partial_understanding_threshold:
                    new_status = MasteryStatus.PARTIALLY_UNDERSTOOD
                else:
                    new_status = MasteryStatus.NEEDS_REVISION

            row.mastery_score = new_score
            row.confidence = new_confidence
            row.status = new_status.value
            row.last_assessed_at = now
            row.updated_at = now
            session.flush()

            return self._row_to_mastery(row)

    def get_mastery(self, student_id: str, concept: str) -> ConceptMasterySchema | None:
        """Fetch mastery state for a specific concept."""
        with self.session() as session:
            row = session.execute(
                select(ConceptMasteryRow).where(
                    ConceptMasteryRow.student_id == student_id,
                    ConceptMasteryRow.concept == concept,
                )
            ).scalar_one_or_none()
            return self._row_to_mastery(row) if row else None

    def list_mastery(self, student_id: str) -> list[ConceptMasterySchema]:
        """Fetch all concept mastery records for a student."""
        with self.session() as session:
            rows = (
                session.execute(
                    select(ConceptMasteryRow)
                    .where(ConceptMasteryRow.student_id == student_id)
                    .order_by(desc(ConceptMasteryRow.mastery_score))
                )
                .scalars()
                .all()
            )
            return [self._row_to_mastery(r) for r in rows]

    # --------------------------------------------------------- Prerequisites -- #
    def add_prerequisite(
        self,
        concept: str,
        prerequisite_concept: str,
        relationship_type: PrerequisiteRelation | str = PrerequisiteRelation.DIRECT,
        description: str = "",
    ) -> ConceptPrerequisiteSchema:
        """Register a prerequisite dependency in the concept adjacency graph."""
        rel_val = (
            relationship_type.value
            if isinstance(relationship_type, PrerequisiteRelation)
            else str(relationship_type)
        )
        now = utc_now_iso()

        with self.session() as session:
            existing = session.execute(
                select(ConceptPrerequisite).where(
                    ConceptPrerequisite.concept == concept.strip(),
                    ConceptPrerequisite.prerequisite_concept == prerequisite_concept.strip(),
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.relationship_type = rel_val
                existing.description = description
                session.flush()
                return self._row_to_prereq(existing)

            row = ConceptPrerequisite(
                concept=concept.strip(),
                prerequisite_concept=prerequisite_concept.strip(),
                relationship_type=rel_val,
                description=description,
                created_at=now,
            )
            session.add(row)
            session.flush()
            return self._row_to_prereq(row)

    def get_prerequisites(self, concept: str) -> list[ConceptPrerequisiteSchema]:
        """Return all prerequisite dependencies for a given concept."""
        with self.session() as session:
            rows = (
                session.execute(
                    select(ConceptPrerequisite).where(
                        ConceptPrerequisite.concept == concept.strip()
                    )
                )
                .scalars()
                .all()
            )
            return [self._row_to_prereq(r) for r in rows]

    def check_prerequisites_satisfied(
        self,
        student_id: str,
        concept: str,
        threshold: float | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify whether all prerequisites for a target concept meet the mastery threshold.

        Returns: (all_satisfied: bool, missing_prerequisite_names: list[str])
        """
        req_threshold = threshold if threshold is not None else self.settings.mastery_threshold
        prereqs = self.get_prerequisites(concept)
        if not prereqs:
            return True, []

        missing: list[str] = []
        for p in prereqs:
            m = self.get_mastery(student_id, p.prerequisite_concept)
            # Prerequisite is unsatisfied if unattempted or mastery score is below threshold
            if m is None or m.mastery_score < req_threshold:
                missing.append(p.prerequisite_concept)

        return len(missing) == 0, missing

    def seed_default_curriculum(self) -> int:
        """Populate initial foundational prerequisite graphs across Math, Deep Learning, and Physics."""
        curriculum_edges = [
            # Deep Learning
            (
                "Neural Networks",
                "Linear Algebra",
                PrerequisiteRelation.DIRECT,
                "Vector and matrix operations",
            ),
            (
                "Neural Networks",
                "Calculus",
                PrerequisiteRelation.DIRECT,
                "Derivatives and gradients",
            ),
            (
                "Activation Functions",
                "Neural Networks",
                PrerequisiteRelation.DIRECT,
                "Non-linear transformations",
            ),
            (
                "Gradient Descent",
                "Calculus",
                PrerequisiteRelation.DIRECT,
                "Partial derivatives and slope",
            ),
            (
                "Backpropagation",
                "Calculus",
                PrerequisiteRelation.DIRECT,
                "Chain rule of differentiation",
            ),
            (
                "Backpropagation",
                "Computational Graphs",
                PrerequisiteRelation.DIRECT,
                "Forward and backward graph passes",
            ),
            (
                "Backpropagation",
                "Gradient Descent",
                PrerequisiteRelation.DIRECT,
                "Error gradient propagation",
            ),
            ("CNN", "Neural Networks", PrerequisiteRelation.DIRECT, "Feedforward dense networks"),
            (
                "CNN",
                "Convolution Operation",
                PrerequisiteRelation.DIRECT,
                "Filter kernels and feature maps",
            ),
            (
                "RNN",
                "Neural Networks",
                PrerequisiteRelation.DIRECT,
                "Sequential recurrent feedback loops",
            ),
            (
                "Transformers",
                "Attention Mechanism",
                PrerequisiteRelation.DIRECT,
                "Self-attention queries, keys, values",
            ),
            ("Transformers", "RNN", PrerequisiteRelation.WEAK, "Sequence modeling paradigms"),
            # Physics
            (
                "First Law of Thermodynamics",
                "Work and Heat",
                PrerequisiteRelation.DIRECT,
                "Energy conservation basics",
            ),
            (
                "Second Law of Thermodynamics",
                "First Law of Thermodynamics",
                PrerequisiteRelation.DIRECT,
                "Entropy and irreversibility",
            ),
            (
                "Carnot Engine",
                "Second Law of Thermodynamics",
                PrerequisiteRelation.DIRECT,
                "Reversible heat cycles",
            ),
        ]

        added = 0
        for concept, prereq, rel, desc_text in curriculum_edges:
            self.add_prerequisite(concept, prereq, rel, desc_text)
            added += 1
        return added

    # ------------------------------------------------------------- Helpers -- #
    @staticmethod
    def _row_to_mastery(row: ConceptMasteryRow) -> ConceptMasterySchema:
        return ConceptMasterySchema(
            concept=row.concept,
            mastery_score=row.mastery_score,
            confidence=row.confidence,
            status=MasteryStatus(row.status),
            attempts=row.attempts,
            last_assessed_at=row.last_assessed_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _row_to_prereq(row: ConceptPrerequisite) -> ConceptPrerequisiteSchema:
        return ConceptPrerequisiteSchema(
            id=row.id,
            concept=row.concept,
            prerequisite_concept=row.prerequisite_concept,
            relationship_type=PrerequisiteRelation(row.relationship_type),
            description=row.description,
            created_at=row.created_at,
        )
