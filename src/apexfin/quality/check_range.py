"""Range: numeric plausibility against configured bounds.

The bounds come from `expectations.yaml` (`value_min` / `value_max`). A source
with no bounds configured is simply skipped -- this check only fires when a
human has stated what "reasonable" means, because an unconfigured bound would
either never fire or fire on every legitimate value.

A value out of range is a WARNING, not a BLOCKING: a single implausible print
in a long price history is worth flagging but it should not, by itself, stop
the daily run.
"""

from __future__ import annotations

from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext


@register_check("range")
class RangeCheck(QualityCheck):
    check_id: ClassVar[str] = "range"
    default_severity: ClassVar[Severity] = Severity.WARNING
    title: ClassVar[str] = "Range plausibility"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        for spec in ctx.series:
            expectation = ctx.expectation_for(spec)
            lo = expectation.value_min
            hi = expectation.value_max
            if lo is None and hi is None:
                continue
            points = ctx.silver.series(spec.source_name, spec.symbol, lookback=250)
            for point in points:
                if lo is not None and point.value < lo:
                    findings.append(
                        self.finding(
                            spec,
                            f"{spec.source_name}/{spec.symbol} value {point.value} is below "
                            f"the expected minimum {lo}.",
                            observed=f"value={point.value} at {point.event_date.isoformat()}",
                            expected=f"value >= {lo}",
                        )
                    )
                elif hi is not None and point.value > hi:
                    findings.append(
                        self.finding(
                            spec,
                            f"{spec.source_name}/{spec.symbol} value {point.value} is above "
                            f"the expected maximum {hi}.",
                            observed=f"value={point.value} at {point.event_date.isoformat()}",
                            expected=f"value <= {hi}",
                        )
                    )
        return findings
