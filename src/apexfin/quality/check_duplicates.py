"""Duplicates: more than one bronze row for the same (source, symbol, date).

This is the one check that cannot be derived from counts alone: a single
duplicate is invisible to `count_between` but silently doubles a point's weight
downstream. The port hands back the *dates* that collided so the finding names
them, and a finding that cannot name the day is not actionable.
"""

from __future__ import annotations

from typing import ClassVar

from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding
from apexfin.core.registry import register_check
from apexfin.quality.base import QualityCheck, QualityContext


@register_check("duplicates")
class DuplicatesCheck(QualityCheck):
    check_id: ClassVar[str] = "duplicates"
    default_severity: ClassVar[Severity] = Severity.WARNING
    title: ClassVar[str] = "Duplicates"

    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        for spec in ctx.series:
            collided = ctx.bronze.duplicate_event_dates(spec.source_name, spec.symbol)
            if not collided:
                continue
            shown = ", ".join(collided[:5])
            more = "" if len(collided) <= 5 else f" (+{len(collided) - 5} more)"
            findings.append(
                self.finding(
                    spec,
                    f"{spec.source_name}/{spec.symbol} has {len(collided)} event date(s) "
                    "carrying more than one bronze row; each extra copy would double-count "
                    "in silver.",
                    observed=f"duplicate_event_dates={shown}{more}",
                    expected="at most one bronze row per (source, symbol, event_date)",
                )
            )
        return findings
