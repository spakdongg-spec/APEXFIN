"""Freshness: is the newest business date late, measured in trading days.

The unit is trading days and nothing else (ARCHITECTURE 5.3.1). An hour-based
SLA reports every weekend as a breach on every daily series, and a dashboard
that cries wolf every Saturday trains its readers to ignore it -- which is
worse than having no alert at all.

Lag is measured from the newest *business* date to `clock.today()`, never from
the write timestamp. Those two answer different questions and only one of them
is about the age of the data.
"""

from __future__ import annotations

from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext


@register_check("freshness")
class FreshnessCheck(QualityCheck):
    check_id: ClassVar[str] = "freshness"
    default_severity: ClassVar[Severity] = Severity.BLOCKING
    title: ClassVar[str] = "Freshness"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        today = ctx.clock.today()

        for spec in ctx.series:
            expectation = ctx.expectation_for(spec)
            threshold = expectation.max_lag_trading_days
            latest = ctx.silver.latest_event_date(spec.source_name, spec.symbol)

            if latest is None:
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} has no silver point at all, so "
                        "its lag cannot be measured. Treated as a breach rather than as "
                        "'nothing to report'.",
                        observed="latest_event_date=none",
                        expected=f"lag <= {threshold} trading days",
                    )
                )
                continue

            lag = ctx.calendar.trading_days_between(latest, today)
            if lag > threshold:
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} is {lag} trading days behind; "
                        f"the threshold for tier {spec.tier.value} is {threshold}.",
                        observed=f"latest_event_date={latest.isoformat()}, lag={lag} trading days",
                        expected=f"lag <= {threshold} trading days "
                        f"(tier={spec.tier.value}, as_of={today.isoformat()})",
                    )
                )

        return findings
