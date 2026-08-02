"""Consistency: does silver agree with bronze for the same series?

Two concrete disagreements are worth a finding:

1. Bronze has data but silver has none -- the normalisation step dropped the
   series entirely (extractor missing, process skipped). That is the silent
   rot class this project exists to surface, so it is a finding, not a no-op.
2. Bronze and silver disagree on the *newest* business date -- silver is
   behind bronze, which means process did not run to completion.

Equality of the newest date is enough: a full bronze/silver diff would be
cheap to write but it is not what this check is for, and a check that reports
ten tiny diffs trains readers to ignore it.
"""

from __future__ import annotations

from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext


@register_check("consistency")
class ConsistencyCheck(QualityCheck):
    check_id: ClassVar[str] = "consistency"
    default_severity: ClassVar[Severity] = Severity.WARNING
    title: ClassVar[str] = "Bronze / Silver consistency"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        for spec in ctx.series:
            bronze_latest = ctx.bronze.latest_event_date(spec.source_name, spec.symbol)
            if bronze_latest is None:
                continue  # nothing collected; freshness owns the empty case
            silver_latest = ctx.silver.latest_event_date(spec.source_name, spec.symbol)
            if silver_latest is None:
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} has bronze data but no silver "
                        "point at all -- the normalisation step dropped the series.",
                        observed="silver latest_event_date=none",
                        expected=f"silver latest_event_date={bronze_latest.isoformat()}",
                    )
                )
                continue
            if bronze_latest != silver_latest:
                findings.append(
                    self.finding(
                        spec,
                        f"{spec.source_name}/{spec.symbol} silver lags behind bronze; "
                        "the process step did not run to completion.",
                        observed=(
                            f"bronze={bronze_latest.isoformat()} silver={silver_latest.isoformat()}"
                        ),
                        expected=f"silver latest_event_date={bronze_latest.isoformat()}",
                    )
                )
        return findings
