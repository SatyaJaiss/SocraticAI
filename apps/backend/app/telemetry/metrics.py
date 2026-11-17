"""Prometheus metrics instrumentation for SocraticAI application, LLM gateway, RAG, and guardrails."""

from __future__ import annotations

import logging

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Application HTTP Metrics
# ---------------------------------------------------------------------------
HTTP_REQUESTS_TOTAL = Counter(
    "socraticai_http_requests_total",
    "Total incoming HTTP requests handled by the FastAPI application.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "socraticai_http_request_duration_seconds",
    "Latency of HTTP requests in seconds.",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "socraticai_http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
    ["method", "endpoint"],
)

API_ERRORS_TOTAL = Counter(
    "socraticai_api_errors_total",
    "Count of unhandled or operational API exceptions.",
    ["endpoint", "error_type"],
)

# ---------------------------------------------------------------------------
# 2. LLM Gateway & Inference Metrics (TensorZero)
# ---------------------------------------------------------------------------
LLM_INFERENCE_REQUESTS_TOTAL = Counter(
    "socraticai_llm_inference_requests_total",
    "Total generative LLM inference requests passing through the gateway.",
    ["provider", "model", "function_name"],
)

LLM_GATEWAY_LATENCY_SECONDS = Histogram(
    "socraticai_llm_gateway_latency_seconds",
    "Latency of LLM inference requests across providers in seconds.",
    ["provider", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.5, 5.0, 8.0, 15.0, 30.0],
)

LLM_PROVIDER_FAILURES_TOTAL = Counter(
    "socraticai_llm_provider_failures_total",
    "Number of provider-level errors (rate limits, timeouts, connection drops).",
    ["provider", "error_type"],
)

LLM_FALLBACK_TOTAL = Counter(
    "socraticai_llm_fallback_total",
    "Number of times primary LLM gateway failed and invoked fallback provider.",
    ["reason"],
)

LLM_TOKENS_CONSUMED_TOTAL = Counter(
    "socraticai_llm_tokens_consumed_total",
    "Total token consumption across prompt and completion phases.",
    ["provider", "token_type"],
)

# ---------------------------------------------------------------------------
# 3. RAG & Retrieval Metrics
# ---------------------------------------------------------------------------
RAG_RETRIEVAL_LATENCY_SECONDS = Histogram(
    "socraticai_rag_retrieval_latency_seconds",
    "Latency of document retrieval steps in seconds.",
    ["strategy"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

RAG_RETRIEVED_PASSAGES_COUNT = Histogram(
    "socraticai_rag_retrieved_passages_count",
    "Distribution of retrieved passages count per retrieval query.",
    ["strategy"],
    buckets=[1, 2, 3, 5, 8, 10, 15, 20],
)

RAG_RERANKING_LATENCY_SECONDS = Histogram(
    "socraticai_rag_reranking_latency_seconds",
    "Latency of cross-encoder reranking operations in seconds.",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

RAG_RETRIEVAL_FAILURES_TOTAL = Counter(
    "socraticai_rag_retrieval_failures_total",
    "Total retrieval and vector search failures.",
    ["stage"],
)

# ---------------------------------------------------------------------------
# 4. Guardrails & Security Metrics (NeMo + PII)
# ---------------------------------------------------------------------------
GUARDRAILS_EXECUTIONS_TOTAL = Counter(
    "socraticai_guardrails_executions_total",
    "Number of guardrail evaluations executed.",
    ["rail_type"],
)

GUARDRAILS_BLOCKED_REQUESTS_TOTAL = Counter(
    "socraticai_guardrails_blocked_requests_total",
    "Requests or responses intercepted and blocked by guardrails.",
    ["rail_type", "violation_code"],
)

GUARDRAILS_DURATION_SECONDS = Histogram(
    "socraticai_guardrails_duration_seconds",
    "Latency of guardrail evaluations in seconds.",
    ["rail_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

GUARDRAILS_PII_REDACTED_TOTAL = Counter(
    "socraticai_guardrails_pii_redacted_total",
    "Count of detected and sanitized PII entities by category (no raw values recorded).",
    ["category"],
)


# ---------------------------------------------------------------------------
# Helper Recording Functions
# ---------------------------------------------------------------------------
def record_http_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
    """Record an HTTP request event."""
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)


def record_llm_inference(
    provider: str,
    model: str,
    function_name: str,
    duration: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Record a completed generative LLM inference invocation."""
    LLM_INFERENCE_REQUESTS_TOTAL.labels(
        provider=provider, model=model, function_name=function_name
    ).inc()
    LLM_GATEWAY_LATENCY_SECONDS.labels(provider=provider, model=model).observe(duration)
    if prompt_tokens > 0:
        LLM_TOKENS_CONSUMED_TOTAL.labels(provider=provider, token_type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_CONSUMED_TOTAL.labels(provider=provider, token_type="completion").inc(
            completion_tokens
        )


def record_llm_failure(provider: str, error_type: str) -> None:
    """Record an LLM provider error."""
    LLM_PROVIDER_FAILURES_TOTAL.labels(provider=provider, error_type=error_type).inc()


def record_llm_fallback(reason: str) -> None:
    """Record a fallback to secondary provider."""
    LLM_FALLBACK_TOTAL.labels(reason=reason).inc()


def record_rag_retrieval(strategy: str, duration: float, passages_count: int) -> None:
    """Record a RAG document retrieval event."""
    RAG_RETRIEVAL_LATENCY_SECONDS.labels(strategy=strategy).observe(duration)
    RAG_RETRIEVED_PASSAGES_COUNT.labels(strategy=strategy).observe(passages_count)


def record_guardrail_event(
    rail_type: str, allowed: bool, duration: float, violation_code: str | None = None
) -> None:
    """Record a guardrail evaluation event."""
    GUARDRAILS_EXECUTIONS_TOTAL.labels(rail_type=rail_type).inc()
    GUARDRAILS_DURATION_SECONDS.labels(rail_type=rail_type).observe(duration)
    if not allowed:
        GUARDRAILS_BLOCKED_REQUESTS_TOTAL.labels(
            rail_type=rail_type, violation_code=violation_code or "UNSPECIFIED"
        ).inc()


def record_pii_redaction(category: str) -> None:
    """Increment metric for a detected and sanitized PII entity."""
    GUARDRAILS_PII_REDACTED_TOTAL.labels(category=category).inc()


def get_latest_metrics() -> tuple[bytes, str]:
    """Generate Prometheus exposition format payload and content type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
