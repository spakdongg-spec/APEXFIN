"""Completeness: how many expected trading days inside the window are present.

Scope is deliberately narrow so this check does not restate freshness. The
window ends at the series' own newest business date, not at today, so a series
that is simply late produces one freshness finding rather than one freshness
finding plus nine completeness findings saying the same thing in a different
unit. Holes and lateness are different failures with different fixes.

The window also starts no earlier than the series' first observation, so a
newly added symbol is not reported as 95 percent incomplete on day one.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext

_MAX_LISTED = 5


@register_check("completeness")
class CompletenessCheck(QualityCheck):
    check_id: ClassVar[str] = "completeness"
    default_severity: ClassVar[Severity] = Severity.WARNING
    title: ClassVar[str] = "Completeness"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []

        for spec in ctx.series:
            expectation = ctx.expectation_for(spec)
            dates = ctx.silver.event_dates(spec.source_name, spec.symbol)
            if not dates:
                continue  # freshness owns the empty-series case

            end = min(dates[-1], ctx.clock.today())
            expected = _window(ctx, end, expectation.completeness_window_days)
            expected = tuple(d for d in expected if d >= dates[0])
            if not expected:
                continue

            present = set(dates)
            missing = tuple(d for d in expected if d not in present)
            if len(missing) > expectation.max_missing_trading_days:
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} is missing "
                        f"{len(missing)} of {len(expected)} expected trading days in the "
                        f"window {expected[0].isoformat()}..{expected[-1].isoformat()}.",
                        observed=f"missing={_render(missing)}",
                        expected=f"at most {expectation.max_missing_trading_days} missing "
                        f"trading days in a {expectation.completeness_window_days}-day window",
                    )
                )

        return findings


def _window(ctx: QualityContext, end: date, length: int) -> tuple[date, ...]:
    """The last `length` trading days ending at `end`, inclusive."""
    if length <= 0:
        return ()
    start = end - timedelta(days=length * 2 + 10)
    days = ctx.calendar.trading_days_in(start, end)
    return days[-length:]


def _render(days: tuple[date, ...]) -> str:
    shown = ", ".join(d.isoformat() for d in days[:_MAX_LISTED])
    if len(days) > _MAX_LISTED:
        return f"{shown}, ... (+{len(days) - _MAX_LISTED} more)"
    return shown
