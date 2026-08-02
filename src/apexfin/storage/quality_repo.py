"""Quality repository: findings plus the series health snapshot."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from apexfin.core.clock import parse_utc, to_utc_iso
from apexfin.core.enums import Severity, Tier
from apexfin.core.models import QualityFinding, SeriesHealth


class QualityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write_findings(
        self, findings: tuple[QualityFinding, ...], run_id: str, now: datetime
    ) -> int:
        for finding in findings:
            self._conn.execute(
                "INSERT INTO quality_findings (run_id, check_id, severity, tier, source_name, "
                "symbol, message, observed, expected, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    finding.check_id,
                    finding.severity.value,
                    finding.tier.value,
                    finding.source_name,
                    finding.symbol,
                    finding.message,
                    finding.observed,
                    finding.expected,
                    to_utc_iso(now),
                ),
            )
        return len(findings)

    def findings_for_run(self, run_id: str) -> tuple[QualityFinding, ...]:
        rows = self._conn.execute(
            "SELECT * FROM quality_findings WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return tuple(
            QualityFinding(
                check_id=str(r["check_id"]),
                severity=Severity(str(r["severity"])),
                source_name=str(r["source_name"]),
                symbol=None if r["symbol"] is None else str(r["symbol"]),
                message=str(r["message"]),
                observed=None if r["observed"] is None else str(r["observed"]),
                expected=None if r["expected"] is None else str(r["expected"]),
                tier=Tier(str(r["tier"])),
            )
            for r in rows
        )

    def upsert_health(self, health: SeriesHealth) -> None:
        self._conn.execute(
            "INSERT INTO series_health (source_name, symbol, last_event_date, "
            "lag_trading_days, max_lag_trading_days, state, last_checked_at, "
            "consecutive_fails, note) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (source_name, symbol) DO UPDATE SET "
            "last_event_date=excluded.last_event_date, "
            "lag_trading_days=excluded.lag_trading_days, "
            "max_lag_trading_days=excluded.max_lag_trading_days, state=excluded.state, "
            "last_checked_at=excluded.last_checked_at, "
            "consecutive_fails=excluded.consecutive_fails, note=excluded.note",
            (
                health.source_name,
                health.symbol,
                None if health.last_event_date is None else health.last_event_date.isoformat(),
                health.lag_trading_days,
                health.max_lag_trading_days,
                health.state,
                to_utc_iso(health.last_checked_at),
                health.consecutive_fails,
                health.note,
            ),
        )

    def previous_fails(self, source_name: str, symbol: str) -> int:
        row = self._conn.execute(
            "SELECT consecutive_fails FROM series_health WHERE source_name=? AND symbol=?",
            (source_name, symbol),
        ).fetchone()
        return int(row["consecutive_fails"]) if row is not None else 0

    def all_health(self) -> tuple[SeriesHealth, ...]:
        rows = self._conn.execute(
            "SELECT * FROM series_health ORDER BY source_name, symbol"
        ).fetchall()
        return tuple(
            SeriesHealth(
                source_name=str(r["source_name"]),
                symbol=str(r["symbol"]),
                last_event_date=(
                    None
                    if r["last_event_date"] is None
                    else date.fromisoformat(str(r["last_event_date"]))
                ),
                lag_trading_days=(
                    None if r["lag_trading_days"] is None else int(r["lag_trading_days"])
                ),
                max_lag_trading_days=int(r["max_lag_trading_days"]),
                state=str(r["state"]),
                last_checked_at=parse_utc(str(r["last_checked_at"])),
                consecutive_fails=int(r["consecutive_fails"]),
                note=None if r["note"] is None else str(r["note"]),
            )
            for r in rows
        )
