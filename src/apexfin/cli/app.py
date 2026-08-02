"""CLI composition root: the only place that wires everything together.

Builds one SQLite connection, migrates it, constructs the five repositories
and the `RunContext`, registers the `render` step, and exposes the ten
commands from docs/CLI_CONTRACT.md. The object graph itself lives in
`cli.context.build_context`; this file is the Typer wiring table.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

import apexfin
from apexfin.cli import admin_cmds, pipeline_cmds
from apexfin.cli.context import build_context
from apexfin.cli.state import CliState
from apexfin.core.config import find_project_root
from apexfin.core.errors import ApexfinError
from apexfin.core.logging import configure_logging

app = typer.Typer(
    help="APEXFIN - forkable financial data engineering skeleton. "
    "Offline demo: `apexfin init && apexfin run daily --fixture-pack fresh`.",
    no_args_is_help=True,
)
run_app = typer.Typer(help="Run the daily pipeline chain.")
manifest_app = typer.Typer(help="Validate or inspect the pipeline manifest.")
plugins_app = typer.Typer(help="List builtin and third-party registrations.")
app.add_typer(run_app, name="run")
app.add_typer(manifest_app, name="manifest")
app.add_typer(plugins_app, name="plugins")


def _version_callback(value: bool) -> None:
    if value:
        print(f"apexfin {apexfin.__version__}")
        raise typer.Exit()


@app.callback()
def _cli(
    ctx: typer.Context,
    db: Path | None = typer.Option(None, "--db", help="SQLite path (env APEXFIN_DB)"),
    config: Path | None = typer.Option(None, "--config", help="config directory"),
    log_level: str = typer.Option("info", "--log-level"),
    json_output: bool = typer.Option(False, "--json", help="machine-readable stdout"),
    as_of: str | None = typer.Option(None, "--as-of", help="YYYY-MM-DD; freeze the clock"),
    dry_run: bool = typer.Option(False, "--dry-run", help="plan only, write nothing"),
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    ctx.obj = CliState(
        root=find_project_root(),
        db=db,
        config_dir=config,
        log_level=log_level,
        json_output=json_output,
        as_of=as_of,
        dry_run=dry_run,
    )
    # Logs must never land on stdout (CLI_CONTRACT 3.2), least of all in
    # --json mode, where stdout carries exactly one JSON object.
    configure_logging(log_level)


def _run(state: CliState, fn: Callable[..., int], *args: Any, **kwargs: Any) -> None:
    """Invoke a command, mapping ApexfinError to its contracted exit code."""
    try:
        code = fn(*args, **kwargs)
    except ApexfinError as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = exc.exit_code
    if code:
        raise typer.Exit(code)


def _dry(state: CliState, names: list[str]) -> None:
    if state.json_output:
        print(json.dumps({"ok": True, "dry_run": True, "steps": names}, ensure_ascii=False))
    else:
        print("dry-run: would run " + ", ".join(names))


@app.command("init")
def init(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="recreate the database"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["init"])
        return
    if force:
        target = state.db or (state.root / "data" / "apexfin.db")
        target.unlink(missing_ok=True)
    _run(state, admin_cmds.cmd_init, state)


@app.command("collect")
def collect(
    ctx: typer.Context,
    source: list[str] = typer.Option([], "--source", help="collect only these sources"),
    symbol: list[str] = typer.Option([], "--symbol", help="collect only these symbols"),
    full: bool = typer.Option(False, "--full"),
    since: str | None = typer.Option(None, "--since"),
    fixture_pack: str | None = typer.Option(None, "--fixture-pack"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["collect"])
        return
    cctx = build_context(state, fixture_pack=fixture_pack)
    _run(
        state,
        pipeline_cmds.cmd_collect,
        cctx,
        fixture_pack,
        sources=tuple(source),
        symbols=tuple(symbol),
        json_output=state.json_output,
    )


@app.command("process")
def process(
    ctx: typer.Context,
    full: bool = typer.Option(False, "--full"),
    source: list[str] = typer.Option([], "--source"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["process_silver"])
        return
    cctx = build_context(state)
    _run(state, pipeline_cmds.cmd_process, cctx)


@app.command("quality")
def quality(
    ctx: typer.Context,
    check: list[str] = typer.Option([], "--check"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["quality_gate"])
        return
    cctx = build_context(state)
    _run(state, pipeline_cmds.cmd_quality, cctx, strict=strict)


@app.command("decide")
def decide(
    ctx: typer.Context,
    horizon_days: int = typer.Option(5, "--horizon-days"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["quality_gate", "decide"])
        return
    cctx = build_context(state)
    _run(state, pipeline_cmds.cmd_decide, cctx)


@app.command("render")
def render(
    ctx: typer.Context,
    out: Path | None = typer.Option(None, "--out"),
    degraded: bool = typer.Option(False, "--degraded"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, ["render"])
        return
    cctx = build_context(state)
    try:
        target = pipeline_cmds.render_dashboard(cctx, out=out, force_degraded=degraded)
    except ApexfinError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise typer.Exit(exc.exit_code) from None
    if state.json_output:
        payload = {"ok": True, "command": "render", "artifacts": {"dashboard": str(target)}}
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"render: wrote {target}")


@run_app.command("daily")
def run_daily(
    ctx: typer.Context,
    manifest: Path | None = typer.Option(None, "--manifest"),
    fixture_pack: str | None = typer.Option(None, "--fixture-pack"),
    only: list[str] = typer.Option([], "--only"),
    skip: list[str] = typer.Option([], "--skip"),
    continue_on_error: bool = typer.Option(False, "--continue-on-error"),
) -> None:
    state: CliState = ctx.obj
    if state.dry_run:
        _dry(state, pipeline_cmds.dry_run_plan(tuple(only), tuple(skip)))
        return
    cctx = build_context(state, fixture_pack=fixture_pack)
    _run(
        state,
        pipeline_cmds.cmd_run,
        cctx,
        manifest_path=manifest,
        fixture_pack=fixture_pack,
        only=tuple(only),
        skip=tuple(skip),
        continue_on_error=continue_on_error,
        json_output=state.json_output,
    )


@manifest_app.command("validate")
def manifest_validate(
    ctx: typer.Context,
    manifest_path: Path | None = typer.Option(None, "--manifest"),
) -> None:
    state: CliState = ctx.obj
    _run(state, admin_cmds.cmd_manifest_validate, state, manifest_path)


@manifest_app.command("show")
def manifest_show(
    ctx: typer.Context,
    tier: str | None = typer.Option(None, "--tier"),
) -> None:
    state: CliState = ctx.obj
    _run(state, admin_cmds.cmd_manifest_show, state, tier)


@plugins_app.command("list")
def plugins_list(ctx: typer.Context) -> None:
    state: CliState = ctx.obj
    _run(state, admin_cmds.cmd_plugins_list, state)


@app.command("doctor")
def doctor(
    ctx: typer.Context,
    validate_extractors: bool = typer.Option(False, "--validate-extractors"),
) -> None:
    state: CliState = ctx.obj
    _run(state, admin_cmds.cmd_doctor, state)


def main() -> None:
    """Console entry: `python -m apexfin` and the `apexfin` script both land here."""
    app()


if __name__ == "__main__":
    main()
