"""SQLite connection manager enforcing WAL, foreign keys, and busy timeout."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with SparkSpeak's required pragmas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def open_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Context manager that opens and closes a configured SQLite connection."""
    conn = connect_sqlite(db_path)
    try:
        yield conn
    finally:
        conn.close()
