"""Shared pytest fixtures: isolated settings, DB, container and API client.

Every fixture uses ``tmp_path`` so tests never touch the real ``./data``
directory or the real (env-driven) settings. The LLM is always the offline
``demo`` provider and the vector store always uses :class:`FakeEmbedder`, so the
whole suite is deterministic and needs no API keys or network access.
"""

from __future__ import annotations

import pytest
from app.core.config import (
    ApiSettings,
    AppSettings,
    BM25Settings,
    DatabaseSettings,
    LLMSettings,
    LoggingSettings,
    Settings,
    VectorStoreSettings,
)
from app.db.connection import Database
from app.services.container import Container

from apps.backend.tests.fixtures.fakes import FakeEmbedder


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Fully isolated settings pointed at per-test temp directories."""
    return Settings(
        _env_file=None,
        app=AppSettings(name="test-app", version="0.0.0-test", debug=False),
        llm=LLMSettings(provider="demo"),
        database=DatabaseSettings(
            url=f"sqlite:///{tmp_path / 'test.db'}",
            create_on_startup=True,
        ),
        vector_store=VectorStoreSettings(
            persist_directory=str(tmp_path / "chroma"),
            collection_name="test_notes",
            top_k=4,
            embedding_model="fake",
        ),
        api=ApiSettings(upload_dir=str(tmp_path / "uploads")),
        bm25=BM25Settings(index_dir=str(tmp_path / "bm25")),
        logging=LoggingSettings(log_dir=str(tmp_path / "logs")),
    )


@pytest.fixture
def db(settings) -> Database:
    database = Database(settings.database)
    database.create_schema()
    yield database
    database.dispose()


@pytest.fixture
def container(settings, db, monkeypatch) -> Container:
    """Container wired to the temp DB and a fake embedder."""
    monkeypatch.setattr(
        "app.rag.retrieval.vector_store.get_embedding_provider",
        lambda _settings: FakeEmbedder(),
    )
    c = Container(settings, database=db)
    yield c
    c.dispose()


@pytest.fixture
def ctx(container):
    """The AgentContext the graph nodes receive."""
    return container.context()


@pytest.fixture
def client(container):
    """FastAPI TestClient with the real container injected via overrides."""
    from app.core.dependencies import get_container_dep, get_ctx
    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    app.dependency_overrides[get_container_dep] = lambda: container
    app.dependency_overrides[get_ctx] = container.context
    return TestClient(app)


@pytest.fixture
def auth_header(container):
    """Factory fixture returning an Authorization header dict for any student_id."""
    from app.core.security import create_access_token

    def _make_header(student_id: str = "test_student", name: str = "Learner") -> dict[str, str]:
        container.student_repo.get_or_create(student_id, name=name)
        token = create_access_token(
            subject=student_id,
            secret_key=container.settings.auth.secret_key,
        )
        return {"Authorization": f"Bearer {token}"}

    return _make_header
