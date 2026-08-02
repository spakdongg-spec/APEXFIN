"""The source catalog: which series exist, who owns them, how much to trust them.

Lives in L1 because four layers need it and none of them may reach across to
another L3 package to get it. It reads `config/sources.yaml`, validates against
`contracts/sources.schema.json`, and hands out frozen `SeriesSpec` objects.

Credentials are never in this file's data. `credential_env` holds the *name* of
an environment variable; the schema's pattern (`^APEXFIN_[A-Z0-9_]+$`) plus
`assert_no_secrets` make a pasted key fail at load time rather than work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apexfin.core.config import load_yaml
from apexfin.core.enums import Frequency, Tier
from apexfin.core.errors import ConfigError
from apexfin.core.models import SeriesSpec
from apexfin.core.schema import load_schema, validate

DEFAULT_TIER = Tier.SUPPORT


@dataclass(frozen=True)
class SourceSpec:
    name: str
    domain: str
    collector: str
    frequency: Frequency
    enabled: bool
    reliability: float
    requires_credentials: bool
    credential_env: str | None
    min_request_interval_s: float
    series: tuple[SeriesSpec, ...]


@dataclass(frozen=True)
class SourceCatalog:
    sources: tuple[SourceSpec, ...]

    def enabled(self) -> tuple[SourceSpec, ...]:
        return tuple(s for s in self.sources if s.enabled)

    def by_name(self, name: str) -> SourceSpec:
        for source in self.sources:
            if source.name == name:
                return source
        known = ", ".join(s.name for s in self.sources) or "<none>"
        raise ConfigError(f"unknown source '{name}'; sources.yaml declares: {known}")

    def series(self, *, enabled_only: bool = True) -> tuple[SeriesSpec, ...]:
        pool = self.enabled() if enabled_only else self.sources
        return tuple(spec for source in pool for spec in source.series)

    def series_for(self, source_name: str, symbol: str) -> SeriesSpec | None:
        for spec in self.series(enabled_only=False):
            if spec.source_name == source_name and spec.symbol == symbol:
                return spec
        return None

    def reliability_map(self) -> dict[str, float]:
        return {s.name: s.reliability for s in self.sources}

    def tier_map(self) -> dict[tuple[str, str], Tier]:
        return {(s.source_name, s.symbol): s.tier for s in self.series(enabled_only=False)}


def load_catalog(path: Path, schema_path: Path | None = None) -> SourceCatalog:
    raw = load_yaml(path)
    if schema_path is not None and schema_path.exists():
        errors = validate(raw, load_schema(schema_path), origin=path.name)
        if errors:
            joined = "\n  ".join(errors)
            raise ConfigError(f"{path} fails sources.schema.json:\n  {joined}")
    entries = raw.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path}: 'sources' must be a non-empty list")
    return SourceCatalog(tuple(_source(entry, path) for entry in entries))


def _source(entry: Any, origin: Path) -> SourceSpec:
    if not isinstance(entry, dict):
        raise ConfigError(f"{origin}: every source entry must be a mapping")
    name = str(entry["name"])
    domain = str(entry["domain"])
    frequency = Frequency(str(entry["frequency"]).upper())
    symbols = entry.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise ConfigError(f"{origin}: source '{name}' declares no symbols")
    series = tuple(_series(symbol, name, domain, frequency, origin) for symbol in symbols)
    return SourceSpec(
        name=name,
        domain=domain,
        collector=str(entry["collector"]),
        frequency=frequency,
        enabled=bool(entry["enabled"]),
        reliability=float(entry["reliability"]),
        requires_credentials=bool(entry.get("requires_credentials", False)),
        credential_env=(
            None if entry.get("credential_env") is None else str(entry["credential_env"])
        ),
        min_request_interval_s=float(entry.get("min_request_interval_s", 0.0)),
        series=series,
    )


def _series(
    symbol: Any, source_name: str, domain: str, frequency: Frequency, origin: Path
) -> SeriesSpec:
    if not isinstance(symbol, dict) or "id" not in symbol:
        raise ConfigError(f"{origin}: source '{source_name}' has a symbol entry without 'id'")
    tier_raw = symbol.get("tier")
    return SeriesSpec(
        source_name=source_name,
        symbol=str(symbol["id"]),
        domain=domain,
        tier=DEFAULT_TIER if tier_raw is None else Tier(str(tier_raw)),
        frequency=frequency,
        unit=None if symbol.get("unit") is None else str(symbol["unit"]),
        label=None if symbol.get("label") is None else str(symbol["label"]),
    )
