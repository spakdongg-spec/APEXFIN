"""Writing opinions into the ledger.

Every decision the pipeline produces gets a ledger row, `no_call` included.
Skipping `no_call` would let the system quietly forget the days it had nothing
to say, and a hit rate computed only over the days it felt confident is not a
hit rate -- it is marketing.

A `no_call` row is written already settled as `void`: there is no falsifiable
claim to grade, so leaving it `pending` would park a row in the due-date index
that can never resolve. It stays visible in the ledger, and it is excluded from
hit-rate arithmetic by its outcome, not by its absence.
"""

from __future__ import annotations

from datetime import date

from apexfin.core.contracts import LedgerWritePort
from apexfin.core.errors import ApexfinError
from apexfin.core.models import Decision, LedgerEntry

#: Stances that make a claim the market can later prove wrong.
FALSIFIABLE_STANCES = frozenset({"long", "short", "flat"})

_NO_CALL_NOTE = "无观点：未作出可证伪的方向主张，不计入命中率。"


class LedgerWriteError(ApexfinError):
    """The ledger was handed an entry that could never be settled honestly."""


def write_opinion_ledger(
    ledger: LedgerWritePort,
    decision: Decision,
    decision_id: int,
    *,
    reference_value: float,
    due_on: date,
    horizon_days: int,
) -> LedgerEntry:
    """Record `decision` in the opinion ledger and return the row written.

    Raises `LedgerWriteError` rather than writing a row that cannot be graded:
    a zero horizon, a due date on or before the stated date, or a decision id
    that was never persisted all produce entries that look fine in the table
    and are meaningless at settlement time.
    """
    if decision_id <= 0:
        raise LedgerWriteError(
            f"refusing to write a ledger row for {decision.symbol} with decision_id="
            f"{decision_id}: the decision was not persisted, so the row would dangle"
        )
    if horizon_days <= 0:
        raise LedgerWriteError(
            f"horizon_days must be positive for {decision.symbol}, got {horizon_days}"
        )
    if due_on <= decision.as_of:
        raise LedgerWriteError(
            f"due_on ({due_on.isoformat()}) must fall after stated_on "
            f"({decision.as_of.isoformat()}) for {decision.symbol}"
        )

    falsifiable = decision.stance in FALSIFIABLE_STANCES
    if falsifiable and reference_value <= 0.0:
        raise LedgerWriteError(
            f"{decision.symbol} stance '{decision.stance}' needs a positive reference value "
            f"to compute a return at settlement, got {reference_value!r}"
        )

    entry = LedgerEntry(
        decision_id=decision_id,
        symbol=decision.symbol,
        stated_on=decision.as_of,
        horizon_days=horizon_days,
        due_on=due_on,
        stance=decision.stance,
        reference_value=reference_value,
        settled_on=None if falsifiable else decision.as_of,
        settled_value=None,
        outcome="pending" if falsifiable else "void",
        settled_note=None if falsifiable else _NO_CALL_NOTE,
    )
    ledger.write_ledger(entry)
    return entry
