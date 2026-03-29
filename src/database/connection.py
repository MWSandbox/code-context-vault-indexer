"""Database connection management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Connection, create_engine


_DEFAULT_DB_URL = (
    'postgresql+psycopg://postgres:postgres@localhost:5432/code_context_vault'
)


def get_db_url() -> str:
    """Return the database URL from the environment or fall back to the default."""
    return os.environ.get('DATABASE_URL', _DEFAULT_DB_URL)


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Yield a transactional database connection and commit on exit."""
    engine = create_engine(get_db_url())
    with engine.begin() as conn:
        yield conn
