"""Unit tests for OpenTelemetry distributed tracing and Prometheus metrics instrumentation."""

import pytest
from app.core.config import TelemetrySettings
from app.telemetry.metrics import (
    get_latest_metrics,
    record_guardrail_event,
    record_http_request,
    record_llm_fallback,
    record_llm_inference,
    record_pii_redaction,
    record_rag_retrieval,
)
from app.telemetry.tracing import (
    async_span_context,
    extract_trace_context,
    get_tracer,
    inject_trace_context,
    setup_telemetry,
    span_context,
)


def test_telemetry_setup_and_tracer_initialization():
    """Verify tracer provider initialization and tracer retrieval."""
    settings = TelemetrySettings(enabled=True, otlp_endpoint=None)
    tracer = setup_telemetry(settings)

    assert tracer is not None
    assert get_tracer() is not None


def test_w3c_trace_context_propagation():
    """Verify W3C traceparent headers can be injected and extracted across boundaries."""
    carrier: dict[str, str] = {}
    with span_context("test.span"):
        inject_trace_context(carrier)

    # In an active span, W3C traceparent is populated
    assert "traceparent" in carrier
    assert carrier["traceparent"].startswith("00-")

    # Extracting returns context
    extracted = extract_trace_context(carrier)
    assert extracted is not None


@pytest.mark.asyncio
async def test_span_attributes_sanitize_pii_and_secrets():
    """Verify trace attributes automatically sanitize passwords, tokens, emails, and prompts."""
    raw_attributes = {
        "user_email": "sensitive@example.com",
        "api_key": "sk-secret12345678",
        "authorization": "Bearer token123",
        "operation_name": "retrieve_documents",
        "batch_size": 10,
    }

    async with async_span_context("test.sanitized", raw_attributes) as span:
        assert span is not None

    from app.telemetry.tracing import _sanitize_attributes

    sanitized = _sanitize_attributes(raw_attributes)
    assert sanitized["user_email"] == "[REDACTED_SECURITY_ATTRIBUTE]"
    assert sanitized["api_key"] == "[REDACTED_SECURITY_ATTRIBUTE]"
    assert sanitized["authorization"] == "[REDACTED_SECURITY_ATTRIBUTE]"
    assert sanitized["operation_name"] == "retrieve_documents"
    assert sanitized["batch_size"] == 10


def test_prometheus_metrics_recording_and_exposition():
    """Verify Prometheus recording functions increment metrics and format exposition payload."""
    record_http_request("POST", "/api/v1/chat", 200, 0.05)
    record_llm_inference(
        "demo", "demo-tutor", "tutor_chat", 0.02, prompt_tokens=100, completion_tokens=50
    )
    record_llm_fallback("test_timeout")
    record_rag_retrieval("hybrid", 0.015, 4)
    record_guardrail_event(
        "input", allowed=False, duration=0.002, violation_code="PROMPT_INJECTION"
    )
    record_pii_redaction("EMAIL")

    payload, content_type = get_latest_metrics()
    text = payload.decode("utf-8")

    assert "socraticai_http_requests_total" in text
    assert "socraticai_llm_inference_requests_total" in text
    assert "socraticai_llm_fallback_total" in text
    assert "socraticai_rag_retrieval_latency_seconds" in text
    assert "socraticai_guardrails_blocked_requests_total" in text
    assert 'socraticai_guardrails_pii_redacted_total{category="EMAIL"}' in text
    assert "text/plain" in content_type
