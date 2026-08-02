"""The pipeline runner.

Executes the planned steps in order, each inside its own SAVEPOINT so a
failing step rolls back its own writes while the `step_runs` bookkeeping
survives. A failing `critical` step aborts the run; a failing non-critical step
is recorded and the run continues. The quality gate's verdict drives the final
run state and exit code: BLOCKED on a risk-essential breach exits 4, DEGRADED
still exits 0, PASS exits 0.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from apexfin.core.enums import ExitCode, GateVerdict, RunState, StepStatus
from apexfin.core.errors import ApexfinError
from apexfin.core.models import StepResult
from apexfin.pipeline.context import RunContext
from apexfin.pipeline.events import log_step_finished, log_step_started
from apexfin.pipeline.planner import plan
from apexfin.storage.engine import savepoint


@dataclass
class PipelineResult:
    """What a run produced, for the caller to report."""

    exit_code: int
    verdict: GateVerdict
    steps: list[StepResult]


def run_pipeline(
    ctx: RunContext,
    *,
    only: tuple[str, ...] = (),
    skip: tuple[str, ...] = (),
    continue_on_error: bool = False,
) -> PipelineResult:
    steps = plan(keep_daily=True, only=only, skip=skip)
    started_at = ctx.clock.now()
    as_of = ctx.clock.today()
    ctx.run.start_run(ctx.run_id, started_at, as_of, ctx.manifest_hash, ctx.fixture_pack)

    blocked = False
    degraded = False
    results: list[StepResult] = []
    exit_code = ExitCode.OK
    error: BaseException | None = None

    try:
        for step in steps:
            log_step_started(step.name, step.tier.value)
            started = time.monotonic()
            try:
                with savepoint(ctx.conn, step.name):
                    result = step.fn(ctx)
            except ApexfinError:
                raise
            except Exception as exc:  # noqa: BLE001 - record, don't swallow
                duration = time.monotonic() - started
                failed = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    duration_s=round(duration, 4),
                    message=f"{type(exc).__name__}: {exc}",
                )
                ctx.run.record_step(ctx.run_id, step.tier.value, started_at, failed)
                results.append(failed)
                log_step_finished(step.name, failed.status, failed.duration_s)
                if step.critical and not continue_on_error:
                    error = exc
                    exit_code = ExitCode.RUNTIME_ERROR
                    break
                continue

            duration = time.monotonic() - started
            result = result.model_copy(update={"duration_s": round(duration, 4)})
            ctx.run.record_step(ctx.run_id, step.tier.value, started_at, result)
            results.append(result)
            log_step_finished(step.name, result.status, result.duration_s)

            if step.name == "quality_gate":
                if ctx.gate_state == GateVerdict.BLOCKED:
                    blocked = True
                elif ctx.gate_state == GateVerdict.DEGRADED:
                    degraded = True
    finally:
        verdict = GateVerdict.PASS
        if blocked:
            verdict = GateVerdict.BLOCKED
            if error is None:
                exit_code = ExitCode.QUALITY_BLOCKED
        elif degraded:
            verdict = GateVerdict.DEGRADED
        if error is not None and exit_code == ExitCode.OK:
            exit_code = ExitCode.RUNTIME_ERROR
        finished = ctx.clock.now()
        summary = _summarize(verdict, results, error)
        ctx.run.finish_run(ctx.run_id, finished, RunState(verdict.value), int(exit_code), summary)

    return PipelineResult(exit_code=int(exit_code), verdict=verdict, steps=results)


def _summarize(verdict: GateVerdict, results: list[StepResult], error: BaseException | None) -> str:
    if error is not None:
        return f"run aborted: {error}"
    failed = [r.step_name for r in results if r.status == StepStatus.FAILED]
    if failed:
        return f"completed with failing step(s): {', '.join(failed)}"
    return f"gate {verdict.value}"
