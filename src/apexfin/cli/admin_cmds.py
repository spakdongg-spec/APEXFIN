"""Administrative commands: init / manifest / plugins / doctor (CLI_CONTRACT 四)."""

from __future__ import annotations

import importlib.metadata
import os
import sys
from pathlib import Path
from typing import Any

from apexfin.cli.state import CliState
from apexfin.core.clock import SystemClock
from apexfin.core.config import load_yaml
from apexfin.core.errors import ApexfinError, ManifestError
from apexfin.core.registry import builtin_entries, discover_plugins
from apexfin.core.schema import load_schema, validate
from apexfin.core.trading_calendar import MAX_YEAR, MIN_YEAR
from apexfin.pipeline.manifest import load_manifest, validate_manifest
from apexfin.storage.engine import connect
from apexfin.storage.migrator import current_version, migrate

#: Env vars doctor reports on. Presence only -- the value is never printed.
_KNOWN_SECRET_ENV = ("APEXFIN_FRED_API_KEY",)

_DEPENDENCIES = ("typer", "pydantic", "pydantic_settings", "pyyaml", "jinja2", "structlog")


def _db(state: CliState) -> Path:
    return state.db if state.db is not None else state.root / "data" / "apexfin.db"


def _config_dir(state: CliState) -> Path:
    return state.config_dir if state.config_dir is not None else state.root / "config"


def cmd_init(state: Any) -> int:
    conn = connect(_db(state))
    applied = migrate(conn, SystemClock().now())
    version = current_version(conn)
    conn.close()
    if state.json_output:
        print(f'{{"ok": true, "applied": {applied}, "schema_version": {version}}}')
    else:
        print(f"init: applied {len(applied)} migration(s); schema version {version}")
    return 0


def cmd_manifest_validate(state: Any, manifest_path: Path | None) -> int:
    path = manifest_path or state.root / "config" / "pipeline_manifest.yaml"
    data = load_manifest(path)
    violations = validate_manifest(data)
    if violations:
        raise ManifestError(f"{path.name} invalid:\n  " + "\n  ".join(violations))
    steps = [s["name"] for s in data.get("steps", [])]
    if state.json_output:
        print(f'{{"ok": true, "steps": {steps!r}}}')
    else:
        print(f"[PASS] {path.name} consistent ({len(steps)} steps)")
    return 0


def cmd_manifest_show(state: Any, tier: str | None) -> int:
    path = state.root / "config" / "pipeline_manifest.yaml"
    data = load_manifest(path)
    for spec in data.get("steps", []):
        if tier is not None and spec.get("tier") != tier:
            continue
        deps = ", ".join(spec.get("depends_on", [])) or "-"
        if state.json_output:
            print(
                f'{{"name": "{spec["name"]}", "tier": "{spec.get("tier")}", '
                f'"depends_on": "{deps}", "why": "{spec.get("why", "")}"}}'
            )
        else:
            print(f"{spec['name']:<18} {spec.get('tier'):<15} -> {deps}")
    return 0


def cmd_plugins_list(state: Any) -> int:
    rows = [*builtin_entries(), *discover_plugins().entries]
    for entry in rows:
        group = entry.group.rsplit(".", 1)[-1]
        reason = f"  ({entry.reason})" if entry.reason else ""
        if state.json_output:
            print(
                f'{{"group": "{group}", "name": "{entry.name}", "status": '
                f'"{entry.status}", "origin": "{entry.origin}"}}'
            )
        else:
            print(f"[{entry.status}] {group:>10} {entry.name:<20} {entry.origin}{reason}")
    return 0


def cmd_doctor(state: Any) -> int:
    checks: list[tuple[str, bool, str]] = []

    version_detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("python", sys.version_info >= (3, 11), version_detail))
    for dep in _DEPENDENCIES:
        try:
            version = importlib.metadata.version(dep)
        except importlib.metadata.PackageNotFoundError:
            version = "missing"
        checks.append((dep, version != "missing", version))

    db_ok = True
    db_detail = ""
    try:
        conn = connect(_db(state))
        migrate(conn, SystemClock().now())
        db_detail = f"writable, schema v{current_version(conn)}"
        conn.close()
    except ApexfinError as exc:
        db_ok = False
        db_detail = str(exc)
    checks.append(("database", db_ok, db_detail))

    for name in ("expectations.yaml", "sources.yaml"):
        ok = True
        detail = "schema ok"
        try:
            raw = load_yaml(_config_dir(state) / name)
            schema_name = f"{name.removesuffix('.yaml')}.schema.json"
            errors = validate(raw, load_schema(state.root / "contracts" / schema_name), origin=name)
            if errors:
                ok = False
                detail = "; ".join(errors)
        except ApexfinError as exc:
            ok = False
            detail = str(exc)
        checks.append((f"config:{name}", ok, detail))

    checks.append(("calendar", MIN_YEAR <= 2026 <= MAX_YEAR, f"NYSE {MIN_YEAR}..{MAX_YEAR}"))

    plugin_report = discover_plugins()
    checks.append(
        ("plugins", not plugin_report.failures, f"{len(plugin_report.entries)} discovered")
    )

    for var in _KNOWN_SECRET_ENV:
        # Informational by design: a missing optional credential is normal for
        # the offline demo and must not fail the self-check (CLI_CONTRACT 四).
        checks.append((var, True, "present" if os.environ.get(var) else "absent"))

    sprite_ok = True
    sprite_detail = "icons ok"
    try:
        icons_raw = load_yaml(state.root / "config" / "icons.yaml")
        names = [str(i) for i in icons_raw.get("icons", [])]
        sprite = (state.root / "static" / "sprite.svg").read_text(encoding="utf-8")
        missing = [n for n in names if f'id="icon-{n}"' not in sprite]
        if missing:
            sprite_ok = False
            sprite_detail = f"missing in sprite.svg: {', '.join(missing)}"
    except ApexfinError as exc:
        sprite_ok = False
        sprite_detail = str(exc)
    checks.append(("sprite-icons", sprite_ok, sprite_detail))

    failed = 0
    for name, ok, detail in checks:
        if state.json_output:
            print(f'{{"check": "{name}", "ok": {str(ok).lower()}, "detail": "{detail}"}}')
        else:
            print(f"[{'PASS' if ok else 'FAIL'}] {name:<18} {detail}")
        if not ok:
            failed += 1
    return 1 if failed else 0
