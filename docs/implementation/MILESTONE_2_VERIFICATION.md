# SocraticAI — Milestone 2 Verification Report

## Advanced RAG & Retrieval Intelligence: Pre-Implementation Audit & Gap Analysis

**Date:** 2026-11-16  
**Status:** Completed  
**Milestone:** 2  

---

## 1. Executive Summary

This report establishes the baseline architecture of SocraticAI's document ingestion, indexing, retrieval, and context assembly pipelines following the completion of Milestone 1.5. Every architectural component has been verified directly against the source code to identify confirmed limitations, determine required changes, design non-destructive schema migrations, and plan the integration of BM25 lexical search, hybrid Reciprocal Rank Fusion (RRF), Cross-Encoder reranking, and dual decision-model relevance evaluation (TypeSafe AI Jev and Google Gemini Decisions API).

---

## 2. Ingestion & Parsing Baseline

### 2.1 Verified Source Paths
- Ingestion endpoint: [`apps/backend/app/api/v1/routes/documents.py`](file:///d:/ML/EduAgent-master/apps/backend/app/api/v1/routes/documents.py)
- Ingestion pipeline: [`apps/backend/app/rag/ingestion/pipeline.py`](file:///d:/ML/EduAgent-master/apps/backend/app/rag/ingestion/pipeline.py)
- Format parsers: PyMuPDF (`fitz`) for PDF, UTF-8 text reader for `.txt` / `.md`.

### 2.2 Verified Behavior & Limitations
1. **Unstructured Parsing:**
   - Plain text and Markdown files are ingested as a single monolithic page (`(1, text)`), discarding Markdown headers (`#`, `##`, `###`), list boundaries, and code blocks.
   - PDF extraction via `page.get_text("text")` extracts raw string flow without extracting document table of contents (TOC), structural headings, or font-size cues.
2. **Duplicate Uploads:**
   - Uploading an identical document generates a new UUID `doc_id` and duplicates chunks and embeddings into ChromaDB. There is no content hashing (`content_hash = sha256(content)`) to detect identical files.
3. **Memory Footprint:**
   - Files are accumulated in memory buffers during streaming before writing to temporary files.
4. **Metadata Preservation:**
   - The pipeline only tags chunks with `{"text", "page", "source"}`. It lacks structured metadata: `document_title`, `section_title`, `section_path`, `chunk_id`, `chunk_index`, `content_hash`, and timestamps.

---

## 3. Chunking Strategy Baseline

### 3.1 Verified Source Paths
- Chunker: [`apps/backend/app/rag/chunking/chunker.py`](file:///d:/ML/EduAgent-master/apps/backend/app/rag/chunking/chunker.py)

### 3.2 Verified Behavior & Limitations
1. **Naive Sliding Window:**
   - `chunk_text` slices text strictly on token boundaries using `tiktoken` BPE tokens (`cl100k_base`) with a fixed token overlap (default: 600 tokens, 100 overlap).
   - Semantic units (theorems, definitions, multi-line equations, paragraphs) are sliced arbitrarily across chunk seams.
2. **Missing Section Hierarchy:**
   - Chunks possess no awareness of their parent section, heading level, or breadcrumbs (e.g., `["Chapter 3: Thermodynamics", "Section 3.2: Entropy"]`).
3. **Missing Stable Identifiers:**
   - Chunk IDs in ChromaDB are formatted simply as `"{doc_id}::{chunk_index}"` without hashing chunk contents, making cross-system identification (e.g. BM25 vs Vector) dependent on sequential index order.

---

## 4. Retrieval & Search Baseline

### 4.1 Verified Source Paths
- Vector store: [`apps/backend/app/rag/retrieval/vector_store.py`](file:///d:/ML/EduAgent-master/apps/backend/app/rag/retrieval/vector_store.py)
- RAG service: [`apps/backend/app/rag/pipelines/service.py`](file:///d:/ML/EduAgent-master/apps/backend/app/rag/pipelines/service.py)
- Domain models: [`apps/backend/app/schemas/domain.py`](file:///d:/ML/EduAgent-master/apps/backend/app/schemas/domain.py)

### 4.2 Verified Behavior & Limitations
1. **Dense-Only Retrieval:**
   - Retrieval relies solely on dense embeddings (`sentence-transformers/all-MiniLM-L6-v2` or ChromaDB ONNX fallback).
   - Fails on exact technical identifiers, chemical formulas, variable names, specific acronyms, and equations (e.g., `O(n log n)`, `torch.nn.CrossEntropyLoss`, `H2SO4`).
2. **Absence of Lexical Search (BM25):**
   - No BM25 indexing exists.
3. **No Candidate Reranking:**
   - Raw cosine similarity scores from ChromaDB directly dictate the top-$k$ returned passages without cross-encoder reranking.
4. **No Query Preprocessing or Decomposition:**
   - Complex compound student questions (e.g., "Compare mitosis and meiosis and give examples of each") are passed as a single string to vector similarity search, which dilutes the embedding representation.

---

## 5. Decision-Model Integration Baseline

### 5.1 Verified Source Paths
- Jev adapter: [`apps/backend/app/routing/jev_client.py`](file:///d:/ML/EduAgent-master/apps/backend/app/routing/jev_client.py)

### 5.2 Verified Behavior & Limitations
1. **Single-Provider Coupling:**
   - Jev is wired specifically for high-level intent classification in the router.
2. **Missing Gemini Decisions API Provider:**
   - Google's Gemini Decisions API (`gemini-decision-1` via `google-genai` v1beta) is not integrated.
3. **Absence of Shared Decision Abstraction:**
   - There is no unified `DecisionProvider` interface with support for choice selection, noul (binary) decisions, rubric scoring, provider fallback, and shadow evaluation mode.
4. **No Retrieval Relevance Grading:**
   - Retrieved chunks are directly sent to downstream agent prompts without a relevance evaluation gate.

---

## 6. Citation & Answer Grounding Baseline

### 6.1 Verified Source Paths
- Teacher Agent: [`apps/backend/app/agents/teacher/agent.py`](file:///d:/ML/EduAgent-master/apps/backend/app/agents/teacher/agent.py)
- RAG Agent: [`apps/backend/app/agents/rag/agent.py`](file:///d:/ML/EduAgent-master/apps/backend/app/agents/rag/agent.py)
- Base Agent Helpers: [`apps/backend/app/agents/base.py`](file:///d:/ML/EduAgent-master/apps/backend/app/agents/base.py)

### 6.2 Verified Behavior & Limitations
1. **Unstructured Prompt Injection:**
   - Chunks are rendered as plain text lines: `[1] Source: filename (p.X)\nContent`.
2. **Unverifiable Output:**
   - LLM responses mention concepts from notes without machine-readable citations (e.g. `[doc_id#p2]`).
3. **Zero Citation Verification:**
   - There is no mechanism to verify whether citations are real, whether the page exists, whether the document belongs to the student, and whether the cited text actually supports the generated claims.

---

## 7. Proposed Architectural Changes for Milestone 2

### 7.1 Enhanced Document Ingestion & Section-Aware Chunking
- Introduce `StructuredDocumentParser` supporting Markdown heading tree extraction and PDF table of contents / font-based heading discovery.
- Implement `SectionAwareChunker` that respects heading hierarchies, section titles, paragraphs, and sentence boundaries before chunking.
- Expand chunk metadata to include `chunk_id`, `document_id`, `student_id`, `document_title`, `page_number`, `section_title`, `section_path`, `chunk_index`, `content_hash`, and `created_at`.
- Add duplicate file detection via SHA-256 content hashing in `document_repo`.

### 7.2 BM25 Lexical Retrieval & Hybrid Search (RRF)
- Implement `BM25Index` using `rank-bm25` with disk serialization, per-student index isolation, incremental document addition, and deletion.
- Implement `HybridRetriever` combining dense vector candidates and BM25 lexical candidates using Reciprocal Rank Fusion:
  $$RRF\_score(d) = \sum_{i \in \{\text{dense}, \text{bm25}\}} \frac{1}{k + \text{rank}_i(d)}$$
- Retain dense-only and BM25-only retrieval as configurable baselines.

### 7.3 Cross-Encoder Reranking
- Implement `CrossEncoderReranker` using `sentence-transformers` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) with bounded candidate input, CPU/GPU detection, and graceful fallback.
- Benchmark recall, MRR, nDCG@K, latency, and memory utilization across retrieval configurations.

### 7.4 Unified Decision-Provider Framework & Gemini Decisions API
- Design `BaseDecisionProvider` contract (`choose`, `evaluate`, `score`).
- Implement:
  1. `JevDecisionProvider` (TypeSafe AI Jev System One).
  2. `GeminiDecisionsProvider` (`google-genai` SDK v1beta, model `gemini-decision-1`).
  3. `ShadowDecisionProvider` for side-by-side evaluation and agreement scoring.
  4. `FallbackDecisionProvider` for automated failover.
- Implement retrieval relevance grading to score candidate passages against user queries and filter out irrelevant passages before context assembly.

### 7.5 Query Rewriting & Decomposition
- Implement `QueryProcessor` with deterministic intent detection for simple queries and lightweight decomposition for multi-part comparative queries.

### 7.6 Citation Generation & Verification Pipeline
- Standardize citation format: `[Source: {filename}, p. {page}]` and structured citation metadata.
- Implement `CitationVerifier` with two validation phases:
  1. Deterministic verification (verifying source document ID, ownership, and page existence).
  2. Semantic support verification (verifying claim groundedness against the cited passage).

---

## 8. Schema Migrations & Compatibility Plan

### 8.1 SQLite Schema Compatibility
- The `documents` table will gain an optional `content_hash` string column (with index) to support duplicate file detection without requiring a destructive migration.
- New ORM model `DocumentCitationRecord` (if needed for audit logging) will be declared non-destructively.

### 8.2 ChromaDB Collection Compatibility
- Existing collections will continue to work seamlessly; new metadata fields (`section_title`, `chunk_id`, `content_hash`) will be added to newly ingested chunks alongside existing fields (`doc_id`, `student_id`, `source`, `page`).

### 8.3 Domain Models Compatibility
- Update `RetrievedChunk` in `apps/backend/app/schemas/domain.py` with optional default fields:
  ```python
  class RetrievedChunk(BaseModel):
      content: str
      source: str
      page: int | None = None
      score: float = 0.0
      chunk_id: str | None = None
      document_id: str | None = None
      student_id: str | None = None
      section_title: str | None = None
      section_path: str | None = None
      chunk_index: int | None = None
      content_hash: str | None = None
  ```
  All existing callers will remain 100% backward-compatible.

---

## 9. Dependency Additions

| Package | Version | Purpose |
|---|---|---|
| `rank-bm25` | `^0.2.2` | In-memory and disk-persisted BM25 lexical indexing with student isolation. |
| `google-genai` | `^3.3.0` | Google Gemini Decisions API integration (`gemini-decision-1`). |

Both packages have been verified and installed in `.venv`.

---

## 10. Conclusion

No fundamental architectural conflicts or destructive migrations were identified. Proceeding with the implementation of Milestone 2 according to the technical plan.
