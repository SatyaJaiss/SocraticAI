"""FastAPI application entry point for SocraticAI.

The app is a thin HTTP layer over the LangGraph workflows and the services
layer. Dependency injection flows through :func:`app.core.dependencies.get_ctx` so
tests can swap the container without touching the route logic.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.services.container import get_container
from app.telemetry.metrics import (
    HTTP_REQUESTS_IN_PROGRESS,
    get_latest_metrics,
    record_http_request,
)
from app.telemetry.tracing import instrument_fastapi_app, instrument_httpx

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure DB schema exists and pre-compile workflows. Shutdown: release pools."""
    container = get_container()
    if container.settings.database.create_on_startup:
        container.db.create_schema()
    # Pre-compile LangGraph workflows once during startup
    _ = container.tutoring_graph
    _ = container.evaluation_graph
    logger.info("SocraticAI API ready (LLM provider=%s)", container.settings.llm.provider)
    yield
    container.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description=(
            "SocraticAI — an AI tutoring assistant backed by LangGraph, RAG and a "
            "persistent student model."
        ),
        lifespan=lifespan,
    )

    # CORS for the Streamlit frontend.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # HTTP Metrics Middleware
    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        endpoint = request.url.path
        method = request.method
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            record_http_request(method, endpoint, response.status_code, duration)
            return response
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

    # Map the SocraticAIError tree to HTTP responses.
    register_exception_handlers(app)

    # Prometheus metrics exposition endpoint
    if settings.metrics.enabled:
        from fastapi.responses import Response

        @app.get(settings.metrics.endpoint, include_in_schema=False)
        def prometheus_metrics() -> Response:
            data, content_type = get_latest_metrics()
            return Response(content=data, media_type=content_type)

    # OpenTelemetry distributed tracing instrumentation
    if settings.telemetry.enabled:
        instrument_fastapi_app(app)
        instrument_httpx()

    # Mount API v1 router
    app.include_router(api_v1_router)

    return app


app = create_app()
