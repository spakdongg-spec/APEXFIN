"""The tier-aware verdict. This is the differentiator, so it fails loud.

Tier semantics (ARCHITECTURE 5.2):

  - risk_essential staleness  -> BLOCKED, non-zero exit, downstream stops
  - everything else degraded -> DEGRADED, the run still produces output
  - nothing at all           -> PASS

The decision is pure: it reads findings and returns a verdict plus the
supporting detail (`blocking_findings`, `degraded_sources`, `human_summary`).
It writes nothing -- the step that calls it owns persistence, which keeps the
gate liftable out of this repository without dragging the storage layer along.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apexfin.core.enums import GateVerdict, Severity, Tier
from apexfin.core.models import QualityFinding


@dataclass(frozen=True)
class GateDecision:
    """The verdict plus the evidence a human needs to act on it."""

    verdict: GateVerdict
    blocking_findings: tuple[QualityFinding, ...]
    degraded_sources: tuple[str, ...]
    human_summary: str


def decide(findings: Sequence[QualityFinding]) -> GateDecision:
    """Tier-aware verdict from a flat list of findings.

    BLOCKED  if any BLOCKING finding sits on a risk_essential series.
    DEGRADED if there is any finding at all (blocking or warning).
    PASS     otherwise.
    """
    blocking = tuple(f for f in findings if f.severity == Severity.BLOCKING)
    soft = tuple(f for f in findings if f.severity != Severity.BLOCKING)
    risk_blocking = tuple(f for f in blocking if f.tier == Tier.RISK_ESSENTIAL)

    if risk_blocking:
        verdict = GateVerdict.BLOCKED
    elif blocking or soft:
        verdict = GateVerdict.DEGRADED
    else:
        verdict = GateVerdict.PASS

    degraded_sources = tuple(sorted({f.source_name for f in (*blocking, *soft)}))
    summary = _summarise(verdict, risk_blocking, soft)
    return GateDecision(
        verdict=verdict,
        blocking_findings=blocking,
        degraded_sources=degraded_sources,
        human_summary=summary,
    )


def _summarise(
    verdict: GateVerdict,
    risk_blocking: Sequence[QualityFinding],
    soft: Sequence[QualityFinding],
) -> str:
    if verdict is GateVerdict.PASS:
        return "全部数据源通过 6 类质量检查，本日研判可完整产出。"
    if verdict is GateVerdict.BLOCKED:
        names = ", ".join(sorted({f"{f.source_name}/{f.symbol}" for f in risk_blocking}))
        return (
            f"{names} 陈旧或异常，达到阻断阈值，质量闸门判定 BLOCKED——"
            "研判被暂停，页面以故障态呈现，不产出带误导性的结论。"
        )
    # DEGRADED
    if soft:
        names = ", ".join(sorted({f"{f.source_name}/{f.symbol}" for f in soft}))
        return f"{names} 数据不完整（降级），页面仍可阅读，建议补充数据后重跑。"
    names = ", ".join(sorted({f"{f.source_name}/{f.symbol}" for f in risk_blocking}))
    return f"{names} 出现降级，页面仍可阅读，建议补充数据后重跑。"
