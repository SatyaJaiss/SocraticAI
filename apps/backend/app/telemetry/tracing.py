"""OpenTelemetry distributed tracing configuration, context propagation, and span instrumentation."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.core.config import TelemetrySettings

logger = logging.getLogger(__name__)

_TRACER: trace.Tracer | None = None
_PROPAGATOR = TraceContextTextMapPropagator()


def setup_telemetry(settings: TelemetrySettings) -> trace.Tracer:
    """Initialize OpenTelemetry tracer provider and exporter."""
    global _TRACER  # noqa: PLW0603

    if not settings.enabled:
        _TRACER = trace.get_tracer("socraticai.noop")
        return _TRACER

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP gRPC span exporter configured for %s", settings.otlp_endpoint)
        except Exception as exc:
            logger.warning("Failed to configure OTLP exporter (%s), falling back to console.", exc)
            if settings.debug_console:
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif settings.debug_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    _TRACER = trace.get_tracer(settings.service_name, settings.service_version)
    logger.info("OpenTelemetry distributed tracing initialized.")
    return _TRACER


def get_tracer() -> trace.Tracer:
    """Return active OpenTelemetry tracer singleton."""
    global _TRACER  # noqa: PLW0603
    if _TRACER is None:
        _TRACER = trace.get_tracer("socraticai")
    return _TRACER


def inject_trace_context(carrier: dict[str, str] | None = None) -> dict[str, str]:
    """Inject current W3C traceparent and tracestate into carrier dictionary."""
    target = carrier if carrier is not None else {}
    _PROPAGATOR.inject(target)
    return target


def extract_trace_context(carrier: dict[str, str]) -> Any:
    """Extract W3C trace context from carrier headers."""
    return _PROPAGATOR.extract(carrier)


@asynccontextmanager
async def async_span_context(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncGenerator[trace.Span, None]:
    """Async context manager creating an OpenTelemetry span with sanitized attributes."""
    tracer = get_tracer()
    safe_attrs = _sanitize_attributes(attributes or {})
    with tracer.start_as_current_span(name, attributes=safe_attrs) as span:
        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(trace.StatusCode.OK)
        except Exception as exc:
            span.set_status(trace.StatusCode.ERROR, description=str(exc))
            span.record_exception(exc)
            raise
        finally:
            span.set_attribute("duration_seconds", time.perf_counter() - start_time)


@contextmanager
def span_context(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[trace.Span, None, None]:
    """Synchronous context manager creating an OpenTelemetry span with sanitized attributes."""
    tracer = get_tracer()
    safe_attrs = _sanitize_attributes(attributes or {})
    with tracer.start_as_current_span(name, attributes=safe_attrs) as span:
        start_time = time.perf_counter()
        try:
            yield span
            span.set_status(trace.StatusCode.OK)
        except Exception as exc:
            span.set_status(trace.StatusCode.ERROR, description=str(exc))
            span.record_exception(exc)
            raise
        finally:
            span.set_attribute("duration_seconds", time.perf_counter() - start_time)


def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Callable:
    """Decorator wrapping an async function in an OpenTelemetry span."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with async_span_context(name, attributes):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def instrument_fastapi_app(app: FastAPI) -> None:
    """Instrument FastAPI application with OpenTelemetry middleware."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="metrics,health,docs,openapi.json,redoc",
        )
        logger.info("FastAPI application instrumented with OpenTelemetry.")
    except Exception as exc:
        logger.warning("Could not instrument FastAPI with OpenTelemetry: %s", exc)


def instrument_httpx() -> None:
    """Instrument HTTPX client calls with OpenTelemetry."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumented with OpenTelemetry.")
    except Exception as exc:
        logger.warning("Could not instrument HTTPX with OpenTelemetry: %s", exc)


def _sanitize_attributes(attrs: dict[str, Any]) -> dict[str, Any]:
    """Ensure no personal identifiable information, passwords, or raw secrets are attached to spans."""
    sanitized: dict[str, Any] = {}
    blocked_keys = {
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
        "email",
        "phone",
        "ssn",
        "credit_card",
        "raw_prompt",
        "user_message",
    }
    for k, v in attrs.items():
        if any(b in k.lower() for b in blocked_keys):
            sanitized[k] = "[REDACTED_SECURITY_ATTRIBUTE]"
        elif isinstance(v, (int, float, bool, str)):
            sanitized[k] = v
        else:
            sanitized[k] = str(v)[:100]
    return sanitized
