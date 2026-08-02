"""Debate orchestration -- run the analyst framework for a set of decisions.

Kept out of `pipeline/steps.py` so that file stays under the 300-line cap.
This module is the glue between the pipeline (which holds a `RunContext` and a
list of aggregate `Decision`s) and the analyst/debate framework (pure). For
every decision it collects the analyst views, runs the bull/bear debate and
stashes the full result into `Decision.inputs["debate"]` for the dashboard.
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
from apexfin.decision.debate import DebateResult, run_debate
from apexfin.decision.views import MarketViewImpl
from apexfin.pipeline.context import RunContext


def attach_debates(ctx: RunContext, decisions: list[Decision], as_of: date) -> None:
    """Run the bull/bear debate per symbol and stash it in `Decision.inputs`.

    The debate needs a MarketView, rebuilt here from the same sources the
    strategies used. For every decision we run the analyst roles (technical /
    macro / options / cot / text / behavioral), consolidate the bull and bear
    cases, adjudicate, and write the full debate text into
    `inputs["debate"]` so `reporting` can render the analysis chain without
    touching the database again.
    """
    health_rows = ctx.quality.all_health()
    healthy = {h.symbol for h in health_rows if h.state == "healthy"}
    view = MarketViewImpl(ctx.silver, ctx.catalog, as_of, frozenset(healthy))

    for decision in decisions:
        views = _collect_analyst_views(view, decision.symbol, as_of)
        if not views:
            continue
        debate = run_debate(views)
        decision.inputs["debate"] = _debate_to_dict(debate)


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
