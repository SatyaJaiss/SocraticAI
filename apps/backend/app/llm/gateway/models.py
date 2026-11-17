"""Data models and responses for TensorZero gateway integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GatewayInferenceResult(BaseModel):
    """Normalized inference result returned by the TensorZero gateway."""

    text: str
    raw_response: Any | None = None
    provider: str = "tensorzero"
    model: str = "default"
    latency_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
