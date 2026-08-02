"""Composition root of the DataPack -- the single object the template reads.

This module answers one question: *what does the dashboard contain, and where
does each part come from*. How each part is computed lives in
`reporting.builders` and `reporting.charts`. Keeping the two apart is what lets
this file be read top-to-bottom as a table of contents.

The template does no computation and touches no repository (ARCHITECTURE 9.3):
every number, label and bar width is finished here. `reporting` is constrained
to {core, storage} by the architecture test, so everything is read through the
repositories on the run context -- it can report on the pipeline, it can never
change it.
"""

from __future__ import annotations

from typing import Any

from apexfin.core.clock import to_utc_iso
from apexfin.core.enums import GateVerdict
from apexfin.core.models import SeriesSpec
from apexfin.reporting.builders import build_gate, build_health_rows, build_quality_matrix
from apexfin.reporting.charts import build_charts
from apexfin.reporting.models import DataPack
from apexfin.reporting.run_view import (
    build_decisions,
    build_notices,
    build_run_footer,
    build_steps,
)


def build_datapack(ctx: Any) -> DataPack:
    """Build the dashboard DataPack from the run context and its repositories.

    `ctx` is the pipeline `RunContext`, typed loosely because importing it here
    would point an L5 module at L4. It must expose `run_id`, `clock`,
    `catalog`, `quality`, `run`, `decision` and `silver`.
    """
    run_row = ctx.run.run_row(ctx.run_id)
    findings = ctx.quality.findings_for_run(ctx.run_id)
    health = ctx.quality.all_health()
    steps = ctx.run.steps_for_run(ctx.run_id)
    decisions = ctx.decision.decisions_for_run(ctx.run_id)

    specs = list(ctx.catalog.series(enabled_only=False))
    display = {(s.source_name, s.symbol): _display_name(s) for s in specs}
    sources = _ordered_sources(specs)

    verdict = _verdict(run_row)
    summary = (run_row["summary"] if run_row is not None else "") or ""

    return DataPack(
        generated_at=to_utc_iso(ctx.clock.now()),
        run_id=ctx.run_id,
        gate=build_gate(verdict, summary, health, display),
        quality_matrix=build_quality_matrix(findings, display, sources),
        health_rows=build_health_rows(health, display),
        steps=build_steps(steps),
        decisions=build_decisions(decisions),
        charts=build_charts(ctx.catalog, ctx.silver),
        notices=build_notices(verdict, summary),
        run_footer=build_run_footer(run_row),
    )


def build_datapack_dict(ctx: Any) -> dict[str, Any]:
    """JSON-ready form, for the template and for `apexfin report --json`."""
    return build_datapack(ctx).model_dump(mode="json")


def _display_name(spec: SeriesSpec) -> str:
    """`source/domain`, which is what an operator calls a feed.

    A bare `yahoo` is ambiguous once the same collector serves equities and
    indices; the dashboard has to name the thing that can be re-run on its own.
    """
    return f"{spec.source_name}/{spec.domain}"


def _ordered_sources(specs: list[SeriesSpec]) -> list[str]:
    """Distinct feeds in configuration order -- stable across runs so the
    matrix does not reshuffle its rows between two renders of the same data."""
    seen: list[str] = []
    for spec in specs:
        name = _display_name(spec)
        if name not in seen:
            seen.append(name)
    return seen


def _verdict(run_row: Any) -> GateVerdict:
    """The run's gate verdict, defaulting to PASS only when there is no row.

    `RUNNING` and `FAILED` are valid run states that are not gate verdicts, so
    they are mapped to PASS for the banner rather than raising: a crashed run
    still has to render, and the footer is where "did not finish" is reported.
    """
    if run_row is None:
        return GateVerdict.PASS
    raw = str(run_row["state"])
    known = {v.value for v in GateVerdict}
    return GateVerdict(raw) if raw in known else GateVerdict.PASS
