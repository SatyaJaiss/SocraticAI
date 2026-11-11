"""FastAPI application entry point for SocraticAI.

The app is a thin HTTP layer over the LangGraph workflows and the services
layer. Dependency injection flows through :func:`app.core.dependencies.get_ctx` so
tests can swap the container without touching the route logic.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.services.container import get_container

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

    # Map the SocraticAIError tree to HTTP responses.
    register_exception_handlers(app)

    # Mount API v1 router
    app.include_router(api_v1_router)

    return app


app = create_app()

