"""Manifest loading and the four-way consistency assertion (ARCHITECTURE 5.2).

The manifest is the governance contract for the daily pipeline: every step
must justify why it runs. Validation is bidirectional and fails loud -- a
broken manifest is exactly what lets a silent dependency drift go unnoticed,
so it exits 6 rather than guessing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apexfin.core.config import find_project_root, load_yaml
from apexfin.core.errors import ManifestError
from apexfin.core.schema import load_schema, validate
from apexfin.pipeline.registry import all_steps


def _contracts_dir() -> Path:
    return find_project_root() / "contracts"


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the pipeline manifest and validate it against its JSON schema."""
    data = load_yaml(path)
    schema_path = _contracts_dir() / "manifest.schema.json"
    if schema_path.exists():
        errors = validate(data, load_schema(schema_path), origin=path.name)
        if errors:
            raise ManifestError(
                f"{path.name} fails manifest.schema.json:\n  " + "\n  ".join(errors)
            )
    return data


def validate_manifest(data: dict[str, Any]) -> list[str]:
    """Return every consistency violation found in the manifest.

    The four assertions:
      1. schema valid (JSON Schema, required name/tier/keep_daily/why>=12)
      2. @step registration <-> manifest declaration, bidirectional
      3. a keep_daily=true step must not depend on a keep_daily=false step
      4. depends_on is acyclic
    """
    violations: list[str] = []
    schema_path = _contracts_dir() / "manifest.schema.json"
    if schema_path.exists():
        violations.extend(validate(data, load_schema(schema_path), origin="manifest"))

    steps = {s["name"]: s for s in data.get("steps", [])}
    registered = all_steps()

    for name in steps:
        if name not in registered:
            violations.append(f"manifest step '{name}' has no @step registration")
    for name in registered:
        if name not in steps:
            violations.append(f"@step '{name}' is not declared in the manifest")

    keep_daily = {n: bool(s.get("keep_daily", True)) for n, s in steps.items()}
    for name, spec in steps.items():
        for dep in spec.get("depends_on", []):
            if keep_daily.get(dep) is False and keep_daily.get(name) is True:
                violations.append(
                    f"keep_daily=true step '{name}' depends on keep_daily=false step '{dep}'"
                )

    _check_acyclic(steps, violations)
    return violations


def _check_acyclic(steps: dict[str, Any], violations: list[str]) -> None:
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(steps, white)

    def visit(node: str, stack: list[str]) -> None:
        color[node] = gray
        for dep in steps.get(node, {}).get("depends_on", []):
            if dep not in steps:
                continue
            if color[dep] == gray:
                violations.append("dependency cycle: " + " -> ".join([*stack, dep]))
                return
            if color[dep] == white:
                visit(dep, [*stack, node])
        color[node] = black

    for node in steps:
        if color[node] == white:
            visit(node, [])


def assert_manifest_ok(data: dict[str, Any]) -> None:
    """Raise ManifestError (exit 6) if the manifest has any violation."""
    violations = validate_manifest(data)
    if violations:
        raise ManifestError("manifest invalid:\n  " + "\n  ".join(violations))
