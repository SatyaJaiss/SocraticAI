"""Unit tests for TensorZero LLM Gateway client, routing, fallback, and metrics."""

import pytest
from app.core.config import LLMSettings, TensorZeroSettings
from app.llm.clients.client import build_llm_client
from app.llm.gateway.tensorzero_client import TensorZeroGatewayClient
from app.schemas.domain import Explanation


@pytest.mark.asyncio
async def test_tensorzero_gateway_client_fallback_to_demo():
    """Verify that TensorZero client transparently falls back to Demo provider when gateway is offline."""
    base_llm = build_llm_client(LLMSettings(provider="demo"))
    tz_settings = TensorZeroSettings(enabled=False, gateway_url="http://localhost:3000")

    client = TensorZeroGatewayClient(settings=tz_settings, fallback_client=base_llm)

    response = await client.generate(
        system="You are an AI teacher.",
        user="Explain linear regression in simple terms.",
    )

    assert response
    assert isinstance(response, str)
    assert len(response) > 20


@pytest.mark.asyncio
async def test_tensorzero_gateway_client_generate_json():
    """Verify structured JSON generation with schema validation through the gateway client."""
    base_llm = build_llm_client(LLMSettings(provider="demo"))
    tz_settings = TensorZeroSettings(enabled=False)

    client = TensorZeroGatewayClient(settings=tz_settings, fallback_client=base_llm)

    # In demo provider, generate_json formats deterministic valid JSON
    result = await client.generate_json(
        system="Generate an explanation in JSON format.",
        user="Question about derivatives",
        model_class=Explanation,
    )

    assert isinstance(result, Explanation)
    assert result.topic
    assert result.explanation


def test_build_llm_client_returns_tensorzero_when_configured():
    """Verify that build_llm_client returns a TensorZeroGatewayClient when provider is tensorzero."""
    llm_settings = LLMSettings(provider="tensorzero")
    client = build_llm_client(llm_settings)

    assert isinstance(client, TensorZeroGatewayClient)
