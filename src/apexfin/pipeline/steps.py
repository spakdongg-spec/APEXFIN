"""The daily-chain step functions (L4).

Three of the five manifest steps live here; `collect` lives in
`pipeline.collect` and `render` is registered by the composition root (`cli`),
because those two are the steps that must import things `pipeline` may not
depend on (the fixture sources and `reporting` respectively).

Each step receives a `RunContext`, does its work through the repositories on it,
persists what it must, and returns a `StepResult`. The runner measures the real
duration and records the step; the step itself passes `duration_s=0.0`.
"""

from __future__ import annotations

from apexfin.accounting.ledger import write_opinion_ledger
from apexfin.core.enums import GateVerdict, Severity, StepStatus, Tier
from apexfin.core.models import SeriesHealth, StepResult
from apexfin.decision.orchestrate import decide_all
from apexfin.pipeline.context import RunContext
from apexfin.pipeline.registry import step
from apexfin.processing.quality_score import ScoringPolicy
from apexfin.processing.silver_builder import build as build_silver
from apexfin.quality import run_all_checks
from apexfin.quality.base import QualityContext
from apexfin.quality.gate import decide as decide_gate
from apexfin.quality.health import compute_series_health

#: Horizon of a daily opinion, in trading days (O-07: no other unit exists).
_DECISION_HORIZON_DAYS = 5

#: Every stance is counted; a metrics dict that omits `no_call` hides silence.
_STANCES = ("long", "short", "flat", "no_call")


@step(
    "process_silver",
    Tier.RISK_ESSENTIAL,
    depends_on=("collect",),
    critical=True,
    why="Normalizes payloads into comparable numeric points that checks and strategies read.",
)
def process_silver_step(ctx: RunContext) -> StepResult:
    now = ctx.clock.now()
    records = ctx.bronze.unprocessed()
    if not records:
        return StepResult(
            step_name="process_silver",
            status=StepStatus.OK,
            duration_s=0.0,
            message="no unprocessed bronze rows",
            metrics={"points": 0.0, "skipped": 0.0},
        )

    policy = ScoringPolicy(
        reliability=ctx.catalog.reliability_map(),
        max_lag=ctx.expectations.max_lag_map(),
        expects_secondary=ctx.expectations.expects_secondary_map(),
    )
    outcome = build_silver(records, calendar=ctx.calendar, as_of=ctx.clock.today(), policy=policy)
    written = ctx.silver.upsert(outcome.points, ctx.run_id, now)

    reasons = [s.reason for s in outcome.skipped]
    message = f"built {written} silver point(s); {len(outcome.skipped)} skipped"
    if reasons:
        message += "; " + "; ".join(reasons[:3])
    return StepResult(
        step_name="process_silver",
        status=StepStatus.OK,
        duration_s=0.0,
        message=message,
        metrics={**outcome.metrics, "written": float(written)},
    )


@step(
    "quality_gate",
    Tier.RISK_ESSENTIAL,
    depends_on=("process_silver",),
    critical=True,
    why="Blocks the run when risk-essential series go stale (core promise).",
)
def quality_gate_step(ctx: RunContext) -> StepResult:
    now = ctx.clock.now()
    series = ctx.catalog.series(enabled_only=True)
    qctx = QualityContext(
        run_id=ctx.run_id,
        clock=ctx.clock,
        calendar=ctx.calendar,
        expectations=ctx.expectations,
        series=series,
        silver=ctx.silver,
        bronze=ctx.bronze,
    )
    findings = run_all_checks(qctx)
    gate = decide_gate(findings)
    ctx.quality.write_findings(tuple(findings), ctx.run_id, now)

    health: tuple[SeriesHealth, ...] = compute_series_health(qctx, ctx.quality)
    for row in health:
        ctx.quality.upsert_health(row)

    ctx.gate_state = gate.verdict

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in Severity}
    # Verdict omitted: metrics is dict[str, float]; the verdict rides in message/gate_state.
    return StepResult(
        step_name="quality_gate",
        status=StepStatus.OK,
        duration_s=0.0,
        message=gate.human_summary,
        metrics={
            "findings": float(len(findings)),
            "blocking": float(counts[Severity.BLOCKING]),
            "warning": float(counts[Severity.WARNING]),
        },
    )


@step(
    "decide",
    Tier.SUPPORT,
    depends_on=("quality_gate",),
    why="Produces the daily stance; skipped automatically when the gate is BLOCKED.",
)
def decide_step(ctx: RunContext) -> StepResult:
    now = ctx.clock.now()
    if ctx.gate_state == GateVerdict.BLOCKED:
        return StepResult(
            step_name="decide",
            status=StepStatus.SKIPPED,
            duration_s=0.0,
            message="gate BLOCKED; decision step skipped",
            metrics={},
        )

    as_of = ctx.clock.today()

    degraded = ctx.gate_state == GateVerdict.DEGRADED
    decisions = decide_all(ctx, ctx.run_id, as_of, degraded)

    specs = ctx.catalog.series(enabled_only=True)
    sym_to_source = {spec.symbol: spec.source_name for spec in specs}

    written = 0
    for decision in decisions:
        decision_id = ctx.decision.write(decision, now)
        points = ctx.silver.series(
            sym_to_source.get(decision.symbol, decision.symbol), decision.symbol, lookback=1
        )
        reference_value = float(points[-1].value) if points else 0.0
        write_opinion_ledger(
            ctx.decision,
            decision,
            decision_id,
            reference_value=reference_value,
            due_on=ctx.calendar.add_trading_days(as_of, _DECISION_HORIZON_DAYS),
            horizon_days=_DECISION_HORIZON_DAYS,
        )
        written += 1

    stances = {s: float(sum(1 for d in decisions if d.stance == s)) for s in _STANCES}
    return StepResult(
        step_name="decide",
        status=StepStatus.OK,
        duration_s=0.0,
        message=f"wrote {written} decision(s); "
        + ", ".join(f"{name} {int(count)}" for name, count in stances.items() if count),
        metrics={"decisions": float(written), **stances},
    )
