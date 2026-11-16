"""Unit tests for CitationVerifier, ownership isolation, page validation, and claim grounding."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.core.config import CitationSettings
from app.rag.citation.verifier import CitationVerifier
from app.schemas.domain import DocumentRecord, RetrievedChunk


class TestCitationVerifier:
    @pytest.fixture
    def verifier(self):
        mock_repo = MagicMock()
        # Mock student documents
        mock_repo.list_for_student.return_value = [
            DocumentRecord(
                id="doc_bio_1",
                student_id="student_1",
                filename="biology_notes.pdf",
                status="ready",
                chunk_count=5,
            ),
            DocumentRecord(
                id="doc_chem_1",
                student_id="student_1",
                filename="chemistry.pdf",
                status="ready",
                chunk_count=4,
            ),
        ]
        settings = CitationSettings(
            enabled=True,
            verification_threshold=0.40,
            max_claims_per_verification=8,
        )
        return CitationVerifier(mock_repo, settings)

    def test_extract_citations(self, verifier):
        text = (
            "Photosynthesis converts light into glucose [Source: biology_notes.pdf, p. 2]. "
            "ATP is generated during the light reactions [Source: biology_notes.pdf, p. 3, sec: Light Reactions]."
        )
        citations = verifier.extract_citations(text)
        assert len(citations) == 2
        assert citations[0].source == "biology_notes.pdf"
        assert citations[0].page == 2
        assert "Photosynthesis converts light into glucose" in citations[0].claim
        assert citations[1].page == 3
        assert citations[1].section_title == "Light Reactions"

    def test_verify_turn_valid_grounded_citation(self, verifier):
        text = "Photosynthesis converts solar energy into chemical energy [Source: biology_notes.pdf, p. 2]."
        chunks = [
            RetrievedChunk(
                content="Photosynthesis converts solar energy into chemical energy stored in glucose molecules.",
                source="biology_notes.pdf",
                page=2,
                score=0.9,
                document_id="doc_bio_1",
            )
        ]
        res = verifier.verify_turn(text, student_id="student_1", retrieved_chunks=chunks)
        assert res.all_valid is True
        assert res.citation_correctness == 1.0
        assert res.unsupported_claim_count == 0
        assert len(res.citations) == 1
        assert res.citations[0].ownership_verified is True
        assert res.citations[0].page_verified is True
        assert res.citations[0].support_score >= 0.40

    def test_verify_turn_rejects_cross_student_document(self, verifier):
        # Student references a document they don't own (e.g. physics_secret.pdf)
        text = "The speed of light is 3e8 m/s [Source: physics_secret.pdf, p. 1]."
        chunks = [
            RetrievedChunk(
                content="The speed of light is constant.", source="physics_secret.pdf", page=1
            )
        ]

        res = verifier.verify_turn(text, student_id="student_1", retrieved_chunks=chunks)
        assert res.all_valid is False
        assert res.citation_correctness == 0.0
        assert res.citations[0].ownership_verified is False
        assert "does not belong to student" in res.citations[0].reason

    def test_verify_turn_detects_unsupported_claim(self, verifier):
        # Citation points to a valid file and page, but claim text is completely unrelated to passage
        text = "Dinosaurs built advanced space rockets [Source: biology_notes.pdf, p. 2]."
        chunks = [
            RetrievedChunk(
                content="Photosynthesis occurs inside chloroplasts using chlorophyll pigments.",
                source="biology_notes.pdf",
                page=2,
                score=0.9,
                document_id="doc_bio_1",
            )
        ]
        res = verifier.verify_turn(text, student_id="student_1", retrieved_chunks=chunks)
        assert res.all_valid is False
        assert res.unsupported_claim_count == 1
        assert res.citations[0].is_valid is False
        assert "lacks sufficient grounding" in res.citations[0].reason
