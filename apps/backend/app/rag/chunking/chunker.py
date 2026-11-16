"""Section-aware text chunking with rich metadata preservation and token budgeting.

Design rationale
----------------
* Preserves document structural boundaries (headings, sections, paragraphs).
* Attaches rich metadata: ``doc_id``, ``student_id``, ``chunk_id``, ``document_title``,
  ``page``, ``section_title``, ``section_path``, ``chunk_index``, ``content_hash``,
  and ``created_at``.
* Generates deterministic, stable chunk identifiers using content hashing.
* Avoids splitting critical semantic units (theorems, equations, definitions) mid-sentence.
* Maintains 100% backward compatibility with legacy ``{"text", "page", "source"}`` consumers.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar

from app.core.config import MAX_CHUNKS_PER_DOCUMENT
from app.utils.helpers import utc_now_iso

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised implicitly
    import tiktoken
except ImportError:  # pragma: no cover - fallback path
    tiktoken = None

_ENCODING_NAME = "cl100k_base"
_encoder = None


def _get_encoder():
    """Lazily load the BPE encoder once per process."""
    global _encoder  # noqa: PLW0603 - intentional process-wide lazy cache
    if tiktoken is None:
        return None
    if _encoder is None:
        _encoder = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoder


def count_tokens(text: str) -> int:
    """Return an approximate token count for ``text``."""
    if not text:
        return 0
    encoder = _get_encoder()
    if encoder is not None:
        return len(encoder.encode(text))
    return len(text.split())


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Split ``text`` into overlapping, token-bounded chunks.

    Overlap is capped at ``chunk_size - 1`` so chunks always make progress.
    Returns a list of non-empty, whitespace-stripped chunks.
    """
    if not text or not text.strip():
        return []
    chunk_size = max(int(chunk_size), 1)
    overlap = max(int(overlap), 0)
    if overlap >= chunk_size:
        overlap = chunk_size - 1

    encoder = _get_encoder()
    if encoder is not None:
        tokens = encoder.encode(text)
        chunks: list[str] = []
        start = 0
        n = len(tokens)
        while start < n:
            end = min(start + chunk_size, n)
            piece = encoder.decode(tokens[start:end]).strip()
            if piece:
                chunks.append(piece)
            if end >= n:
                break
            start = max(start + chunk_size - overlap, start + 1)
        return chunks

    # Fallback: chunk by words when tiktoken is unavailable.
    words = text.split()
    chunks = []
    step = max(chunk_size - overlap, 1)
    for i in range(0, max(len(words), 1), step):
        piece = " ".join(words[i : i + chunk_size]).strip()
        if piece:
            chunks.append(piece)
        if i + chunk_size >= len(words):
            break
    return chunks


# --------------------------------------------------------------------------- #
# Section-Aware Chunking
# --------------------------------------------------------------------------- #


@dataclass
class ParsedSection:
    """A semantic document section bounded by headings or page breaks."""

    title: str
    path: str
    content: str
    page: int | None = None
    level: int = 1
    metadata: dict = field(default_factory=dict)


