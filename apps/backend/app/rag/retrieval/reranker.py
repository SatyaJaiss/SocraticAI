"""Cross-Encoder reranking for bounded candidate sets with fallback and resource observability.

Design rationale
----------------
* Bi-encoder dense retrieval & BM25 retrieve high-recall candidate sets quickly.
* Cross-encoder computes all-to-all cross-attention between query and passage,
  providing substantially higher relevance precision.
* Executes only on a bounded candidate set (e.g. top 10-20 items), never the entire index.
* Lazy-loads the neural model only when invoked to preserve system memory.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import RerankerSettings
from app.schemas.domain import RetrievedChunk

logger = logging.getLogger(__name__)

try:
    import torch
    from sentence_transformers import CrossEncoder

    _CROSS_ENCODER_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None
    CrossEncoder = None
    _CROSS_ENCODER_AVAILABLE = False


class CrossEncoderReranker:
    """Neural cross-encoder reranker with automatic device selection and error tolerance."""

    def __init__(self, settings: RerankerSettings) -> None:
        self.settings = settings
        self._model: Any = None
        self._loaded: bool = False

    def _resolve_device(self) -> str:
        """Resolve target device ('cuda', 'cpu') based on settings and environment."""
        req_dev = (self.settings.device or "auto").lower()
        if req_dev == "cuda":
            return "cuda" if (torch and torch.cuda.is_available()) else "cpu"
        if req_dev == "cpu":
            return "cpu"
        # Auto mode
        return "cuda" if (torch and torch.cuda.is_available()) else "cpu"

    def _load_model(self) -> None:
        """Lazy load the CrossEncoder model upon first use."""
        if self._loaded:
            return
        self._loaded = True
        if not _CROSS_ENCODER_AVAILABLE:
            logger.warning("sentence-transformers CrossEncoder is not available; reranker disabled")
            return

        device = self._resolve_device()
        try:
            logger.info(
                "Loading CrossEncoder %s on device=%s (max_length=%d)...",
                self.settings.model_name,
                device,
                self.settings.max_length,
            )
            self._model = CrossEncoder(
                self.settings.model_name,
                max_length=self.settings.max_length,
                device=device,
            )
            logger.info("CrossEncoder %s successfully loaded", self.settings.model_name)
        except Exception as exc:
            logger.error(
                "Failed to load CrossEncoder %s: %s; reranking will be bypassed",
                self.settings.model_name,
                exc,
            )
            self._model = None

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Rerank candidates using cross-attention; falls back to original order on failure."""
        if not self.settings.enabled or not candidates or not query.strip():
            return candidates[: top_k or self.settings.top_k]

        self._load_model()
        if self._model is None:
            return candidates[: top_k or self.settings.top_k]

        # Prepare (query, passage) pairs for the bounded candidate set
        pairs = [[query, c.content] for c in candidates]

        try:
            scores = self._model.predict(
                pairs,
                batch_size=self.settings.batch_size,
                show_progress_bar=False,
            )

            # Attach reranker scores while preserving original scores
            scored_candidates: list[tuple[float, RetrievedChunk]] = []
            for score, chunk in zip(scores, candidates, strict=False):
                chunk.reranker_score = round(float(score), 4)
                chunk.score = chunk.reranker_score
                scored_candidates.append((float(score), chunk))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            k = top_k or self.settings.top_k
            reranked = [c for _, c in scored_candidates[:k]]

            logger.debug(
                "CrossEncoder reranked %d candidates -> returning top %d",
                len(candidates),
                len(reranked),
            )
            return reranked

        except Exception as exc:
            logger.warning(
                "CrossEncoder prediction failed: %s; returning original candidate order", exc
            )
            return candidates[: top_k or self.settings.top_k]
