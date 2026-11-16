"""RAG (Retrieval-Augmented Generation) package — chunking, embeddings, ingestion, retrieval, and pipelines."""

from __future__ import annotations

from app.rag.chunking.chunker import chunk_text
from app.rag.ingestion.pipeline import ingest_document
from app.rag.pipelines.service import RAGService
from app.rag.retrieval.vector_store import VectorStore

__all__ = [
    "RAGService",
    "VectorStore",
    "chunk_text",
    "ingest_document",
]
