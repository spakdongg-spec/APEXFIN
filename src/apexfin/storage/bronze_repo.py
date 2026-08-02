"""Bronze repository: raw payloads with a revision chain.

Upstream revisions (FRED restating history, Yahoo re-adjusting for splits) are
snapshotted into `bronze_revisions` instead of being overwritten. Overwriting
would make 'what data was yesterday's conclusion based on' permanently
unanswerable.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from typing import Any

from apexfin.core.clock import parse_utc, to_utc_iso
from apexfin.core.models import BronzeRecord, RawRecord, UpsertStats


def canonical_hash(payload: dict[str, Any]) -> str:
    """sha256 over key-sorted, separator-normalised JSON."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BronzeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, records: tuple[RawRecord, ...], run_id: str, now: datetime) -> UpsertStats:
        inserted = duplicates = revisions = 0
        for record in records:
            payload_hash = canonical_hash(record.payload)
            event_time = to_utc_iso(record.event_time)
            existing = self._conn.execute(
                "SELECT id, payload, payload_hash, revision FROM bronze_records "
                "WHERE source_name=? AND symbol=? AND event_time=?",
                (record.source_name, record.symbol, event_time),
            ).fetchone()

            if existing is None:
                self._conn.execute(
                    "INSERT INTO bronze_records (source_name, domain, symbol, event_time, "
                    "event_date, payload, payload_hash, revision, source_url, run_id, "
                    "ingested_at) VALUES (?,?,?,?,?,?,?,0,?,?,?)",
                    (
                        record.source_name,
                        record.domain,
                        record.symbol,
                        event_time,
                        record.event_time.date().isoformat(),
                        json.dumps(record.payload, sort_keys=True, ensure_ascii=False),
                        payload_hash,
                        record.source_url,
                        run_id,
                        to_utc_iso(now),
                    ),
                )
                inserted += 1
            elif existing["payload_hash"] == payload_hash:
                duplicates += 1
            else:
                next_revision = int(existing["revision"]) + 1
                self._conn.execute(
                    "INSERT INTO bronze_revisions (bronze_id, revision, payload, payload_hash, "
                    "superseded_at, run_id) VALUES (?,?,?,?,?,?)",
                    (
                        int(existing["id"]),
                        int(existing["revision"]),
                        existing["payload"],
                        existing["payload_hash"],
                        to_utc_iso(now),
                        run_id,
                    ),
                )
                self._conn.execute(
                    "UPDATE bronze_records SET payload=?, payload_hash=?, revision=?, run_id=?, "
                    "ingested_at=? WHERE id=?",
                    (
                        json.dumps(record.payload, sort_keys=True, ensure_ascii=False),
                        payload_hash,
                        next_revision,
                        run_id,
                        to_utc_iso(now),
                        int(existing["id"]),
                    ),
                )
                revisions += 1
        return UpsertStats(inserted=inserted, duplicates=duplicates, revisions=revisions)

    def latest_event_date(self, source_name: str, symbol: str) -> date | None:
        row = self._conn.execute(
            "SELECT MAX(event_date) AS d FROM bronze_records WHERE source_name=? AND symbol=?",
            (source_name, symbol),
        ).fetchone()
        if row is None or row["d"] is None:
            return None
        return date.fromisoformat(str(row["d"]))

    def count_between(self, source_name: str, symbol: str, start: date, end: date) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM bronze_records WHERE source_name=? AND symbol=? "
            "AND event_date BETWEEN ? AND ?",
            (source_name, symbol, start.isoformat(), end.isoformat()),
        ).fetchone()
        return int(row["c"]) if row is not None else 0

    def distinct_series(self) -> tuple[tuple[str, str], ...]:
        rows = self._conn.execute(
            "SELECT DISTINCT source_name, symbol FROM bronze_records ORDER BY source_name, symbol"
        ).fetchall()
        return tuple((str(r["source_name"]), str(r["symbol"])) for r in rows)

    def clear_source(self, source_name: str) -> int:
        """Drop every bronze row for a source.

        Used by offline fixture packs, which replay a self-contained scenario:
        a stale pack must replace a previously collected fresh one, not pile
        onto it, or freshness would keep reading the old latest date.
        """
        cur = self._conn.execute("DELETE FROM bronze_records WHERE source_name=?", (source_name,))
        return int(cur.rowcount)

    def duplicate_event_dates(self, source_name: str, symbol: str) -> tuple[str, ...]:
        """Event dates carrying more than one row for the same series."""
        rows = self._conn.execute(
            "SELECT event_date FROM bronze_records WHERE source_name=? AND symbol=? "
            "GROUP BY event_date HAVING COUNT(*) > 1 ORDER BY event_date",
            (source_name, symbol),
        ).fetchall()
        return tuple(str(r["event_date"]) for r in rows)

    def unprocessed(self, limit: int = 5000) -> tuple[BronzeRecord, ...]:
        """Bronze rows with no silver row for the same (source, symbol, time)."""
        rows = self._conn.execute(
            "SELECT b.* FROM bronze_records b LEFT JOIN silver_points s "
            "ON s.source_name=b.source_name AND s.symbol=b.symbol AND s.event_time=b.event_time "
            "WHERE s.id IS NULL ORDER BY b.event_time LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(_to_record(r) for r in rows)

    def all_records(self, limit: int = 20000) -> tuple[BronzeRecord, ...]:
        rows = self._conn.execute(
            "SELECT * FROM bronze_records ORDER BY event_time LIMIT ?", (limit,)
        ).fetchall()
        return tuple(_to_record(r) for r in rows)

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM bronze_records").fetchone()
        return int(row["c"]) if row is not None else 0


def _to_record(row: sqlite3.Row) -> BronzeRecord:
    return BronzeRecord(
        id=int(row["id"]),
        source_name=str(row["source_name"]),
        domain=str(row["domain"]),
        symbol=str(row["symbol"]),
        event_time=parse_utc(str(row["event_time"])),
        event_date=date.fromisoformat(str(row["event_date"])),
        payload=json.loads(str(row["payload"])),
        payload_hash=str(row["payload_hash"]),
        revision=int(row["revision"]),
        ingested_at=parse_utc(str(row["ingested_at"])),
    )
