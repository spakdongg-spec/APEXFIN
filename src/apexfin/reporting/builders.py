"""Assembly of the data-quality DataPack sections: gate, matrix, health.

Split out of `datapack.py` so that module stays a thin composition root: the
question "what does the dashboard contain" and the question "how is each part
computed" have different reasons to change, and keeping them together is what
pushed the original file past the 300-line limit. The run-side sections live in
`reporting.run_view`; charts live in `reporting.charts`.

Every function returns a validated model from `reporting.models`, so a wrong
key or a stringified number fails at this boundary rather than in the browser.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from apexfin.core.enums import GateVerdict, Severity
from apexfin.core.models import QualityFinding, SeriesHealth
from apexfin.reporting.models import (
    CheckDef,
    Freshness,
    GateBlock,
    HealthRow,
    MatrixCell,
    MatrixRow,
    QualityMatrix,
    SourceChip,
)
from apexfin.reporting.state_maps import (
    CHECK_DEFS,
    CHECK_KEY_BY_ID,
    GATE_PRESENTATION,
    STATE_PRESENTATION,
)

_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

_UNKNOWN_STATE = ("未知", "circle-dashed", "muted")

#: Worst-wins ordering when several symbols roll up into one source chip.
#: `unknown` outranks `healthy` on purpose: a series nobody has ever collected
#: is not evidence that the source is fine.
_STATE_RANK = {"healthy": 0, "unknown": 1, "degraded": 2, "blocked": 3}

#: Display name for a series, keyed by (source_name, symbol).
DisplayMap = Mapping[tuple[str, str], str]


def weekday_label(value: Any) -> str:
    """`07-31（周五）`. The weekday is not decoration: a reader checking whether
    a daily series is late needs to know the last event was a Friday."""
    return f"{value.strftime('%m-%d')}（{_WEEKDAYS[value.weekday()]}）"


def _display(source_name: str, symbol: str, display: DisplayMap) -> str:
    return display.get((source_name, symbol), source_name)


def build_gate(
    verdict: GateVerdict,
    summary: str,
    health: Sequence[SeriesHealth],
    display: DisplayMap,
) -> GateBlock:
    """The verdict banner, with one chip per source rather than per series.

    Rolling symbols up to their source is the point of the banner: a reader
    scanning it wants to know which *feed* to distrust, and thirty chips for
    thirty tickers communicates nothing. The roll-up takes the worst state, so
    one broken symbol cannot hide behind twenty healthy siblings.
    """
    label, icon_id, tone = GATE_PRESENTATION[verdict.value]

    worst: dict[str, str] = {}
    order: list[str] = []
    for row in health:
        name = _display(row.source_name, row.symbol, display)
        if name not in worst:
            order.append(name)
            worst[name] = row.state
        elif _STATE_RANK.get(row.state, 1) > _STATE_RANK.get(worst[name], 1):
            worst[name] = row.state

    chips: list[SourceChip] = []
    for name in order:
        state = worst[name]
        text, chip_icon, chip_tone = STATE_PRESENTATION.get(state, _UNKNOWN_STATE)
        chips.append(
            SourceChip(
                source_name=name,
                state=state,  # type: ignore[arg-type]
                label_text=text,
                icon_id=chip_icon,
                tone=chip_tone,  # type: ignore[arg-type]
            )
        )

    return GateBlock(
        verdict=verdict.value,
        verdict_label=label,
        icon_id=icon_id,
        tone=tone,  # type: ignore[arg-type]
        summary=_gate_summary(verdict, summary),
        sources=chips,
    )


def _gate_summary(verdict: GateVerdict, summary: str) -> str:
    if summary:
        return summary
    if verdict is GateVerdict.PASS:
        return "全部数据源通过 6 类质量检查，下游决策照常产出。"
    if verdict is GateVerdict.BLOCKED:
        return "质量闸门判定 BLOCKED，下游决策被阻断，看板渲染降级态。"
    return "部分数据源降级，看板仍可用，建议择机重跑采集。"


def build_quality_matrix(
    findings: Sequence[QualityFinding], display: DisplayMap, sources: Sequence[str]
) -> QualityMatrix:
    """Six checks across every configured source, including the clean ones.

    A row with no findings is the evidence that the checks ran and passed.
    Omitting it would make "clean" indistinguishable from "never checked",
    which is the single most expensive ambiguity in a governance dashboard.
    """
    by_source: dict[str, list[QualityFinding]] = defaultdict(list)
    for finding in findings:
        name = _display(finding.source_name, finding.symbol or "", display)
        by_source[name].append(finding)

    rows: list[MatrixRow] = []
    for name in sources:
        cells = {chk["key"]: _cell(name, chk, by_source.get(name, ())) for chk in CHECK_DEFS}
        passed = sum(1 for c in cells.values() if c.state == "healthy")
        total = len(CHECK_DEFS)
        rows.append(
            MatrixRow(
                source_name=name,
                cells=cells,
                pass_count=passed,
                total=total,
                rate=passed / total,
                rate_state="ok" if passed == total else "warn",
            )
        )

    checks = [
        CheckDef(key=c["key"], label_zh=c["label_zh"], label_en=c["label_en"]) for c in CHECK_DEFS
    ]
    return QualityMatrix(checks=checks, rows=rows)


def _cell(name: str, chk: Mapping[str, str], findings: Sequence[QualityFinding]) -> MatrixCell:
    hits = [f for f in findings if CHECK_KEY_BY_ID.get(f.check_id) == chk["key"]]
    if not hits:
        state = "healthy"
    elif any(f.severity == Severity.BLOCKING for f in hits):
        state = "blocked"
    else:
        state = "degraded"
    state_label = STATE_PRESENTATION.get(state, _UNKNOWN_STATE)[0]
    return MatrixCell(
        state=state,  # type: ignore[arg-type]
        cell_value=state,
        icon_id=STATE_PRESENTATION[state][1],
        cell_tooltip=f"{name} · {chk['label_zh']} · {state_label}",
    )


def build_health_rows(health: Sequence[SeriesHealth], display: DisplayMap) -> list[HealthRow]:
    rows: list[HealthRow] = []
    for h in health:
        label, icon_id, tone = STATE_PRESENTATION.get(h.state, _UNKNOWN_STATE)
        rows.append(
            HealthRow(
                source_name=_display(h.source_name, h.symbol, display),
                symbol=h.symbol,
                state=h.state,  # type: ignore[arg-type]
                label_text=label,
                icon_id=icon_id,
                tone=tone,  # type: ignore[arg-type]
                lag_trading_days=h.lag_trading_days,
                max_lag_trading_days=max(h.max_lag_trading_days, 1),
                freshness=_freshness(h),
                last_event_date=(
                    None if h.last_event_date is None else h.last_event_date.isoformat()
                ),
                last_event_label=(
                    None if h.last_event_date is None else weekday_label(h.last_event_date)
                ),
                note=h.note,
            )
        )
    return rows


def _freshness(h: SeriesHealth) -> Freshness | None:
    """The pre-computed bar. `None` for a series that has never been seen --
    a zero-length bar would read as "perfectly fresh"."""
    if h.lag_trading_days is None:
        return None
    bar_max = max(h.max_lag_trading_days, 1)
    overdue = h.lag_trading_days > h.max_lag_trading_days
    diff = abs(h.lag_trading_days - h.max_lag_trading_days)
    return Freshness(
        bar_value=min(h.lag_trading_days, bar_max),
        bar_max=bar_max,
        overdue=overdue,
        label=f"阈值 {h.max_lag_trading_days} 交易日 · {'超' if overdue else '余'} {diff}",
    )
