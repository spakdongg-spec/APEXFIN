"""Decision repository: decisions and the opinion ledger.

`no_call` rows are written, not skipped. A day with no record is a day the
system can later pretend it never had an opinion, which defeats the whole
point of keeping a ledger.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from apexfin.core.clock import to_utc_iso
from apexfin.core.models import Decision, LedgerEntry


class DecisionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def write(self, decision: Decision, now: datetime) -> int:
        cursor = self._conn.execute(
            "INSERT INTO decisions (run_id, as_of_date, symbol, stance, confidence, strategy, "
            "rationale, inputs_json, degraded, created_at) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (run_id, symbol, strategy) DO UPDATE SET stance=excluded.stance, "
            "confidence=excluded.confidence, rationale=excluded.rationale, "
            "inputs_json=excluded.inputs_json, degraded=excluded.degraded",
            (
                decision.run_id,
                decision.as_of.isoformat(),
                decision.symbol,
                decision.stance,
                decision.confidence,
                decision.strategy,
                decision.rationale,
                json.dumps(decision.inputs, sort_keys=True),
                1 if decision.degraded else 0,
                to_utc_iso(now),
            ),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = self._conn.execute(
            "SELECT id FROM decisions WHERE run_id=? AND symbol=? AND strategy=?",
            (decision.run_id, decision.symbol, decision.strategy),
        ).fetchone()
        return int(row["id"]) if row is not None else 0

    def decisions_for_run(self, run_id: str) -> tuple[Decision, ...]:
        rows = self._conn.execute(
            "SELECT * FROM decisions WHERE run_id=? ORDER BY symbol", (run_id,)
        ).fetchall()
        return tuple(
            Decision(
                run_id=str(r["run_id"]),
                as_of=date.fromisoformat(str(r["as_of_date"])),
                symbol=str(r["symbol"]),
                stance=str(r["stance"]),  # type: ignore[arg-type]
                confidence=float(r["confidence"]),
                strategy=str(r["strategy"]),
                rationale=str(r["rationale"]),
                inputs=json.loads(str(r["inputs_json"])),
                degraded=bool(r["degraded"]),
            )
            for r in rows
        )

    def write_ledger(self, entry: LedgerEntry) -> None:
        self._conn.execute(
            "INSERT INTO opinion_ledger (decision_id, symbol, stated_on, horizon_days, due_on, "
            "stance, reference_value, settled_on, settled_value, outcome, settled_note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                entry.decision_id,
                entry.symbol,
                entry.stated_on.isoformat(),
                entry.horizon_days,
                entry.due_on.isoformat(),
                entry.stance,
                entry.reference_value,
                None if entry.settled_on is None else entry.settled_on.isoformat(),
                entry.settled_value,
                entry.outcome,
                entry.settled_note,
            ),
        )

    def ledger_rows(self, limit: int = 50) -> tuple[LedgerEntry, ...]:
        rows = self._conn.execute(
            "SELECT * FROM opinion_ledger ORDER BY stated_on DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return tuple(
            LedgerEntry(
                decision_id=int(r["decision_id"]),
                symbol=str(r["symbol"]),
                stated_on=date.fromisoformat(str(r["stated_on"])),
                horizon_days=int(r["horizon_days"]),
                due_on=date.fromisoformat(str(r["due_on"])),
                stance=str(r["stance"]),
                reference_value=float(r["reference_value"]),
                settled_on=(
                    None if r["settled_on"] is None else date.fromisoformat(str(r["settled_on"]))
                ),
                settled_value=None if r["settled_value"] is None else float(r["settled_value"]),
                outcome=str(r["outcome"]) if r["outcome"] else "pending",
                settled_note=None if r["settled_note"] is None else str(r["settled_note"]),
            )
            for r in rows
        )

    def pending_entries(self) -> tuple[tuple[int, LedgerEntry], ...]:
        rows = self._conn.execute(
            "SELECT * FROM opinion_ledger WHERE outcome='pending' ORDER BY due_on"
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                (
                    int(r["id"]),
                    LedgerEntry(
                        decision_id=int(r["decision_id"]),
                        symbol=str(r["symbol"]),
                        stated_on=date.fromisoformat(str(r["stated_on"])),
                        horizon_days=int(r["horizon_days"]),
                        due_on=date.fromisoformat(str(r["due_on"])),
                        stance=str(r["stance"]),
                        reference_value=float(r["reference_value"]),
                    ),
                )
            )
        return tuple(out)

    def settle(
        self, entry_id: int, settled_on: date, settled_value: float | None, outcome: str, note: str
    ) -> None:
        self._conn.execute(
            "UPDATE opinion_ledger SET settled_on=?, settled_value=?, outcome=?, settled_note=? "
            "WHERE id=?",
            (settled_on.isoformat(), settled_value, outcome, note, entry_id),
        )
