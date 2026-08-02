"""The run-side DataPack sections: timeline, decisions, notices, footer.

Separated from `builders.py` (which assembles the data-quality sections) so
neither file has to grow past the 300-line limit to accommodate the other, and
so a change to how a decision is displayed cannot accidentally touch how the
quality matrix is built.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from apexfin.core.clock import parse_utc, to_utc_iso
from apexfin.core.enums import STANCE_PRESENTATION, GateVerdict
from apexfin.core.models import Decision
from apexfin.reporting.models import (
    DebateAnalyst,
    DebateDetail,
    DecisionRow,
    Notice,
    RunFooter,
    SignalDetail,
    StepRow,
)
from apexfin.reporting.state_maps import STATUS_PRESENTATION

_UNKNOWN_STATUS = ("未知", "circle-dashed")

#: Below this many seconds the footer says "不到 1 分钟" instead of a number.
_SUB_MINUTE = 60.0


def build_steps(steps: Sequence[tuple[Any, ...]]) -> list[StepRow]:
    """Rows of the run timeline, from `RunRepository.steps_for_run`.

    `status` is lower-cased here because the database stores it upper-case and
    the template's CSS selectors were written against the lower-case form.

    The schema allows `running`, which this backend never emits: a step row is
    written on completion, so a half-finished step has no row at all. Stating
    that plainly beats inventing a placeholder row -- if live progress is ever
    wanted, the writer has to change, not the renderer.
    """
    rows: list[StepRow] = []
    for step_name, tier, status, started_at, duration_s, message, _metrics in steps:
        name = status.value.lower()
        label, icon_id = STATUS_PRESENTATION.get(name, _UNKNOWN_STATUS)
        rows.append(
            StepRow(
                step_name=step_name,
                tier=tier,
                # Marks a blocking tier apart from an advisory one. The current
                # template ignores this field; it stays because it is part of
                # the published fixture contract and silently dropping a key
                # from a contract is how a frontend breaks in production.
                tier_state="ok" if tier == "risk_essential" else "warn",
                status=name,
                status_label=label,
                icon_id=icon_id,
                duration_s=duration_s,
                duration_label=None if duration_s is None else f"{duration_s:.1f} 秒",
                ran_at=None if started_at is None else started_at.strftime("%H:%M"),
                note=message,
            )
        )
    return rows


def build_decisions(decisions: Sequence[Decision]) -> list[DecisionRow]:
    """One row per stance, `no_call` included.

    A `no_call` renders with a flat arrow -- there is nowhere else for it to
    point -- but its label says 无观点, not 中性. Those are different claims and
    the table has to keep them apart.

    Each row also carries the per-strategy `signals` breakdown stored in
    `inputs["signals"]`, so the board shows the analysis chain (which strategy
    said what) instead of only the verdict.
    """
    rows: list[DecisionRow] = []
    for index, d in enumerate(decisions):
        direction, label = STANCE_PRESENTATION.get(d.stance, ("flat", "中性"))
        raw_signals = d.inputs.get("signals", [])
        details: list[SignalDetail] = []
        for raw in raw_signals:
            if not isinstance(raw, dict):
                continue
            try:
                details.append(
                    SignalDetail(
                        strategy=str(raw.get("strategy", "?")),
                        direction=str(raw.get("direction", "flat")),  # type: ignore[arg-type]
                        strength=float(raw.get("strength", 0.0)),
                        rationale=str(raw.get("rationale", "")),
                    )
                )
            except (TypeError, ValueError):
                continue
        rows.append(
            DecisionRow(
                decision_id=f"d-{index + 1:03d}",
                symbol=d.symbol,
                direction=direction,  # type: ignore[arg-type]
                direction_label=label,
                rationale=d.rationale,
                score=round(float(d.confidence), 4),
                as_of=d.as_of.isoformat(),
                signals=details,
                debate=_build_debate(d.inputs.get("debate")),
            )
        )
    return rows


def _build_debate(raw: object) -> DebateDetail | None:
    """Parse `Decision.inputs["debate"]` into a renderable DebateDetail."""
    if not isinstance(raw, dict):
        return None
    try:
        analysts = [
            DebateAnalyst(
                role=str(a.get("role", "?")),
                direction=str(a.get("direction", "neutral")),  # type: ignore[arg-type]
                confidence=float(a.get("confidence", 0.0)),
                evidence=[str(e) for e in a.get("evidence", []) if e],
                note=str(a.get("note", "")),
                available=bool(a.get("available", True)),
            )
            for a in raw.get("analysts", [])
            if isinstance(a, dict)
        ]
        return DebateDetail(
            verdict_code=str(raw.get("verdict_code", "MODIFY")),  # type: ignore[arg-type]
            verdict_why=str(raw.get("verdict_why", "")),
            conviction=float(raw.get("conviction", 0.0)),
            conviction_label=str(raw.get("conviction_label", "弱")),
            bull_case=str(raw.get("bull_case", "")),
            bear_case=str(raw.get("bear_case", "")),
            rebuttal=str(raw.get("rebuttal", "")),
            risk_notes=str(raw.get("risk_notes", "")),
            dimension_summary=str(raw.get("dimension_summary", "")),
            analysts=analysts,
        )
    except (TypeError, ValueError):
        return None


def build_notices(verdict: GateVerdict, summary: str) -> list[Notice]:
    if verdict is GateVerdict.BLOCKED:
        return [Notice(level="danger", icon_id="x-octagon", text=summary)]
    if verdict is GateVerdict.DEGRADED:
        return [Notice(level="warn", icon_id="alert-triangle", text=summary)]
    return []


def build_run_footer(run_row: Any) -> RunFooter:
    """Provenance line at the bottom of the page.

    A run with no `finished_at` did not finish: the process was killed, the
    container went away, or the writer died before its `finally` block.
    Substituting the render time and reporting "不到 1 分钟" would turn a crashed
    run into a fast one -- precisely the silent lie this project exists to make
    impossible. So it says 未完成 and gives no duration at all.
    """
    finished_raw = None if run_row is None else run_row["finished_at"]
    if finished_raw is None:
        return RunFooter(
            finished_at=None,
            finished_label="未完成",
            duration_label="未完成（进程未正常结束，耗时不可知）",
        )

    finished = parse_utc(str(finished_raw))
    started_raw = run_row["started_at"]
    started = finished if started_raw is None else parse_utc(str(started_raw))
    duration = max(0.0, (finished - started).total_seconds())

    tz = finished.strftime("%z") or "+0000"
    offset = f"{tz[:3]}:{tz[3:]}" if len(tz) == 5 else "+00:00"
    return RunFooter(
        finished_at=to_utc_iso(finished),
        finished_label=f"{finished.strftime('%Y-%m-%d %H:%M')}（{offset}）",
        duration_label=(
            "不到 1 分钟" if duration < _SUB_MINUTE else f"约 {round(duration / 60)} 分钟"
        ),
    )
