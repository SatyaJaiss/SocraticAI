"""Unit tests for CrossEncoder reranker and graceful fallback."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import RerankerSettings
from app.rag.retrieval.reranker import CrossEncoderReranker
from app.schemas.domain import RetrievedChunk


class TestCrossEncoderReranker:
    def test_disabled_reranker_returns_original_slice(self):
        settings = RerankerSettings(enabled=False, top_k=2)
        reranker = CrossEncoderReranker(settings)
        chunks = [
            RetrievedChunk(content="C1", source="s1", score=0.9),
            RetrievedChunk(content="C2", source="s2", score=0.8),
            RetrievedChunk(content="C3", source="s3", score=0.7),
        ]
        res = reranker.rerank("query", chunks, top_k=2)
        assert len(res) == 2
        assert res[0].content == "C1"
        assert res[1].content == "C2"

    def test_reranker_reorders_by_neural_scores(self):
        settings = RerankerSettings(enabled=True, top_k=2)
        reranker = CrossEncoderReranker(settings)

        # Mock model predict
        mock_model = MagicMock()
        # Predict returns score 0.2 for first chunk and 0.9 for second chunk
        mock_model.predict.return_value = [0.2, 0.9]
        reranker._model = mock_model
        reranker._loaded = True

        chunks = [
            RetrievedChunk(content="Irrelevant text", source="s1", score=0.8),
            RetrievedChunk(content="Highly relevant text", source="s2", score=0.4),
        ]
        res = reranker.rerank("query", chunks)

        assert len(res) == 2
        assert res[0].content == "Highly relevant text"
        assert res[0].reranker_score == 0.9
        assert res[1].content == "Irrelevant text"
        assert res[1].reranker_score == 0.2

    def test_reranker_graceful_fallback_on_exception(self):
        settings = RerankerSettings(enabled=True, top_k=2)
        reranker = CrossEncoderReranker(settings)

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("CUDA OOM")
        reranker._model = mock_model
        reranker._loaded = True

        chunks = [
            RetrievedChunk(content="Original 1", source="s1", score=0.9),
            RetrievedChunk(content="Original 2", source="s2", score=0.8),
        ]
        res = reranker.rerank("query", chunks)
        # Should gracefully return original candidates without crashing
        assert len(res) == 2
        assert res[0].content == "Original 1"
