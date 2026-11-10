"""Database engine + session management.

Design rationale
----------------
* One ``Database`` object owns the SQLAlchemy ``Engine`` and a session factory.
  It is constructed once from settings and injected everywhere — repositories
  and the API never build their own engines.
* ``session()`` is a commit-on-success context manager, so callers are shielded
  from manual ``commit``/``rollback``/``close`` and transactions always resolve.
* SQLite foreign-key enforcement is switched on via a connection event so
  referential integrity holds even on the lightweight default store.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DatabaseSettings
from app.models.orm import Base
from app.utils.helpers import ensure_dir

logger = logging.getLogger(__name__)


class Database:
    """Owns an engine and session factory; exposes a transactional session."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._url = settings.url
        self._engine: Engine = self._build_engine(settings)
        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    # ------------------------------------------------------------------ #
    def _build_engine(self, settings: DatabaseSettings) -> Engine:
        url = settings.url
        connect_args: dict = {}
        if url.startswith("sqlite"):
            # SQLite objects cannot be shared across threads by default.
            connect_args["check_same_thread"] = False
            db_path = url.replace("sqlite:///", "", 1)
            if db_path and db_path != ":memory:":
                ensure_dir(Path(db_path).parent)
        engine = create_engine(url, echo=settings.echo, connect_args=connect_args)

        if url.startswith("sqlite"):

            @event.listens_for(engine, "connect")
            def _set_sqlite_pragma(dbapi_con, _connection_record) -> None:
                cursor = dbapi_con.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        logger.info("Database engine initialised for %s", url)
        return engine

    # ------------------------------------------------------------------ #
    def create_schema(self) -> None:
        """Create all tables declared on :class:`~app.models.orm.Base`."""
        Base.metadata.create_all(self._engine)
        logger.info("Database schema created")

    def drop_schema(self) -> None:
        """Drop all declared tables (used in test tear-down)."""
        Base.metadata.drop_all(self._engine)
        logger.info("Database schema dropped")

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional context manager: commits on exit, rolls back on error."""
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """Dispose of the engine connection pool (called at shutdown)."""
        self._engine.dispose()
        logger.debug("Database engine disposed")

    @property
    def engine(self) -> Engine:
        return self._engine


_instance: Database | None = None


def get_db(settings: DatabaseSettings | None = None) -> Database:
    """Return the process-wide :class:`Database` singleton."""
    global _instance  # noqa: PLW0603
    if _instance is None or settings is not None:
        if settings is None:
            from app.core.config import get_settings

            settings = get_settings().database
        _instance = Database(settings)
    return _instance
