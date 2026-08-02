"""Debate orchestration -- run the analyst framework and produce decisions.

Kept out of `pipeline/steps.py` so that file stays under the 300-line cap.
This module is the glue between the pipeline (which holds a `RunContext`) and
the analyst/debate framework (pure). For every symbol it collects the analyst
views, runs the bull/bear debate, and turns the verdict into a `Decision` that
fits the existing decisions table (stance / confidence / rationale / inputs),
with the full debate text stashed in `inputs["debate"]` for the dashboard.
"""

from __future__ import annotations

from datetime import date

from apexfin.core.models import Decision
from apexfin.decision.analysts.contracts import AnalystView
from apexfin.decision.analysts.macro import analyze_macro
from apexfin.decision.analysts.technical import analyze_technical
from apexfin.decision.analysts.uncovered import (
    analyze_behavioral,
    analyze_cot,
    analyze_options,
    analyze_text,
)
from apexfin.decision.debate import ROLE_WEIGHT, DebateResult, run_debate
from apexfin.decision.views import MarketViewImpl
from apexfin.pipeline.context import RunContext


def decide_all(ctx: RunContext, run_id: str, as_of: date, degraded: bool) -> list[Decision]:
    """Run the analyst framework for every catalog symbol and emit decisions.

    The stance comes from the bull/bear debate verdict: AFFIRM -> long,
    REJECT -> short, MODIFY keeps the direction of the dominant side (or
    `no_call` when evidence is genuinely split past the verdict threshold).
    """
    health_rows = ctx.quality.all_health()
    healthy = {h.symbol for h in health_rows if h.state == "healthy"}
    view = MarketViewImpl(ctx.silver, ctx.catalog, as_of, frozenset(healthy))

    decisions: list[Decision] = []
    for spec in ctx.catalog.series(enabled_only=True):
        # Macro readings (CPI, yields, VIX) are inputs to the framework, not
        # tradeable targets: no direction decision is emitted for them. A
        # fabricated "long CPI" would be a category error, not analysis.
        if spec.domain != "equity":
            continue
        views = _collect_analyst_views(view, spec.symbol, as_of)
        debate = run_debate(views)
        decisions.append(_decision_from_debate(run_id, spec.symbol, as_of, debate, degraded))
    return decisions


def _decision_from_debate(
    run_id: str, symbol: str, as_of: date, debate: DebateResult, degraded: bool
) -> Decision:
    """Map a DebateResult to a Decision row (stance/confidence/rationale)."""
    stance = _VERDICT_STANCE.get(debate.verdict_code, "no_call")
    if stance == "no_call" and debate.verdict_code == "MODIFY":
        stance = _dominant_stance(debate)
    confidence = round(debate.conviction, 4)
    return Decision(
        run_id=run_id,
        as_of=as_of,
        symbol=symbol,
        stance=stance,  # type: ignore[arg-type]
        confidence=confidence,
        strategy="debate",
        rationale=_rationale(debate),
        inputs={"debate": _debate_to_dict(debate)},
        contributing_signals=tuple(v.role for v in debate.analyst_views if v.available),
        degraded=degraded,
    )


#: Verdict -> stance. MODIFY is resolved by `_dominant_stance` below.
_VERDICT_STANCE = {
    "AFFIRM": "long",
    "REJECT": "short",
    "MODIFY": "no_call",
}


def _dominant_stance(debate: DebateResult) -> str:
    """Direction of the heavier side; flat when the debate is genuinely empty."""
    bull_w = sum(
        _weight(v.role) * v.confidence / 100.0
        for v in debate.analyst_views
        if v.direction == "long"
    )
    bear_w = sum(
        _weight(v.role) * v.confidence / 100.0
        for v in debate.analyst_views
        if v.direction == "short"
    )
    if bull_w + bear_w == 0:
        return "flat"
    return "long" if bull_w >= bear_w else "short"


def _weight(role: str) -> float:
    return ROLE_WEIGHT.get(role, 1.0)


def _rationale(debate: DebateResult) -> str:
    """One-paragraph verdict summary stored as the decision's rationale."""
    head = (
        f"{debate.verdict_code}（{debate.verdict_why}；信念{debate.conviction_label}，"
        f"{(debate.conviction * 100):.0f}%；维度：{debate.dimension_summary}）"
    )
    if debate.verdict_code == "AFFIRM":
        first = debate.bull_case.splitlines()[0] if debate.bull_case else ""
        return f"{head}。多头论据占优：{first}"
    if debate.verdict_code == "REJECT":
        first = debate.bear_case.splitlines()[0] if debate.bear_case else ""
        return f"{head}。空头论据占优：{first}"
    return f"{head}。多空论据接近，保留反向触发条件，不构成明确方向观点。"


def _collect_analyst_views(view: MarketViewImpl, symbol: str, as_of: date) -> list[AnalystView]:
    """Run every analyst role for one symbol; price roles only when healthy."""
    points = view.series(symbol, lookback=30)
    views: list[AnalystView] = []
    if view.is_healthy(symbol):
        views.append(analyze_technical(symbol, points, as_of))
        views.append(analyze_macro(view, symbol, as_of))
    else:
        views.append(
            AnalystView(
                role="technical",
                symbol=symbol,
                direction="neutral",
                confidence=0.0,
                available=False,
                note="数据源不健康，拒绝在陈旧或残缺的序列上给出观点",
                as_of=as_of,
            )
        )
    views.append(analyze_options(symbol, as_of))
    views.append(analyze_cot(symbol, as_of))
    views.append(analyze_text(symbol, as_of))
    views.append(analyze_behavioral(symbol, as_of))
    return views


def _debate_to_dict(debate: DebateResult) -> dict[str, object]:
    """Stable JSON shape for `Decision.inputs["debate"]` (dashboard contract)."""
    return {
        "verdict_code": debate.verdict_code,
        "verdict_why": debate.verdict_why,
        "conviction": debate.conviction,
        "conviction_label": debate.conviction_label,
        "bull_case": debate.bull_case,
        "bear_case": debate.bear_case,
        "rebuttal": debate.rebuttal,
        "risk_notes": debate.risk_notes,
        "dimension_summary": debate.dimension_summary,
        "analysts": [
            {
                "role": v.role,
                "direction": v.direction,
                "confidence": v.confidence,
                "evidence": v.evidence,
                "note": v.note,
                "available": v.available,
            }
            for v in debate.analyst_views
        ],
    }
