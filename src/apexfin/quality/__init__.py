"""L3c governance: the part of this project that is worth copying.

Deliberately low-coupling. It depends on `core` and reads through the narrow
storage ports, never on `sources`, `processing` or `decision`. That is what
makes it liftable into another repository as a whole directory.
"""

from __future__ import annotations

from apexfin.core.models import QualityFinding
from apexfin.core.registry import all_checks
from apexfin.quality.base import QualityContext


def run_all_checks(ctx: QualityContext) -> list[QualityFinding]:
    """Run every registered check and flatten the findings.

    A check that raises is a bug in the check, not a data problem; the runner
    turns that into a step failure rather than a swallowed finding, so a broken
    check cannot masquerade as a clean pass.
    """
    findings: list[QualityFinding] = []
    for check_cls in all_checks().values():
        findings.extend(check_cls().run(ctx))
    return findings


__all__ = ["QualityContext", "all_checks", "run_all_checks"]
