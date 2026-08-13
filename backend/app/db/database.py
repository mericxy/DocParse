"""Synchronous SQLAlchemy setup shared by the API and worker processes."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ..config import Settings


class Base(DeclarativeBase):
    pass


SessionFactory = sessionmaker[Session]


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return
    if url.database == ":memory:":
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_database(settings: Settings) -> tuple[Engine, SessionFactory]:
    """Create an engine configured for short API/worker SQLite transactions."""

    from sqlalchemy import create_engine

    _ensure_sqlite_parent(settings.database_url)
    is_memory = settings.database_url in {"sqlite://", "sqlite:///:memory:"}
    engine_kwargs: dict[str, object] = {
        "connect_args": {"check_same_thread": False},
    }
    if is_memory:
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **engine_kwargs)

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    return engine, factory


def init_database(engine: Engine) -> None:
    # Import registers mapped classes before create_all.
    from . import models as _models  # noqa: F401

    Base.metadata.create_all(engine)
