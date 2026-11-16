"""Advanced RAG service orchestrating dense, lexical, hybrid, reranking, and relevance evaluation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.config import Settings, VectorStoreSettings, get_settings
from app.core.exceptions import RetrievalError
from app.decision.composite import CompositeDecisionProvider
from app.decision.relevance_grader import RetrievalRelevanceGrader
from app.rag.retrieval.bm25 import BM25Index
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.query_processor import QueryProcessor
from app.rag.retrieval.reranker import CrossEncoderReranker
from app.rag.retrieval.vector_store import VectorStore
from app.schemas.domain import RAGContext, RetrievedChunk
from app.utils.helpers import truncate

if TYPE_CHECKING:
    from app.cache.manager import CacheManager

logger = logging.getLogger(__name__)


class RAGService:
    """Enterprise RAG coordinator with Hybrid RRF, Cross-Encoder reranking, and decision grading."""

    def __init__(
        self,
        settings: VectorStoreSettings | None = None,
        vector_store: VectorStore | None = None,
        bm25_index: BM25Index | None = None,
        hybrid_retriever: HybridRetriever | None = None,
        reranker: CrossEncoderReranker | None = None,
        relevance_grader: RetrievalRelevanceGrader | None = None,
        query_processor: QueryProcessor | None = None,
        cache_manager: CacheManager | None = None,
        full_settings: Settings | None = None,
    ) -> None:
        cfg = full_settings or get_settings()
        self._settings = settings or cfg.vector_store
        self._full_settings = cfg
        self._cache = cache_manager

        # 1. Dense Vector Store
        self._store = vector_store or VectorStore(self._settings, cache_manager=cache_manager)

        # 2. BM25 Lexical Index
        self._bm25 = bm25_index or BM25Index(cfg.bm25)

        # 3. Hybrid Retriever with Reciprocal Rank Fusion
        self._hybrid = hybrid_retriever or HybridRetriever(
            vector_store=self._store,
            bm25_index=self._bm25,
            settings=cfg.hybrid,
        )

        # 4. Cross-Encoder Neural Reranker
        self._reranker = reranker or CrossEncoderReranker(cfg.reranker)

        # 5. Query Processor
        self._query_processor = query_processor or QueryProcessor(cfg.query_rewrite)

        # 6. Decision Model Relevance Grader
        if relevance_grader:
            self._relevance_grader = relevance_grader
        else:
            decision_provider = CompositeDecisionProvider(cfg.decision)
            self._relevance_grader = RetrievalRelevanceGrader(decision_provider, cfg.decision)

    # ------------------------------------------------------------- ingest --
    def ingest_chunks(self, doc_id: str, chunks: list[dict[str, Any]], student_id: str = "") -> int:
        """Persist chunks into both dense vector store and BM25 lexical index."""
        source = chunks[0].get("source", doc_id) if chunks else doc_id

        # 1. Dense indexing
        dense_count = self._store.add_document(doc_id, chunks, source=source, student_id=student_id)

        # 2. Lexical indexing
        self._bm25.add_document(doc_id, student_id, chunks)

        # 3. Cache purge for student
        if self._cache:
            self._cache.invalidate_student_retrieval(student_id)

        logger.info(
            "RAGService ingested document %s (%d chunks) for student %s into VectorStore + BM25",
            doc_id,
            dense_count,
            student_id or "unassigned",
        )
        return dense_count

    def delete_document(self, doc_id: str, student_id: str = "") -> None:
        """Delete document from both dense vector store and BM25 index."""
        self._store.delete_document(doc_id)
        if student_id:
            self._bm25.delete_document(doc_id, student_id)
        if self._cache:
            self._cache.invalidate_student_retrieval(student_id)

    # ------------------------------------------------------------ search --
    def search(
        self,
        query: str,
        top_k: int | None = None,
        student_id: str | None = None,
        *,
        mode: str | None = None,
        rerank: bool | None = None,
    ) -> list[RetrievedChunk]:
        """Search across course documents using hybrid RRF, optional reranking and relevance gating."""
        if not query.strip():
            return []

        top_k_val = top_k or self._settings.top_k
        search_mode = mode or ("hybrid" if self._full_settings.hybrid.enabled else "dense")
        should_rerank = self._full_settings.reranker.enabled if rerank is None else rerank

        # Check Cache
        cache_key_extra = f"{search_mode}:rerank={should_rerank}"
        if self._cache:
            cached = self._cache.get_retrieval(
                student_id or "",
                f"{query}::{cache_key_extra}",
                top_k_val,
                self._settings.collection_name,
            )
            if cached is not None:
                logger.debug(
                    "RAG retrieval cache hit for %r (student=%s)",
                    truncate(query, 80),
                    student_id or "all",
                )
                return cached

        # Query decomposition
        plan = self._query_processor.process(query)

        # Execute retrieval for each subquery (or single query)
        all_candidates: list[RetrievedChunk] = []
        seen_ids: set[str] = set()

        for sq in plan.subqueries:
            sub_results = self._hybrid.search(
                sq,
                student_id=student_id,
                top_k=top_k_val * 2 if should_rerank else top_k_val,
                mode=search_mode,
            )
            for c in sub_results:
                cid = c.chunk_id or f"{c.document_id}::{c.page}::{hash(c.content)}"
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_candidates.append(c)

        # Sort combined subquery candidates
        all_candidates.sort(key=lambda x: x.score, reverse=True)

        # Cross-Encoder Reranking
        final_chunks = all_candidates
        if should_rerank and all_candidates:
            final_chunks = self._reranker.rerank(query, all_candidates, top_k=top_k_val)
        else:
            final_chunks = all_candidates[:top_k_val]

        # Update Cache
        if self._cache:
            self._cache.set_retrieval(
                student_id or "",
                f"{query}::{cache_key_extra}",
                top_k_val,
                self._settings.collection_name,
                final_chunks,
            )

        logger.debug(
            "RAG search for %r (student=%s, mode=%s, rerank=%s) returned %d chunks",
            truncate(query, 80),
            student_id or "all",
            search_mode,
            should_rerank,
            len(final_chunks),
        )
        return final_chunks

    def build_context(
        self,
        query: str,
        top_k: int | None = None,
        student_id: str | None = None,
        *,
        mode: str | None = None,
        rerank: bool | None = None,
    ) -> RAGContext:
        """Return a :class:`RAGContext` with retrieved chunks (possibly empty)."""
        try:
            chunks = self.search(
                query, top_k=top_k, student_id=student_id, mode=mode, rerank=rerank
            )
        except RetrievalError:
            logger.warning(
                "RAG retrieval failed for %r; continuing ungrounded", truncate(query, 80)
            )
            chunks = []
        return RAGContext(retrieved_chunks=chunks, used=bool(chunks))

    # ------------------------------------------------------------- meta ---
    def count(self) -> int:
        return self._store.count()

    def has_document(self, doc_id: str) -> bool:
        return self._store.has_document(doc_id)

    @property
    def settings(self) -> VectorStoreSettings:
        return self._settings

    @property
    def bm25(self) -> BM25Index:
        return self._bm25

    @property
    def hybrid(self) -> HybridRetriever:
        return self._hybrid

    @property
    def reranker(self) -> CrossEncoderReranker:
        return self._reranker

    @property
    def relevance_grader(self) -> RetrievalRelevanceGrader:
        return self._relevance_grader
