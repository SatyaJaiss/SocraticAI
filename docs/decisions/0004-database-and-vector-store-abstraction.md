# ADR 0004: Database and Vector Store Abstraction

## Status
Accepted

## Context
Persistence in SocraticAI (formerly EduAgent) spans two distinct engines:
1. Relational data (SQLAlchemy ORM over SQLite) for students, conversations, quiz records, memories, and progress logs.
2. Vector embeddings (ChromaDB) for document chunks and semantic retrieval.

In the original codebase, database engines were instantiated globally, and `@lru_cache` was applied to `get_db(settings)`. However, Pydantic v2 `BaseSettings` models are mutable and therefore unhashable, causing runtime `TypeError: unhashable type: 'DatabaseSettings'` errors when custom settings objects were passed during testing.

## Decision
1. **Explicit Singleton State:** Replaced unhashable `@lru_cache` decorators in `app.db.connection` and `app.services.container` with thread-safe singleton state variables (`_instance`, `_container_instance`).
2. **Repository Encapsulation:** Kept all SQL operations strictly encapsulated inside `app.repositories.*`, isolating ORM mapping details from agent nodes and API routes.
3. **Modular RAG Pipeline:** Decomposed RAG operations into discrete stages under `app.rag.*`:
   - `chunking`: Token-aware text chunking.
   - `embeddings`: Sentence-transformers and Chroma ONNX embedding providers.
   - `ingestion`: PyMuPDF document extraction and chunk generation.
   - `retrieval`: Vector store search and similarity querying.
   - `pipelines`: End-to-end orchestration service (`RAGService`).

## Consequences
### Positive
- Fully testable in isolation; tests can substitute fakes or in-memory SQLite/vector stores via `conftest.py`.
- Thread-safe singleton access avoids recreating SQLite connection pools on every request.
- Paves the way for future swapping of vector store or relational backends without altering domain logic.

### Negative / Trade-offs
- None; preserves all existing SQLite and ChromaDB behaviors without introducing unnecessary new external dependencies.

