"""Run repository: pipeline_runs and step_runs (self-observation)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from apexfin.core.clock import parse_utc, to_utc_iso
from apexfin.core.enums import RunState, StepStatus
from apexfin.core.models import StepResult

#: One row of `step_runs`, as returned by `steps_for_run`.
StepRow = tuple[str, str, StepStatus, datetime | None, float, str | None, dict[str, float]]


class RunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def start_run(
        self,
        run_id: str,
        started_at: datetime,
        as_of: date,
        manifest_hash: str,
        fixture_pack: str | None,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO pipeline_runs (run_id, started_at, finished_at, state, "
            "manifest_hash, fixture_pack, as_of_date, exit_code, summary) "
            "VALUES (?,?,NULL,?,?,?,?,NULL,NULL)",
            (
                run_id,
                to_utc_iso(started_at),
                RunState.RUNNING.value,
                manifest_hash,
                fixture_pack,
                as_of.isoformat(),
            ),
        )

    def finish_run(
        self,
        run_id: str,
        finished_at: datetime,
        state: RunState,
        exit_code: int,
        summary: str,
    ) -> None:
        self._conn.execute(
            "UPDATE pipeline_runs SET finished_at=?, state=?, exit_code=?, summary=? "
            "WHERE run_id=?",
            (to_utc_iso(finished_at), state.value, exit_code, summary, run_id),
        )

    def record_step(self, run_id: str, tier: str, started_at: datetime, result: StepResult) -> None:
        self._conn.execute(
            "INSERT INTO step_runs (run_id, step_name, tier, status, started_at, duration_s, "
            "message, metrics) VALUES (?,?,?,?,?,?,?,?)",
            (
                run_id,
                result.step_name,
                tier,
                result.status.value,
                to_utc_iso(started_at),
                result.duration_s,
                result.message,
                json.dumps(result.metrics, sort_keys=True),
            ),
        )

    def latest_run_id(self) -> str | None:
        row = self._conn.execute(
            "SELECT run_id FROM pipeline_runs ORDER BY started_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return None if row is None else str(row["run_id"])

    def run_row(self, run_id: str) -> sqlite3.Row | None:
        row = self._conn.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        return row if isinstance(row, sqlite3.Row) else None

    def steps_for_run(self, run_id: str) -> tuple[StepRow, ...]:
        rows = self._conn.execute(
            "SELECT step_name, tier, status, started_at, duration_s, message, metrics "
            "FROM step_runs WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        out = []
        for r in rows:
            raw_metrics = r["metrics"]
            metrics: dict[str, float] = json.loads(str(raw_metrics)) if raw_metrics else {}
            started_raw = r["started_at"]
            started = parse_utc(str(started_raw)) if started_raw is not None else None
            out.append(
                (
                    str(r["step_name"]),
                    str(r["tier"]),
                    StepStatus(str(r["status"])),
                    started,
                    float(r["duration_s"]),
                    None if r["message"] is None else str(r["message"]),
                    metrics,
                )
            )
        return tuple(out)
