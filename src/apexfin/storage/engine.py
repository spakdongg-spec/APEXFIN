"""SQLite connection, PRAGMAs and the savepoint context manager.

`busy_timeout` fails loud after 5 seconds instead of hanging forever: a demo
that appears to freeze teaches nothing, an error that says 'database is
locked' teaches exactly what happened.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
)


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with project PRAGMAs applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


@contextmanager
def savepoint(conn: sqlite3.Connection, name: str) -> Iterator[sqlite3.Connection]:
    """Run a unit of work inside a named SAVEPOINT.

    A failing pipeline step rolls back its own writes while the surrounding
    run keeps its `step_runs` bookkeeping -- the failure record must survive
    the rollback of the thing that failed.
    """
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    conn.execute(f"SAVEPOINT {safe}")
    try:
        yield conn
    except BaseException:
        conn.execute(f"ROLLBACK TO {safe}")
        conn.execute(f"RELEASE {safe}")
        raise
    else:
        conn.execute(f"RELEASE {safe}")


def table_names(conn: sqlite3.Connection) -> tuple[str, ...]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return tuple(str(row["name"]) for row in rows)