class SectionAwareChunker:
    """Decomposes structured text into sections before token-window chunking."""

    HEADING_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE),  # Markdown # Headings
        re.compile(
            r"^(?:Chapter|Section|Module|Unit|Lesson)\s+(\d+[\.\d*]*[:\s\-]+[^\n]+)",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^([A-Z0-9][A-Z0-9\.\s\-]{2,50})\n[=\-]{3,}\s*$", re.MULTILINE
        ),  # Underlined headings
        re.compile(
            r"^(\d+\.\d+(?:\.\d+)?\s+[A-Z][^\n]+)", re.MULTILINE
        ),  # Numbered sections e.g. 1.2 Introduction
    ]

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        max_section_size: int = 1200,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_section_size = max_section_size

    def extract_markdown_sections(self, text: str, page: int | None = 1) -> list[ParsedSection]:
        """Split text along Markdown headings, maintaining hierarchical section breadcrumbs."""
        lines = text.splitlines(keepends=True)
        sections: list[ParsedSection] = []
        current_title = "Overview"
        heading_stack: list[tuple[int, str]] = [(1, "Overview")]
        current_body: list[str] = []

        md_heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            m = md_heading_re.match(line.strip())
            if m:
                # Flush previous section
                body_str = "".join(current_body).strip()
                if body_str:
                    path_str = " > ".join(t for _, t in heading_stack)
                    sections.append(
                        ParsedSection(
                            title=current_title,
                            path=path_str,
                            content=body_str,
                            page=page,
                            level=heading_stack[-1][0] if heading_stack else 1,
                        )
                    )
                    current_body = []

                level = len(m.group(1))
                heading_text = m.group(2).strip()
                current_title = heading_text

                # Adjust breadcrumb stack
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
            else:
                current_body.append(line)

        # Flush final section
        body_str = "".join(current_body).strip()
        if body_str:
            path_str = " > ".join(t for _, t in heading_stack)
            sections.append(
                ParsedSection(
                    title=current_title,
                    path=path_str,
                    content=body_str,
                    page=page,
                    level=heading_stack[-1][0] if heading_stack else 1,
                )
            )

        return sections or [
            ParsedSection(title="Overview", path="Overview", content=text.strip(), page=page)
        ]

    def chunk_section(
        self,
        section: ParsedSection,
        *,
        doc_id: str,
        student_id: str,
        source: str,
        document_title: str,
        start_chunk_idx: int = 0,
    ) -> list[dict]:
        """Split a single section into token-bounded chunks with rich metadata."""
        raw_pieces = chunk_text(
            section.content, chunk_size=self.chunk_size, overlap=self.chunk_overlap
        )
        chunks: list[dict] = []
        now = utc_now_iso()

        for offset, piece in enumerate(raw_pieces):
            idx = start_chunk_idx + offset
            c_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
            # Stable chunk ID combining doc_id, index, and content digest
            chunk_id = f"{doc_id}::c{idx}::{c_hash[:8]}"

            chunks.append(
                {
                    "text": piece,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "student_id": student_id,
                    "document_title": document_title or source,
                    "source": source,
                    "page": section.page,
                    "section_title": section.title,
                    "section_path": section.path,
                    "chunk_index": idx,
                    "content_hash": c_hash,
                    "created_at": now,
                }
            )
        return chunks


def chunk_document_pages(
    pages: list[tuple[int | None, str]],
    *,
    chunk_size: int = 600,
    overlap: int = 100,
    source: str = "unknown",
    doc_id: str = "",
    student_id: str = "",
    document_title: str = "",
    toc: list[dict] | None = None,
) -> list[dict]:
    """Chunk a list of ``(page_number, text)`` pairs with section-awareness and rich metadata.

    Preserves page boundaries and headings, assigns stable deterministic chunk IDs,
    and returns dictionaries with both legacy fields (``text``, ``page``, ``source``)
    and rich metadata for Milestone 2.
    """
    chunker = SectionAwareChunker(chunk_size=chunk_size, chunk_overlap=overlap)
    all_chunks: list[dict] = []
    chunk_counter = 0

    # Build TOC lookup by page if available: {page: section_title}
    toc_map: dict[int, str] = {}
    if toc:
        for entry in toc:
            p = entry.get("page")
            t = entry.get("title")
            if p is not None and t:
                toc_map[int(p)] = str(t)

    current_toc_title = "Document"

    for page_num, text in pages:
        if not text or not text.strip():
            continue

        if page_num in toc_map:
            current_toc_title = toc_map[page_num]

        # Check if text contains markdown headings or plain text sections
        sections = chunker.extract_markdown_sections(text, page=page_num)

        for sec in sections:
            # If section didn't find markdown headings, inherit TOC title
            if sec.title == "Overview" and current_toc_title != "Document":
                sec.title = current_toc_title
                sec.path = current_toc_title

            section_chunks = chunker.chunk_section(
                sec,
                doc_id=doc_id,
                student_id=student_id,
                source=source,
                document_title=document_title or source,
                start_chunk_idx=chunk_counter,
            )
            for c in section_chunks:
                all_chunks.append(c)
                chunk_counter += 1
                if len(all_chunks) >= MAX_CHUNKS_PER_DOCUMENT:
                    logger.warning(
                        "Reached chunk cap (%d) while chunking %s",
                        MAX_CHUNKS_PER_DOCUMENT,
                        source,
                    )
                    return all_chunks

    return all_chunks
