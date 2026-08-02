"""Contract drift tests: checked-in fixtures must satisfy the checked-in schemas.

The dashboard was built against `tests/fixtures/sample_datapack.json`, and the
backend emits `DataPack` through pydantic models whose serialization schema is
`contracts/datapack.schema.json`. Validating the fixture against that schema
makes the fixture a test of the backend contract instead of a parallel truth
that can silently drift away from it (B-3).

The config files are validated for the same reason: `config/expectations.yaml`
and `config/sources.yaml` are the input contracts the pipeline is governed by,
and a hand-edited YAML that no longer satisfies its schema would fail only at
runtime, three steps away from the edit that broke it.
"""

from __future__ import annotations

import json
from pathlib import Path

from apexfin.core.config import load_yaml
from apexfin.core.schema import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
CONFIG = ROOT / "config"
TESTS_FIXTURES = ROOT / "tests" / "fixtures"


def _assert_valid(instance: object, schema_name: str, origin: str) -> None:
    errors = validate(instance, load_schema(CONTRACTS / schema_name), origin=origin)
    assert not errors, f"{origin} fails {schema_name}:\n  " + "\n  ".join(errors)


def test_sample_datapack_matches_datapack_schema() -> None:
    fixture = json.loads((TESTS_FIXTURES / "sample_datapack.json").read_text(encoding="utf-8"))
    _assert_valid(fixture, "datapack.schema.json", "sample_datapack.json")


def test_expectations_config_matches_expectations_schema() -> None:
    raw = load_yaml(CONFIG / "expectations.yaml")
    _assert_valid(raw, "expectations.schema.json", "config/expectations.yaml")


def test_sources_config_matches_sources_schema() -> None:
    raw = load_yaml(CONFIG / "sources.yaml")
    _assert_valid(raw, "sources.schema.json", "config/sources.yaml")
