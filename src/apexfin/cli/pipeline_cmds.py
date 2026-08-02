"""Pipeline commands: collect / process / quality / decide / render / run.

Standalone commands reuse the registered step functions from
`apexfin.pipeline.steps` and drive them through `run_steps`, a small runner
that mirrors `run_pipeline`'s SAVEPOINT semantics (each step rolls back its own
writes on failure while the `step_runs` bookkeeping survives) without the
planner's dependency pruning, which would wrongly block `apexfin process` when
run after a previous day's collect.

The `render` step is registered here, not in `pipeline.steps`, because it is
the one step that must import `reporting`, and `pipeline` is not allowed to
depend on `reporting` (steps.py documents this arrangement).
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from apexfin.core.config import find_project_root
from apexfin.core.enums import ExitCode, GateVerdict, RunState, StepStatus, Tier
from apexfin.core.errors import ApexfinError, ConfigError
from apexfin.core.models import StepResult
from apexfin.pipeline.collect import collect_step
from apexfin.pipeline.context import RunContext
from apexfin.pipeline.manifest import assert_manifest_ok, load_manifest
from apexfin.pipeline.planner import plan
from apexfin.pipeline.registry import step
from apexfin.pipeline.runner import run_pipeline
from apexfin.pipeline.steps import decide_step, process_silver_step, quality_gate_step
from apexfin.reporting import build_datapack
from apexfin.storage.engine import savepoint

_TIER_BY_STEP = {
    "collect": Tier.RISK_ESSENTIAL,
    "process_silver": Tier.RISK_ESSENTIAL,
    "quality_gate": Tier.RISK_ESSENTIAL,
    "decide": Tier.SUPPORT,
    "render": Tier.DISPLAY_ONLY,
}


def _summary(results: list[StepResult], error: Any) -> str:
    if error is not None:
        return f"run aborted: {error}"
    failed = [r.step_name for r in results if r.status == StepStatus.FAILED]
    if failed:
        return f"completed with failing step(s): {', '.join(failed)}"
    return f"gate {results[-1].status.value if results else 'ok'}"


def run_steps(
    ctx: RunContext,
    steps: list[tuple[str, Any]],
    *,
    continue_on_error: bool = False,
    strict: bool = False,
) -> int:
    """Execute named step functions against one run; returns the exit code."""
    started_at = ctx.clock.now()
    ctx.run.start_run(
        ctx.run_id, started_at, ctx.clock.today(), ctx.manifest_hash, ctx.fixture_pack
    )
    blocked = degraded = False
    error: Any = None
    exit_code = ExitCode.OK
    results: list[StepResult] = []

    for name, fn in steps:
        started = time.monotonic()
        try:
            with savepoint(ctx.conn, name):
                result = fn(ctx)
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            exit_for = exc.exit_code if isinstance(exc, ApexfinError) else ExitCode.RUNTIME_ERROR
            # Recorded in step_runs/summary, and shown on stderr for the operator.
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed = StepResult(
                step_name=name,
                status=StepStatus.FAILED,
                duration_s=round(time.monotonic() - started, 4),
                message=f"{type(exc).__name__}: {exc}",
            )
            ctx.run.record_step(ctx.run_id, _TIER_BY_STEP[name].value, started_at, failed)
            results.append(failed)
            if error is None:
                error = exc
                exit_code = exit_for
            if not continue_on_error:
                break
            continue
        duration = time.monotonic() - started
        result = result.model_copy(update={"duration_s": round(duration, 4)})
        ctx.run.record_step(ctx.run_id, _TIER_BY_STEP[name].value, started_at, result)
        results.append(result)
        if name == "quality_gate":
            if ctx.gate_state == GateVerdict.BLOCKED:
                blocked = True
            elif ctx.gate_state == GateVerdict.DEGRADED:
                degraded = True

    verdict = GateVerdict.PASS
    if blocked:
        verdict = GateVerdict.BLOCKED
        if error is None:
            exit_code = ExitCode.QUALITY_BLOCKED
    elif degraded:
        verdict = GateVerdict.DEGRADED
    if error is not None and exit_code == ExitCode.OK:
        exit_code = ExitCode.RUNTIME_ERROR
    if strict and verdict == GateVerdict.DEGRADED:
        exit_code = ExitCode.QUALITY_BLOCKED

    ctx.run.finish_run(
        ctx.run_id,
        ctx.clock.now(),
        RunState(verdict.value),
        int(exit_code),
        _summary(results, error),
    )
    return int(exit_code)


def cmd_collect(
    ctx: RunContext,
    fixture_pack: str | None,
    *,
    sources: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
    json_output: bool = False,
) -> int:
    ctx = replace(ctx, fixture_pack=fixture_pack)
    code = run_steps(
        ctx,
        [("collect", partial(collect_step, sources=sources, symbols=symbols))],
    )
    if json_output:
        import json as _json

        print(
            _json.dumps(
                {"ok": code == 0, "command": "collect", "run_id": ctx.run_id, "exit_code": code}
            )
        )
    return code


def cmd_process(ctx: RunContext) -> int:
    return run_steps(ctx, [("process_silver", process_silver_step)])


def cmd_quality(ctx: RunContext, *, strict: bool) -> int:
    return run_steps(ctx, [("quality_gate", quality_gate_step)], strict=strict)


def cmd_decide(ctx: RunContext) -> int:
    # Re-run the gate first so a BLOCKED gate refuses with exit 4, not opinions.
    return run_steps(ctx, [("quality_gate", quality_gate_step), ("decide", decide_step)])


def _templates_dir() -> Path:
    templates = find_project_root() / "templates"
    if not templates.is_dir():
        raise ConfigError(f"templates directory not found at {templates}")
    return templates


def render_dashboard(
    ctx: RunContext, out: Path | None = None, *, force_degraded: bool = False
) -> Path:
    """Build the DataPack and render `dashboard.html` to `dist/index.html`."""
    if ctx.run.run_row(ctx.run_id) is None:
        latest = ctx.run.latest_run_id()
        if latest is None:
            raise ConfigError("no run has been recorded yet; run the pipeline before rendering")
        ctx = replace(ctx, run_id=latest)
    datapack = build_datapack(ctx)
    if force_degraded:
        gate = datapack.gate.model_copy(
            update={
                "verdict": "DEGRADED",
                "verdict_label": "降级",
                "icon_id": "alert-triangle",
                "tone": "warn",
                "summary": "强制降级态渲染（--degraded）。",
            }
        )
        from apexfin.reporting.models import Notice

        datapack = datapack.model_copy(
            update={
                "gate": gate,
                "notices": [
                    *datapack.notices,
                    Notice(
                        level="warn",
                        icon_id="alert-triangle",
                        text="强制降级态渲染（--degraded），不代表本次运行实际裁决。",
                    ),
                ],
            }
        )
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        autoescape=True,
    )
    html = env.get_template("dashboard.html").render(datapack=datapack.model_dump(mode="json"))
    target = out or (ctx.settings.dist_dir / "index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


@step(
    "render",
    Tier.DISPLAY_ONLY,
    depends_on=("quality_gate",),
    critical=False,
    timeout_s=60,
    keep_daily=True,
    why="Renders the dashboard including the degraded state, which is how failures become visible.",
)
def render_step(ctx: RunContext) -> StepResult:
    target = render_dashboard(ctx)
    return StepResult(
        step_name="render",
        status=StepStatus.OK,
        duration_s=0.0,
        message=f"wrote {target}",
        metrics={"bytes": float(target.stat().st_size)},
    )


def cmd_run(
    ctx: RunContext,
    *,
    manifest_path: Path | None,
    fixture_pack: str | None,
    only: tuple[str, ...],
    skip: tuple[str, ...],
    continue_on_error: bool,
    json_output: bool = False,
) -> int:
    ctx = replace(ctx, fixture_pack=fixture_pack)
    if manifest_path is not None:
        data = load_manifest(manifest_path)
        assert_manifest_ok(data)
        ctx = replace(
            ctx,
            manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )

    skip_set = set(skip)
    if only and set(only) == {"render"}:
        # `--only render` re-renders the latest finished run; nothing else runs.
        render_step(ctx)
        return int(ExitCode.OK)

    want_render = "render" not in skip_set and (not only or "render" in only)
    # Render is excluded from the runner plan: the footer must carry
    # finished_at, which the runner writes in its `finally`; a mid-chain
    # render would always report 未完成.
    result = run_pipeline(
        ctx,
        only=tuple(o for o in only if o != "render"),
        skip=(*tuple(s for s in skip if s != "render"), "render"),
        continue_on_error=continue_on_error,
    )
    if want_render:
        render_step(ctx)
    if json_output:
        import json as _json

        payload = {
            "ok": int(result.exit_code) == 0,
            "command": "run",
            "run_id": ctx.run_id,
            "exit_code": int(result.exit_code),
            "gate": {"verdict": result.verdict.value},
            "steps": [
                {"name": r.step_name, "status": r.status.value, "duration_s": r.duration_s}
                for r in result.steps
            ],
            "artifacts": (
                {"dashboard": str(ctx.settings.dist_dir / "index.html")} if want_render else {}
            ),
        }
        print(_json.dumps(payload, ensure_ascii=False))
    return int(result.exit_code)


def dry_run_plan(only: tuple[str, ...], skip: tuple[str, ...]) -> list[str]:
    return [s.name for s in plan(keep_daily=True, only=only, skip=skip)]
