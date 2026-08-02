"""Continuity: trading-calendar-aware gap detection.

Consecutive samples on a daily series should be adjacent trading days, so the
gap between them (in trading days) should be exactly one and no trading day
should be missing in between. A weekend is *not* a gap -- Friday to Monday is
one trading day, zero missing -- which is precisely why this is measured in
trading days and not in calendar days (ARCHITECTURE 5.3.1).

The window ends at the series' own newest business date, not at today, so a
late series is reported once by freshness rather than again here.
"""

from __future__ import annotations

from itertools import pairwise
from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext


@register_check("continuity")
class ContinuityCheck(QualityCheck):
    check_id: ClassVar[str] = "continuity"
    default_severity: ClassVar[Severity] = Severity.WARNING
    title: ClassVar[str] = "Continuity"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        today = ctx.clock.today()

        for spec in ctx.series:
            expectation = ctx.expectation_for(spec)
            max_gap = expectation.max_gap_trading_days
            dates = ctx.silver.event_dates(spec.source_name, spec.symbol)
            if len(dates) < 2:
                continue

            end = min(dates[-1], today)
            window = tuple(d for d in dates if d <= end)
            for prev, cur in pairwise(window):
                span = ctx.calendar.trading_days_between(prev, cur)
                missing = span - 1
                if missing <= max_gap:
                    continue
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} has a gap of {missing} missing "
                        f"trading days between {prev.isoformat()} and {cur.isoformat()}.",
                        observed=f"trading_days_between={span}, missing={missing}",
                        expected=f"no more than {max_gap} missing trading days "
                        f"between consecutive samples",
                    )
                )
        return findings
