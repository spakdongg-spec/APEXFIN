"""Silver repository: one normalised number per row."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from apexfin.core.clock import parse_utc, to_utc_iso
from apexfin.core.models import SilverPoint


class SilverRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, points: tuple[SilverPoint, ...], run_id: str, now: datetime) -> int:
        written = 0
        for point in points:
            self._conn.execute(
                "INSERT INTO silver_points (bronze_id, source_name, domain, symbol, event_time, "
                "event_date, value, value_secondary, unit, quality_score, is_filled, "
                "payload_json, run_id, built_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT (source_name, symbol, event_time) DO UPDATE SET "
                "value=excluded.value, value_secondary=excluded.value_secondary, "
                "unit=excluded.unit, quality_score=excluded.quality_score, "
                "is_filled=excluded.is_filled, payload_json=excluded.payload_json, "
                "run_id=excluded.run_id, built_at=excluded.built_at",
                (
                    point.bronze_id,
                    point.source_name,
                    point.domain,
                    point.symbol,
                    to_utc_iso(point.event_time),
                    point.event_date.isoformat(),
                    point.value,
                    point.value_secondary,
                    point.unit,
                    point.quality_score,
                    1 if point.is_filled else 0,
                    json.dumps(point.payload_json, sort_keys=True) if point.payload_json else None,
                    run_id,
                    to_utc_iso(now),
                ),
            )
            written += 1
        return written

    def series(self, source_name: str, symbol: str, lookback: int = 250) -> tuple[SilverPoint, ...]:
        rows = self._conn.execute(
            "SELECT * FROM silver_points WHERE source_name=? AND symbol=? "
            "ORDER BY event_date DESC LIMIT ?",
            (source_name, symbol, lookback),
        ).fetchall()
        return tuple(reversed([_to_point(r) for r in rows]))

    def latest_event_date(self, source_name: str, symbol: str) -> date | None:
        row = self._conn.execute(
            "SELECT MAX(event_date) AS d FROM silver_points WHERE source_name=? AND symbol=?",
            (source_name, symbol),
        ).fetchone()
        if row is None or row["d"] is None:
            return None
        return date.fromisoformat(str(row["d"]))

    def distinct_series(self) -> tuple[tuple[str, str], ...]:
        rows = self._conn.execute(
            "SELECT DISTINCT source_name, symbol FROM silver_points ORDER BY source_name, symbol"
        ).fetchall()
        return tuple((str(r["source_name"]), str(r["symbol"])) for r in rows)

    def clear_source(self, source_name: str) -> int:
        """Drop every silver point for a source (see BronzeRepository.clear_source)."""
        cur = self._conn.execute("DELETE FROM silver_points WHERE source_name=?", (source_name,))
        return int(cur.rowcount)

    def count_for(self, source_name: str, symbol: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM silver_points WHERE source_name=? AND symbol=?",
            (source_name, symbol),
        ).fetchone()
        return int(row["c"]) if row is not None else 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM silver_points").fetchone()
        return int(row["c"]) if row is not None else 0

    def event_dates(self, source_name: str, symbol: str) -> tuple[date, ...]:
        rows = self._conn.execute(
            "SELECT event_date FROM silver_points WHERE source_name=? AND symbol=? "
            "ORDER BY event_date",
            (source_name, symbol),
        ).fetchall()
        return tuple(date.fromisoformat(str(r["event_date"])) for r in rows)

    def domain_of(self, source_name: str, symbol: str) -> str | None:
        row = self._conn.execute(
            "SELECT domain FROM silver_points WHERE source_name=? AND symbol=? LIMIT 1",
            (source_name, symbol),
        ).fetchone()
        return str(row["domain"]) if row is not None else None


def _to_point(row: sqlite3.Row) -> SilverPoint:
    payload = row["payload_json"]
    return SilverPoint(
        source_name=str(row["source_name"]),
        domain=str(row["domain"]),
        symbol=str(row["symbol"]),
        event_time=parse_utc(str(row["event_time"])),
        event_date=date.fromisoformat(str(row["event_date"])),
        value=float(row["value"]),
        value_secondary=None if row["value_secondary"] is None else float(row["value_secondary"]),
        unit=None if row["unit"] is None else str(row["unit"]),
        quality_score=float(row["quality_score"]),
        is_filled=bool(row["is_filled"]),
        payload_json=json.loads(str(payload)) if payload else None,
        bronze_id=None if row["bronze_id"] is None else int(row["bronze_id"]),
    )
