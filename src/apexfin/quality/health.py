"""Per-series health snapshot, written to `series_health`.

The state is the single source of truth for the dashboard's four-state icon
set and for the gate's per-source badge. The thresholds stored here are the
values *captured at check time*, not the current `expectations.yaml` value
(DATA_CONTRACT 四) -- the dashboard must be able to explain, later, why a row
was healthy on the day it was measured.

`overdue` vs `state` are deliberately separate: a `support` series that is one
trading day late is `degraded`, a `risk_essential` one is `blocked`. The state
carries the tier; the staleness alone does not (ARCHITECTURE 5.3.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apexfin.core.enums import Tier
from apexfin.core.models import SeriesHealth
from apexfin.quality.base import QualityContext

if TYPE_CHECKING:
    from apexfin.storage.quality_repo import QualityRepository


def compute_series_health(
    ctx: QualityContext,
    quality_repo: QualityRepository | None = None,
) -> tuple[SeriesHealth, ...]:
    """One health row per configured series."""
    out: list[SeriesHealth] = []
    today = ctx.clock.today()

    for spec in ctx.series:
        expectation = ctx.expectation_for(spec)
        threshold = expectation.max_lag_trading_days
        latest = ctx.silver.latest_event_date(spec.source_name, spec.symbol)

        if latest is None:
            out.append(
                SeriesHealth(
                    source_name=f"{spec.source_name}/{spec.domain}",
                    symbol=spec.symbol,
                    last_event_date=None,
                    lag_trading_days=None,
                    max_lag_trading_days=threshold,
                    state="unknown",
                    last_checked_at=ctx.clock.now(),
                    consecutive_fails=0,
                    note="从未成功采集（建库后首跑）。",
                )
            )
            continue

        lag = ctx.calendar.trading_days_between(latest, today)
        previous_fails = (
            quality_repo.previous_fails(spec.source_name, spec.symbol)
            if quality_repo is not None
            else 0
        )

        if spec.tier == Tier.RISK_ESSENTIAL and lag > threshold:
            state = "blocked"
        elif lag > threshold or previous_fails > 0:
            state = "degraded"
        else:
            state = "healthy"

        out.append(
            SeriesHealth(
                source_name=f"{spec.source_name}/{spec.domain}",
                symbol=spec.symbol,
                last_event_date=latest,
                lag_trading_days=lag,
                max_lag_trading_days=threshold,
                state=state,
                last_checked_at=ctx.clock.now(),
                consecutive_fails=0 if state == "healthy" else max(previous_fails, 1),
                note=None,
            )
        )
    return tuple(out)
