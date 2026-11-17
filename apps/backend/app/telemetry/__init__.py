"""Telemetry package providing metrics and distributed tracing."""

from app.telemetry.metrics import (
    get_latest_metrics,
    record_guardrail_event,
    record_http_request,
    record_llm_failure,
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
    instrument_fastapi_app,
    instrument_httpx,
    setup_telemetry,
    span_context,
    trace_span,
)

__all__ = [
    "async_span_context",
    "extract_trace_context",
    "get_latest_metrics",
    "get_tracer",
    "inject_trace_context",
    "instrument_fastapi_app",
    "instrument_httpx",
    "record_guardrail_event",
    "record_http_request",
    "record_llm_failure",
    "record_llm_fallback",
    "record_llm_inference",
    "record_pii_redaction",
    "record_rag_retrieval",
    "setup_telemetry",
    "span_context",
    "trace_span",
]
