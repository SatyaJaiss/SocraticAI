"""Unit tests for section-aware chunking, stable IDs, and rich metadata."""

from __future__ import annotations

from app.rag.chunking.chunker import (
    SectionAwareChunker,
    chunk_document_pages,
    chunk_text,
    count_tokens,
)


class TestSectionAwareChunker:
    def test_count_tokens_non_empty(self):
        text = "Deep learning uses neural networks with multiple layers."
        tokens = count_tokens(text)
        assert tokens > 0

    def test_chunk_text_bounds_and_overlap(self):
        text = "Word " * 200
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) > 1
        assert all(len(c.strip()) > 0 for c in chunks)

    def test_markdown_heading_extraction(self):
        md = (
            "# Introduction to Biology\n\n"
            "Biology is the study of life.\n\n"
            "## Photosynthesis\n\n"
            "Plants convert sunlight to glucose.\n\n"
            "### Light Reactions\n\n"
            "Thylakoid membranes capture photons.\n"
        )
        chunker = SectionAwareChunker(chunk_size=100, chunk_overlap=20)
        sections = chunker.extract_markdown_sections(md, page=1)

        assert len(sections) == 3
        assert sections[0].title == "Introduction to Biology"
        assert sections[1].title == "Photosynthesis"
        assert sections[2].title == "Light Reactions"
        assert "Introduction to Biology > Photosynthesis > Light Reactions" in sections[2].path

    def test_chunk_document_pages_metadata_preservation(self):
        pages = [
            (1, "# Chapter 1: Physics\n\nNewton's first law of motion states inertia."),
            (2, "## Section 1.2: Gravity\n\nGravity exerts downward force proportional to mass."),
        ]
        chunks = chunk_document_pages(
            pages,
            chunk_size=50,
            overlap=10,
            source="physics.md",
            doc_id="doc_phys_1",
            student_id="student_123",
            document_title="AP Physics Notes",
        )

        assert len(chunks) >= 2
        first = chunks[0]
        assert first["doc_id"] == "doc_phys_1"
        assert first["student_id"] == "student_123"
        assert first["source"] == "physics.md"
        assert first["document_title"] == "AP Physics Notes"
        assert first["chunk_id"].startswith("doc_phys_1::c")
        assert "content_hash" in first
        assert first["page"] in [1, 2]

    def test_stable_chunk_identifiers(self):
        pages = [(1, "Deterministic chunking content text repeated.")]
        c1 = chunk_document_pages(pages, source="doc.txt", doc_id="d1", student_id="s1")
        c2 = chunk_document_pages(pages, source="doc.txt", doc_id="d1", student_id="s1")

        assert c1[0]["chunk_id"] == c2[0]["chunk_id"]
        assert c1[0]["content_hash"] == c2[0]["content_hash"]
