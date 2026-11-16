"""Persistence for uploaded document metadata."""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import ResourceNotFoundError
from app.models.orm import Document
from app.repositories.base_repository import BaseRepository
from app.schemas.domain import DocumentRecord
from app.schemas.enums import DocumentStatus
from app.utils.helpers import utc_now_iso


class DocumentRepository(BaseRepository):
    """CRUD around :class:`Document` lifecycle metadata."""

    # ------------------------------------------------------------ create --
    def create(
        self,
        *,
        document_id: str,
        student_id: str,
        filename: str,
        filepath: str = "",
        status: str = DocumentStatus.UPLOADED.value,
        content_hash: str | None = None,
    ) -> DocumentRecord:
        now = utc_now_iso()
        with self.session() as session:
            row = Document(
                id=document_id,
                student_id=student_id,
                filename=filename,
                filepath=filepath,
                status=status,
                chunk_count=0,
                content_hash=content_hash,
                created_at=now,
            )
            session.add(row)
            session.flush()
        return self._to_record(row)

    # -------------------------------------------------------------- read --
    def get(self, document_id: str) -> DocumentRecord | None:
        with self.session() as session:
            row = session.get(Document, document_id)
            return self._to_record(row) if row else None

    def find_by_content_hash(self, student_id: str, content_hash: str) -> DocumentRecord | None:
        """Find an existing document for this student with matching content hash."""
        with self.session() as session:
            row = (
                session.execute(
                    select(Document).where(
                        Document.student_id == student_id,
                        Document.content_hash == content_hash,
                    )
                )
                .scalars()
                .first()
            )
            return self._to_record(row) if row else None

    def get_or_404(self, document_id: str) -> DocumentRecord:
        record = self.get(document_id)
        if record is None:
            raise ResourceNotFoundError(f"Document {document_id!r} not found")
        return record

    def list_for_student(self, student_id: str, limit: int = 100) -> list[DocumentRecord]:
        with self.session() as session:
            rows = (
                session.execute(
                    select(Document)
                    .where(Document.student_id == student_id)
                    .order_by(Document.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [self._to_record(r) for r in rows]

    def count_for_student(self, student_id: str) -> int:
        with self.session() as session:
            return session.execute(
                select(func.count()).select_from(Document).where(Document.student_id == student_id)
            ).scalar_one()

    # ------------------------------------------------------------ update --
    def update_status(
        self, document_id: str, status: str, *, chunk_count: int | None = None
    ) -> DocumentRecord:
        with self.session() as session:
            row = session.get(Document, document_id)
            if row is None:
                raise ResourceNotFoundError(f"Document {document_id!r} not found")
            row.status = status
            if chunk_count is not None:
                row.chunk_count = chunk_count
            session.flush()
        return self._to_record(row)

    # ------------------------------------------------------------ delete --
    def delete(self, document_id: str) -> None:
        with self.session() as session:
            row = session.get(Document, document_id)
            if row is not None:
                session.delete(row)

    # ---------------------------------------------------------- helpers --
    @staticmethod
    def _to_record(row: Document) -> DocumentRecord:
        return DocumentRecord(
            id=row.id,
            student_id=row.student_id,
            filename=row.filename,
            status=row.status,
            chunk_count=row.chunk_count or 0,
            content_hash=getattr(row, "content_hash", None),
            created_at=row.created_at,
        )
