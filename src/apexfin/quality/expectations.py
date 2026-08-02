"""Expectation table loaded from `config/expectations.yaml`.

Migrated from APEXDATA's `SOURCE_EXPECTATIONS` constant. Every threshold lives
here rather than in code, because thresholds carry the previous owner's
judgement about the previous owner's data and a fork must be able to change
them without touching Python (ALPHA_BOUNDARY, risk R6).

Freshness is expressed in trading days and only in trading days (O-07). There
is no hour-based key in this file's schema, and adding one would put two
incompatible units on the same dashboard.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from apexfin.core.config import load_yaml
from apexfin.core.enums import Frequency
from apexfin.core.errors import ConfigError
from apexfin.core.schema import load_schema, validate

_NUMERIC_KEYS = (
    "max_lag_trading_days",
    "completeness_window_days",
    "max_missing_trading_days",
    "max_gap_trading_days",
)


@dataclass(frozen=True)
class SourceExpectation:
    source_name: str
    frequency: Frequency = Frequency.DAILY
    max_lag_trading_days: int = 2
    completeness_window_days: int = 20
    max_missing_trading_days: int = 0
    max_gap_trading_days: int = 1
    expects_secondary: bool = False
    value_min: float | None = None
    value_max: float | None = None


@dataclass(frozen=True)
class ExpectationTable:
    default: SourceExpectation
    by_source: dict[str, SourceExpectation]
    by_series: dict[tuple[str, str], SourceExpectation]

    def for_source(self, source_name: str) -> SourceExpectation:
        found = self.by_source.get(source_name)
        if found is not None:
            return found
        return replace(self.default, source_name=source_name)

    def for_series(self, source_name: str, symbol: str) -> SourceExpectation:
        found = self.by_series.get((source_name, symbol))
        if found is not None:
            return found
        return self.for_source(source_name)

    def max_lag_map(self) -> dict[str, int]:
        return {name: exp.max_lag_trading_days for name, exp in self.by_source.items()}

    def expects_secondary_map(self) -> dict[str, bool]:
        return {name: exp.expects_secondary for name, exp in self.by_source.items()}

    def uncovered(self, series: Iterable[tuple[str, str]]) -> tuple[str, ...]:
        """Series whose source has no explicit entry in the expectations file."""
        gaps = {f"{source}/{symbol}" for source, symbol in series if source not in self.by_source}
        return tuple(sorted(gaps))

    def assert_covers(self, series: Iterable[tuple[str, str]], origin: Path) -> None:
        """Fail loudly when a configured series has no declared expectation (O-09).

        The defaults block exists to keep the file short, not to let an
        undeclared source inherit thresholds nobody chose for it. A
        risk-essential series silently picking up `max_lag_trading_days: 2`
        because someone forgot to add four lines of YAML is the exact failure
        this project is written to prevent -- and it would fail *quietly*,
        which is worse than failing at all.
        """
        gaps = self.uncovered(series)
        if not gaps:
            return
        known = ", ".join(sorted(self.by_source)) or "<none>"
        raise ConfigError(
            f"{origin}: no expectation entry for {', '.join(gaps)}. "
            f"Declared sources: {known}. Add each missing source under `sources:` "
            "with at least `max_lag_trading_days`; inheriting the defaults "
            "silently is not allowed for a configured series (O-09)."
        )


def load_expectations(path: Path, schema_path: Path | None = None) -> ExpectationTable:
    raw = load_yaml(path)
    if schema_path is not None and schema_path.exists():
        errors = validate(raw, load_schema(schema_path), origin=path.name)
        if errors:
            joined = "\n  ".join(errors)
            raise ConfigError(f"{path} fails expectations.schema.json:\n  {joined}")
    defaults_raw = raw.get("defaults")
    if not isinstance(defaults_raw, dict):
        raise ConfigError(
            f"{path}: top-level 'defaults' block is required (O-09). "
            "Add it with all four numeric keys: " + ", ".join(_NUMERIC_KEYS)
        )
    missing = [key for key in _NUMERIC_KEYS if key not in defaults_raw]
    if missing:
        raise ConfigError(
            f"{path}: 'defaults' is missing required key(s): {', '.join(missing)}. "
            "Every threshold must be explicit; the dataclass defaults are a type "
            "fallback for direct construction, never for the load path (O-09)."
        )
    base = _merge(SourceExpectation(source_name="<default>"), defaults_raw, path)

    by_source: dict[str, SourceExpectation] = {}
    by_series: dict[tuple[str, str], SourceExpectation] = {}

    sources = raw.get("sources") or {}
    if not isinstance(sources, dict):
        raise ConfigError(f"{path}: 'sources' must be a mapping of source name to expectations")

    for name, entry in sources.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"{path}: expectations for '{name}' must be a mapping")
        symbols = entry.get("symbols") or {}
        source_level = _merge(
            replace(base, source_name=str(name)),
            {k: v for k, v in entry.items() if k != "symbols"},
            path,
        )
        by_source[str(name)] = source_level
        if not isinstance(symbols, dict):
            raise ConfigError(f"{path}: '{name}.symbols' must be a mapping")
        for symbol, override in symbols.items():
            if not isinstance(override, dict):
                raise ConfigError(f"{path}: '{name}.symbols.{symbol}' must be a mapping")
            by_series[(str(name), str(symbol))] = _merge(source_level, override, path)

    return ExpectationTable(default=base, by_source=by_source, by_series=by_series)


def _merge(base: SourceExpectation, patch: dict[str, Any], origin: Path) -> SourceExpectation:
    updates: dict[str, Any] = {}
    for key, value in patch.items():
        if key == "frequency":
            updates[key] = Frequency(str(value).upper())
        elif key in _NUMERIC_KEYS:
            updates[key] = _non_negative_int(key, value, origin)
        elif key == "expects_secondary":
            updates[key] = bool(value)
        elif key in ("value_min", "value_max"):
            updates[key] = None if value is None else float(value)
        else:
            raise ConfigError(
                f"{origin}: unknown expectation key '{key}'. "
                "Hour-based keys are rejected on purpose (ARCHITECTURE 5.3.1)."
            )
    return replace(base, **updates)


def _non_negative_int(key: str, value: Any, origin: Path) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{origin}: '{key}' must be an integer, got {value!r}")
    if value < 0:
        raise ConfigError(f"{origin}: '{key}' must be >= 0, got {value}")
    return value
