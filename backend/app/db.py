from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


class Database:
    """Holds the engine/session factory; created per app instance (no hidden globals)."""

    def __init__(self, url: str):
        self.engine = make_engine(url)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def create_all(self) -> None:
        """Used by tests only; production uses Alembic migrations."""
        from app import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def ping(self) -> bool:
        from sqlalchemy import text

        with self.engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True

    def is_migrated(self) -> bool:
        from sqlalchemy import inspect

        return inspect(self.engine).has_table("search_sessions")
