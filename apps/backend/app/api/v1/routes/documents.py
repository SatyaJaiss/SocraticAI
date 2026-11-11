"""Document upload, validation, and retrieval endpoints with tenant isolation."""

from __future__ import annotations

import contextlib
import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.config import SUPPORTED_DOCUMENT_EXTENSIONS
from app.core.dependencies import get_container_dep, get_current_student
from app.core.exceptions import (
    AuthorizationError,
    IngestionError,
    PayloadTooLargeError,
    ResourceNotFoundError,
    UnsupportedMediaTypeError,
)
from app.rag.ingestion.pipeline import ingest_document
from app.schemas.domain import StudentProfile
from app.schemas.enums import DocumentStatus
from app.services.container import Container
from app.utils.helpers import generate_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _sanitize_filename(raw_filename: str | None) -> str:
    """Sanitize filename to prevent directory traversal and illegal characters."""
    if not raw_filename:
        return "uploaded_document"
    # Extract only the base name (strips ../ and directory paths)
    base_name = Path(raw_filename).name
    # Retain only safe characters: alphanumerics, dots, underscores, dashes, spaces
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\. ]", "_", base_name).strip()
    return sanitized or "uploaded_document"


def _validate_file_content(content: bytes, ext: str) -> None:
    """Inspect magic bytes and content headers to reject disguised malicious files."""
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise UnsupportedMediaTypeError("Invalid file content: The file does not have a valid PDF header.")
    elif ext in {".txt", ".md"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedMediaTypeError("Invalid text content: File must be UTF-8 encoded text.") from exc


@router.post("/{student_id}")
async def upload_document(
    student_id: str,
    file: UploadFile = File(...),
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict:
    """Upload a document (PDF/TXT/MD), chunk it and index it in ChromaDB with tenant isolation."""
    if student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot upload documents for another student")

    sanitized_filename = _sanitize_filename(file.filename)
    suffix = Path(sanitized_filename).suffix.lower()

    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"File format {suffix!r} is not supported. Permitted extensions: {sorted(SUPPORTED_DOCUMENT_EXTENSIONS)}"
        )

    # 1. Stream file with size ceiling check
    max_size = container.settings.api.max_upload_size_bytes
    chunk_size = 64 * 1024  # 64 KB chunks
    total_read = 0
    buffer = bytearray()

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > max_size:
            max_mb = max_size // (1024 * 1024)
            raise PayloadTooLargeError(
                f"File size exceeds the maximum limit of {max_mb} MB"
            )
        buffer.extend(chunk)

    content = bytes(buffer)
    if not content:
        raise UnsupportedMediaTypeError("Uploaded file is empty")

    # 2. Validate file signatures and encoding
    _validate_file_content(content, suffix)

    doc_id = generate_id("doc")

    # 3. Persist document metadata row
    container.document_repo.create(
        document_id=doc_id,
        student_id=student_id,
        filename=sanitized_filename,
        status=DocumentStatus.UPLOADED.value,
    )

    # 4. Parse document
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        chunks = ingest_document(tmp_path, source=sanitized_filename)
    except IngestionError as exc:
        container.document_repo.update_status(doc_id, DocumentStatus.FAILED.value)
        return {"error": str(exc), "status": "failed"}
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink(missing_ok=True)

    # 5. Ingest into Vector Store with student_id metadata
    chunk_count = container.rag.ingest_chunks(doc_id, chunks, student_id=student_id)
    container.document_repo.update_status(
        doc_id, DocumentStatus.READY.value, chunk_count=chunk_count
    )

    logger.info("Document %s -> %d chunks stored for student %s", doc_id, chunk_count, student_id)
    return {
        "doc_id": doc_id,
        "filename": sanitized_filename,
        "status": "ingested",
        "chunk_count": chunk_count,
    }


@router.get("/{student_id}")
async def list_documents(
    student_id: str,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> list[dict]:
    """List all documents belonging to the authenticated student."""
    if student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot view another student's documents")

    records = container.document_repo.list_for_student(student_id)
    return [
        {
            "doc_id": r.id,
            "filename": r.filename,
            "status": r.status,
            "chunk_count": r.chunk_count,
            "created_at": r.created_at,
        }
        for r in records
    ]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_student: StudentProfile = Depends(get_current_student),
    container: Container = Depends(get_container_dep),
) -> dict:
    """Delete a document and its vector embeddings, validating ownership."""
    record = container.document_repo.get(doc_id)
    if record is None:
        raise ResourceNotFoundError(f"Document {doc_id!r} not found")

    if record.student_id != current_student.student_id:
        raise AuthorizationError("Access denied: You cannot delete another student's document")

    container.rag.delete_document(doc_id, student_id=current_student.student_id)
    container.document_repo.delete(doc_id)
    logger.info("Deleted document %s for student %s", doc_id, current_student.student_id)
    return {"doc_id": doc_id, "status": "deleted"}
