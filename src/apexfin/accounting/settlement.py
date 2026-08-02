"""Grading opinions once their horizon has elapsed.

A ledger that only ever accumulates `pending` rows is decoration. This module
closes entries out, and it is deliberately conservative about what counts as a
verdict:

* No price at or after the due date -> the entry stays `pending`. Missing data
  is not evidence against the opinion.
* Still no price long after the due date -> `void` with the reason recorded.
  Grading against a price that never arrived would be fabrication.
* A move inside the noise band -> `void`, not `hit`. Being accidentally right
  by 0.1% is not being right.

The noise band is the same 0.5% the reference strategy uses to decide a move is
real. It is stated here as its own constant rather than imported from
`decision/` because `accounting` must be able to grade opinions produced by
strategies this project has never seen.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from apexfin.core.contracts import LedgerSettlePort, SilverReadPort
from apexfin.core.models import LedgerEntry

#: Return magnitude below which a move is treated as noise and the opinion is
#: voided rather than graded.
MATERIAL_MOVE = 0.005

#: How many extra horizons to wait for a settlement price before giving up and
#: voiding the entry.
_PATIENCE_MULTIPLIER = 2

_LOOKBACK = 400


@dataclass(frozen=True)
class SettlementSummary:
    """What one settlement pass did. Every counter is a real row, not an estimate."""

    settled: int = 0
    hits: int = 0
    misses: int = 0
    voids: int = 0
    still_pending: int = 0

    @property
    def graded(self) -> int:
        """Entries that produced an actual verdict. Voids are not verdicts."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float | None:
        """`None` when nothing was graded -- never 0.0, which would read as
        'everything was wrong' instead of 'there is no sample'."""
        return None if self.graded == 0 else self.hits / self.graded


def settle_due_entries(
    ledger: LedgerSettlePort,
    silver: SilverReadPort,
    symbol_sources: Mapping[str, str],
    as_of: date,
) -> SettlementSummary:
    """Close out every pending entry whose horizon has elapsed by `as_of`."""
    settled = hits = misses = voids = pending = 0

    for entry_id, entry in ledger.pending_entries():
        if entry.due_on > as_of:
            pending += 1
            continue

        source_name = symbol_sources.get(entry.symbol)
        if source_name is None:
            ledger.settle(
                entry_id,
                as_of,
                None,
                "void",
                f"标的 {entry.symbol} 已从数据源目录中移除，无法取价结算。",
            )
            settled += 1
            voids += 1
            continue

        price = _settlement_price(silver, source_name, entry)
        if price is None:
            if _out_of_patience(entry, as_of):
                ledger.settle(
                    entry_id,
                    as_of,
                    None,
                    "void",
                    f"到期日 {entry.due_on.isoformat()} 后 "
                    f"{(as_of - entry.due_on).days} 天仍无价格数据，放弃结算。",
                )
                settled += 1
                voids += 1
            else:
                pending += 1
            continue

        settled_on, settled_value = price
        outcome, note = _grade(entry, settled_value)
        ledger.settle(entry_id, settled_on, settled_value, outcome, note)
        settled += 1
        if outcome == "hit":
            hits += 1
        elif outcome == "miss":
            misses += 1
        else:
            voids += 1

    return SettlementSummary(
        settled=settled, hits=hits, misses=misses, voids=voids, still_pending=pending
    )


def _settlement_price(
    silver: SilverReadPort, source_name: str, entry: LedgerEntry
) -> tuple[date, float] | None:
    """First observation on or after the due date, or `None` if none exists yet.

    'First on or after' rather than 'latest available': grading a 5-day call
    against a price 40 days later measures a different claim than the one that
    was made.
    """
    points = silver.series(source_name, entry.symbol, _LOOKBACK)
    for point in points:
        if point.event_date >= entry.due_on:
            return point.event_date, float(point.value)
    return None


def _out_of_patience(entry: LedgerEntry, as_of: date) -> bool:
    waited = (as_of - entry.due_on).days
    return waited > entry.horizon_days * _PATIENCE_MULTIPLIER


def _grade(entry: LedgerEntry, settled_value: float) -> tuple[str, str]:
    if entry.reference_value <= 0.0:
        return "void", "基准价非正，无法计算收益率。"

    change = settled_value / entry.reference_value - 1.0
    moved = abs(change) >= MATERIAL_MOVE
    body = (
        f"{entry.stated_on.isoformat()} 基准 {entry.reference_value:.4f} -> "
        f"到期 {settled_value:.4f}，收益 {change:+.2%}"
    )

    if entry.stance == "flat":
        if moved:
            return "miss", f"{body}；判定横盘但实际波动超过 {MATERIAL_MOVE:.1%}。"
        return "hit", f"{body}；判定横盘，波动在噪声区间内。"

    if not moved:
        return "void", f"{body}；未超出 {MATERIAL_MOVE:.1%} 噪声区间，不判定方向对错。"

    correct = (entry.stance == "long" and change > 0) or (entry.stance == "short" and change < 0)
    verdict = "方向正确" if correct else "方向错误"
    return ("hit" if correct else "miss"), f"{body}；{verdict}。"
