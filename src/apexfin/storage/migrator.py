"""Ordered SQL migration runner.

Forward only. If an already-applied migration's checksum no longer matches the
file on disk, the run stops with a config error instead of trying to heal
itself -- rewriting applied history is the quietest way to break a team's
database, so it gets the loudest failure.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from apexfin.core.clock import to_utc_iso
from apexfin.core.errors import MigrationError

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL,
    checksum    TEXT NOT NULL
)
"""


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, str, Path]]:
    found: list[tuple[int, str, Path]] = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise MigrationError(f"{path.name}: migration filenames must look like 0001_name.sql")
        found.append((int(match.group(1)), match.group(2), path))
    return found


def applied_versions(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    conn.execute(_MIGRATIONS_TABLE)
    rows = conn.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    return {int(r["version"]): (str(r["name"]), str(r["checksum"])) for r in rows}


def migrate(conn: sqlite3.Connection, now: datetime, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations. Returns the versions applied in this call."""
    already = applied_versions(conn)
    newly: list[int] = []
    for version, name, path in discover(directory):
        sql = path.read_text(encoding="utf-8")
        digest = _checksum(sql)
        if version in already:
            recorded_name, recorded_sum = already[version]
            if recorded_sum != digest:
                raise MigrationError(
                    f"migration {version:04d}_{recorded_name} was applied with checksum "
                    f"{recorded_sum[:12]} but {path.name} now hashes to {digest[:12]}. "
                    "Applied migrations are immutable; add a new migration instead."
                )
            continue
        # sqlite3's executescript() implicitly COMMITs any pending transaction
        # before running the script, so a manual `BEGIN` here would be committed
        # out from under us and the trailing COMMIT would fail with "no
        # transaction is active". The BEGIN is therefore part of the script
        # payload, which keeps the whole migration in one real transaction.
        try:
            conn.executescript("BEGIN;\n" + sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at, checksum) "
                "VALUES (?, ?, ?, ?)",
                (version, name, to_utc_iso(now), digest),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            with suppress(sqlite3.Error):
                conn.execute("ROLLBACK")  # BEGIN itself failed: nothing to roll back
            raise MigrationError(f"{path.name} failed to apply: {exc}") from exc
        newly.append(version)
    return newly


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    if row is None or row["v"] is None:
        return 0
    return int(row["v"])
