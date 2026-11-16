"""Unit tests for BM25 lexical retrieval, tenant isolation, and disk persistence."""

from __future__ import annotations

import pytest
from app.core.config import BM25Settings
from app.rag.retrieval.bm25 import BM25Index, tokenize_text


class TestBM25Index:
    @pytest.fixture
    def bm25(self, tmp_path):
        settings = BM25Settings(
            enabled=True,
            candidate_count=5,
            index_dir=str(tmp_path / "bm25"),
        )
        return BM25Index(settings)

    def test_tokenize_text_preserves_identifiers(self):
        text = "Use torch.nn.CrossEntropyLoss with AdamW(lr=1e-4) on O(n log n) data."
        tokens = tokenize_text(text)
        assert "torch.nn.crossentropyloss" in tokens or "crossentropyloss" in tokens
        assert "adamw" in tokens

    def test_bm25_indexing_and_search(self, bm25):
        student_id = "student_alpha"
        chunks = [
            {
                "text": "The gradient of cross entropy loss is computed via backprop.",
                "chunk_id": "c1",
                "doc_id": "doc1",
                "source": "dl.txt",
                "page": 1,
            },
            {
                "text": "Photosynthesis produces glucose and oxygen from sunlight.",
                "chunk_id": "c2",
                "doc_id": "doc1",
                "source": "dl.txt",
                "page": 2,
            },
            {
                "text": "QuickSort has average complexity O(n log n).",
                "chunk_id": "c3",
                "doc_id": "doc2",
                "source": "algo.txt",
                "page": 1,
            },
        ]
        bm25.add_document("doc1", student_id, chunks[:2])
        bm25.add_document("doc2", student_id, chunks[2:])

        # Search for exact term
        results = bm25.search("gradient backprop", student_id=student_id, top_k=2)
        assert len(results) >= 1
        assert results[0].chunk_id == "c1"
        assert results[0].bm25_score > 0.0

        # Search for exact complexity
        algo_results = bm25.search("QuickSort complexity", student_id=student_id, top_k=2)
        assert len(algo_results) >= 1
        assert algo_results[0].chunk_id == "c3"

    def test_bm25_student_isolation(self, bm25):
        bm25.add_document(
            "doc_a",
            "student_A",
            [
                {
                    "text": "Secret project code is Apollo-11",
                    "chunk_id": "sec_1",
                    "doc_id": "doc_a",
                    "source": "a.txt",
                    "page": 1,
                }
            ],
        )
        bm25.add_document(
            "doc_b",
            "student_B",
            [
                {
                    "text": "Public project notes on biology",
                    "chunk_id": "pub_1",
                    "doc_id": "doc_b",
                    "source": "b.txt",
                    "page": 1,
                }
            ],
        )

        # Student B cannot find Student A's text
        res = bm25.search("Apollo-11", student_id="student_B")
        assert len(res) == 0

        # Student A can find their own
        res_a = bm25.search("Apollo-11", student_id="student_A")
        assert len(res_a) == 1
        assert res_a[0].chunk_id == "sec_1"

    def test_bm25_deletion(self, bm25):
        student_id = "student_del"
        chunks = [
            {
                "text": "Temporary document text here.",
                "chunk_id": "t1",
                "doc_id": "doc_temp",
                "source": "temp.txt",
                "page": 1,
            }
        ]
        bm25.add_document("doc_temp", student_id, chunks)
        assert bm25.count(student_id) == 1

        removed = bm25.delete_document("doc_temp", student_id)
        assert removed == 1
        assert bm25.count(student_id) == 0
        assert len(bm25.search("Temporary", student_id=student_id)) == 0
