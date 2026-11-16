"""Document ingestion: extract text, chunk it, and produce store-ready chunks.

Supported formats: PDF (via PyMuPDF/fitz), plain text and Markdown. Each chunk
carries ``{"text", "page", "source"}`` alongside rich section metadata so the
vector store and BM25 index can attach accurate citations (page numbers, section path)
and the RAG agent can cite sources.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import SUPPORTED_DOCUMENT_EXTENSIONS
from app.core.exceptions import IngestionError
from app.rag.chunking.chunker import chunk_document_pages
from app.utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)


def _read_pdf_with_metadata(path: Path) -> tuple[list[tuple[int, str]], str, list[dict[str, Any]]]:
    """Return ``([(page_number, text), ...], doc_title, toc)`` for a PDF, skipping blank pages."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dependency guaranteed
        raise IngestionError("PyMuPDF is not installed; cannot extract PDF text") from exc
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise IngestionError(f"Could not open PDF {path.name}: {exc}") from exc

    pages: list[tuple[int, str]] = []
    toc: list[dict[str, Any]] = []
    doc_title = ""

    try:
        # Extract title from metadata if available
        meta = document.metadata or {}
        doc_title = str(meta.get("title") or "").strip()

        # Extract TOC if available: [[lvl, title, page], ...]
        raw_toc = document.get_toc() or []
        for entry in raw_toc:
            if len(entry) >= 3:
                toc.append({"level": entry[0], "title": str(entry[1]), "page": int(entry[2])})

        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")
            if text and text.strip():
                pages.append((page_number, text))
    finally:
        document.close()
    return pages, doc_title, toc


def _read_plain(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise IngestionError(f"Could not read {path.name}: {exc}") from exc


def extract_pages(path: str | Path) -> list[tuple[int, str]]:
    """Extract ``(page_number, text)`` pairs for any supported file.

    Plain text / Markdown files are treated as a single page (tagged with page 1).
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type {suffix!r}; expected one of "
            f"{sorted(SUPPORTED_DOCUMENT_EXTENSIONS)}"
        )
    if suffix == ".pdf":
        pages, _, _ = _read_pdf_with_metadata(file_path)
        if not pages:
            raise IngestionError(f"PDF {file_path.name!r} contains no extractable text")
        return pages
    text = _read_plain(file_path)
    if not text.strip():
        raise IngestionError(f"File {file_path.name!r} is empty")
    return [(1, text)]


def extract_text(path: str | Path) -> str:
    """Return the full extracted text of a supported document as one string.

    Convenience wrapper over :func:`extract_pages` used by the RAG package
    ``__init__``; raises :class:`IngestionError` for unsupported/empty files.
    """
    pages = extract_pages(path)
    return "\n\n".join(text.strip() for _, text in pages).strip()


def ingest_document(
    path: str | Path,
    *,
    source: str | None = None,
    doc_id: str = "",
    student_id: str = "",
    document_title: str | None = None,
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> list[dict]:
    """Chunk a supported document into store-ready ``{text, page, source, ...}`` dicts.

    Raises :class:`IngestionError` for unsupported/empty files.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise IngestionError(f"File {file_path!r} does not exist")
    source = source or sanitize_filename(file_path.name)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        pages, pdf_title, toc = _read_pdf_with_metadata(file_path)
        if not pages:
            raise IngestionError(f"PDF {file_path.name!r} contains no extractable text")
        title = document_title or pdf_title or source
    else:
        text = _read_plain(file_path)
        if not text.strip():
            raise IngestionError(f"File {file_path.name!r} is empty")
        pages = [(1, text)]
        toc = []
        title = document_title or source

    chunks = chunk_document_pages(
        pages,
        chunk_size=chunk_size,
        overlap=chunk_overlap,
        source=source,
        doc_id=doc_id,
        student_id=student_id,
        document_title=title,
        toc=toc,
    )
    logger.info("Ingested %s -> %d chunks (title=%r)", file_path.name, len(chunks), title)
    return chunks
