"""Benchmark runner executing retrieval configurations A through F across the 100-sample evaluation dataset."""

from __future__ import annotations

import json
import logging
import time
import tracemalloc
from pathlib import Path
from typing import Any

from app.decision.relevance_grader import RetrievalRelevanceGrader
from app.rag.evaluation.metrics import evaluate_retrieval_batch
from app.rag.retrieval.bm25 import BM25Index
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.reranker import CrossEncoderReranker
from app.rag.retrieval.vector_store import VectorStore
from app.schemas.domain import RetrievedChunk

logger = logging.getLogger(__name__)

DATASET_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "rag_evaluation_dataset.json"
)


class RAGBenchmarkRunner:
    """Evaluates and compares retrieval configurations A-F on accuracy, latency, and memory."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        reranker: CrossEncoderReranker,
        relevance_grader: RetrievalRelevanceGrader,
        hybrid_retriever: HybridRetriever,
    ) -> None:
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.reranker = reranker
        self.relevance_grader = relevance_grader
        self.hybrid_retriever = hybrid_retriever
        self.dataset: list[dict[str, Any]] = []

    def load_dataset(self, path: Path | None = None) -> list[dict[str, Any]]:
        target_path = path or DATASET_PATH
        with open(target_path, encoding="utf-8") as f:
            self.dataset = json.load(f)
        return self.dataset

    def seed_benchmark_corpus(self, student_id: str = "eval_student") -> int:
        """Populate the vector store and BM25 index with chunks from the evaluation dataset."""
        if not self.dataset:
            self.load_dataset()

        # Group chunks by document
        doc_chunks: dict[str, list[dict[str, Any]]] = {}
        seen_chunk_ids: set[str] = set()
        chunk_counter = 0

        for item in self.dataset:
            doc_name = item.get("document", "notes.pdf")
            if doc_name == "unrelated":
                continue

            rel_ids = item.get("relevant_chunk_ids") or []
            passages = item.get("expected_passages") or []
            pages = item.get("expected_pages") or [1]

            if not passages:
                continue

            if doc_name not in doc_chunks:
                doc_chunks[doc_name] = []

            for p_idx, text in enumerate(passages):
                cid = rel_ids[p_idx] if p_idx < len(rel_ids) else f"{doc_name}::c{chunk_counter}"
                if cid in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(cid)
                page = pages[p_idx] if p_idx < len(pages) else pages[0]

                chunk_dict = {
                    "text": text,
                    "chunk_id": cid,
                    "doc_id": doc_name,
                    "student_id": student_id,
                    "source": doc_name,
                    "page": page,
                    "section_title": item.get("category", "General"),
                    "section_path": f"{doc_name} > {item.get('category')}",
                    "chunk_index": chunk_counter,
                    "content_hash": f"hash_{cid}",
                }
                doc_chunks[doc_name].append(chunk_dict)
                chunk_counter += 1

        total_seeded = 0
        for doc_name, chunks in doc_chunks.items():
            self.vector_store.add_document(doc_name, chunks, source=doc_name, student_id=student_id)
            self.bm25_index.add_document(doc_name, student_id, chunks)
            total_seeded += len(chunks)

        logger.info(
            "Seeded benchmark corpus with %d passages across %d documents",
            total_seeded,
            len(doc_chunks),
        )
        return total_seeded

    async def run_query_on_config(
        self,
        query: str,
        student_id: str,
        config_name: str,
        top_k: int = 4,
    ) -> list[RetrievedChunk]:
        """Execute query under a specific configuration pipeline (A through F)."""
        # Config A: Dense-only
        if config_name == "A":
            return self.vector_store.search(query, top_k=top_k, student_id=student_id)

        # Config B: BM25-only
        if config_name == "B":
            return self.bm25_index.search(query, student_id=student_id, top_k=top_k)

        # Config C: Hybrid RRF
        if config_name == "C":
            return self.hybrid_retriever.search(
                query, student_id=student_id, top_k=top_k, mode="hybrid"
            )

        # Config D: Hybrid + Cross-Encoder
        if config_name == "D":
            candidates = self.hybrid_retriever.search(
                query, student_id=student_id, top_k=top_k * 2, mode="hybrid"
            )
            return self.reranker.rerank(query, candidates, top_k=top_k)

        # Config E: Hybrid + Decision-Model Relevance Grading
        if config_name == "E":
            candidates = self.hybrid_retriever.search(
                query, student_id=student_id, top_k=top_k, mode="hybrid"
            )
            return await self.relevance_grader.grade_candidates(
                query, candidates, gate_irrelevant=False
            )

        # Config F: Hybrid + Cross-Encoder + Decision-Model Gate
        if config_name == "F":
            candidates = self.hybrid_retriever.search(
                query, student_id=student_id, top_k=top_k * 2, mode="hybrid"
            )
            reranked = self.reranker.rerank(query, candidates, top_k=top_k)
            return await self.relevance_grader.grade_candidates(
                query, reranked, gate_irrelevant=True
            )

        raise ValueError(f"Unknown retrieval configuration: {config_name}")

    async def evaluate_configuration(
        self,
        config_name: str,
        student_id: str = "eval_student",
        top_k: int = 4,
    ) -> dict[str, Any]:
        """Run all dataset queries against a configuration and calculate IR and performance metrics."""
        if not self.dataset:
            self.load_dataset()

        retrieved_ids_batch: list[list[str]] = []
        ground_truth_batch: list[list[str]] = []
        latencies: list[float] = []

        tracemalloc.start()
        start_wall = time.perf_counter()

        for item in self.dataset:
            query = item["query"]
            gt_ids = item.get("relevant_chunk_ids") or []

            t0 = time.perf_counter()
            chunks = await self.run_query_on_config(query, student_id, config_name, top_k=top_k)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            latencies.append(elapsed_ms)
            retrieved_ids_batch.append([c.chunk_id or "" for c in chunks])
            ground_truth_batch.append(gt_ids)

        total_wall_s = time.perf_counter() - start_wall
        _current_ram, peak_ram = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Compute IR metrics
        ir_metrics = evaluate_retrieval_batch(retrieved_ids_batch, ground_truth_batch, k=top_k)

        # Latencies
        latencies.sort()
        p50 = latencies[len(latencies) // 2] if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

        throughput = len(self.dataset) / max(total_wall_s, 1e-6)

        return {
            "config": config_name,
            **ir_metrics,
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "throughput_qps": round(throughput, 2),
            "peak_ram_mb": round(peak_ram / (1024 * 1024), 2),
        }
