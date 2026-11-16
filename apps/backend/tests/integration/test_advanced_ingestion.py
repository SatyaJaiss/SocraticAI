"""Integration tests for advanced document ingestion, duplicate detection, and lifecycle cleanup."""

from __future__ import annotations

import pytest
from app.core.config import DatabaseSettings, VectorStoreSettings
from app.db.connection import Database
from app.rag.ingestion.pipeline import ingest_document
from app.rag.pipelines.service import RAGService
from app.repositories.document_repository import DocumentRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.enums import DocumentStatus


class TestAdvancedIngestion:
    @pytest.fixture
    def setup_env(self, tmp_path):
        db = Database(DatabaseSettings(url="sqlite:///:memory:"))
        db.create_schema()
        student_repo = StudentRepository(db)
        doc_repo = DocumentRepository(db)

        student_repo.create(
            student_id="student_ingest_1",
            name="Ingest Learner",
            password_hash="hashed_pw_123",
        )

        v_settings = VectorStoreSettings(
            persist_directory=str(tmp_path / "chroma"),
            collection_name="test_advanced_ingest",
        )
        rag_service = RAGService(settings=v_settings)

        return {
            "db": db,
            "student_repo": student_repo,
            "doc_repo": doc_repo,
            "rag": rag_service,
            "tmp_path": tmp_path,
        }

    def test_ingest_structured_markdown_with_sections(self, setup_env):
        tmp_path = setup_env["tmp_path"]
        rag = setup_env["rag"]

        md_file = tmp_path / "thermodynamics.md"
        md_file.write_text(
            "# Chapter 1: Thermodynamics\n\n"
            "Thermodynamics is the branch of physics dealing with heat.\n\n"
            "## Section 1.1: First Law\n\n"
            "Energy can neither be created nor destroyed: Delta U = Q - W.\n\n"
            "## Section 1.2: Second Law\n\n"
            "The total entropy of an isolated system always increases.\n",
            encoding="utf-8",
        )

        chunks = ingest_document(
            md_file,
            doc_id="doc_thermo",
            student_id="student_ingest_1",
            document_title="Thermodynamics Guide",
        )

        assert len(chunks) >= 3
        # Ingest into RAGService (VectorStore + BM25)
        count = rag.ingest_chunks("doc_thermo", chunks, student_id="student_ingest_1")
        assert count == len(chunks)

        # Verify search retrieves with section metadata
        search_res = rag.search("First Law energy Delta U", student_id="student_ingest_1")
        assert len(search_res) >= 1
        assert "First Law" in str(search_res[0].section_title)
        assert search_res[0].document_id == "doc_thermo"

    def test_duplicate_document_handling(self, setup_env):
        doc_repo = setup_env["doc_repo"]
        student_id = "student_ingest_1"
        content_hash = "abc12345hash"

        # Create first record
        doc_repo.create(
            document_id="doc_original",
            student_id=student_id,
            filename="notes.pdf",
            status=DocumentStatus.READY.value,
            content_hash=content_hash,
        )
        doc_repo.update_status("doc_original", DocumentStatus.READY.value, chunk_count=5)

        # Query by content hash
        duplicate = doc_repo.find_by_content_hash(student_id, content_hash)
        assert duplicate is not None
        assert duplicate.id == "doc_original"

    def test_document_deletion_cleans_both_indices(self, setup_env):
        rag = setup_env["rag"]
        student_id = "student_ingest_1"
        chunks = [
            {
                "text": "Unique temporary concept about orbital mechanics.",
                "chunk_id": "c_orbit_1",
                "doc_id": "doc_orbit",
                "source": "orbit.txt",
                "page": 1,
            }
        ]
        rag.ingest_chunks("doc_orbit", chunks, student_id=student_id)
        assert len(rag.search("orbital mechanics", student_id=student_id)) == 1

        # Delete document
        rag.delete_document("doc_orbit", student_id=student_id)

        # Verify document is gone from vector store and BM25 index
        assert len(rag.search("orbital mechanics", student_id=student_id)) == 0
