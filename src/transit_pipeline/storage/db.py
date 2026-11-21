"""SQLite connection manager, WAL pragmas, busy timeout, and schema initialization."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from transit_pipeline.config import PROJECT_ROOT

DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


class Database:
    """Owns SQLite connections and schema initialization."""

    def __init__(self, path: Path | str, *, schema_path: Path | None = None) -> None:
        self.path = Path(path)
        self.schema_path = schema_path or DEFAULT_SCHEMA_PATH

    def connect(self) -> sqlite3.Connection:
        """Open a connection configured for WAL-mode concurrent access."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside a transaction and close it afterwards."""
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the schema if it does not exist yet."""
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.session() as connection:
            connection.executescript(schema)
