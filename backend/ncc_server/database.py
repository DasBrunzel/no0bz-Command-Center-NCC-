from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(url, pool_pre_ping=True)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def ping(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def sessions(self) -> Iterator[Session]:
        with self.session() as session:
            yield session

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
