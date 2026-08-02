"""Offline fixture collector -- the default demo path.

Committed sample data, zero network, zero credentials, deterministic output.
Two packs live side by side: `fresh` (everything inside its SLA) and `stale`
(one risk-essential series left behind on purpose). Staleness is produced by
switching packs and freezing the clock, never by editing the database -- both
of those are ordinary production capabilities, so the demo exercises real code
paths rather than a branch that exists only for the demo.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apexfin.core.clock import parse_utc
from apexfin.core.enums import Frequency
from apexfin.core.errors import CollectorError, ConfigError
from apexfin.core.models import FetchWindow, RawRecord, SourceCapabilities
from apexfin.core.registry import register_source
from apexfin.sources.base import BaseCollector

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PACKS = ("fresh", "stale")


@dataclass(frozen=True)
class FixturePackMeta:
    """Pack metadata. `as_of` drives the FrozenClock so demos are reproducible."""

    pack: str
    as_of: datetime
    description: str


def pack_dir(pack: str, root: Path = FIXTURES_DIR) -> Path:
    if pack not in PACKS:
        raise ConfigError(f"unknown fixture pack '{pack}'; expected one of {', '.join(PACKS)}")
    directory = root / pack
    if not directory.is_dir():
        raise ConfigError(f"fixture pack directory missing: {directory}")
    return directory


def load_pack_meta(pack: str, root: Path = FIXTURES_DIR) -> FixturePackMeta:
    meta_path = pack_dir(pack, root) / "_meta.json"
    if not meta_path.exists():
        raise ConfigError(f"fixture pack '{pack}' has no _meta.json at {meta_path}")
    raw: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    return FixturePackMeta(
        pack=str(raw.get("pack", pack)),
        as_of=parse_utc(str(raw["as_of"])),
        description=str(raw.get("description", "")),
    )


def pack_source_files(pack: str, root: Path = FIXTURES_DIR) -> tuple[Path, ...]:
    return tuple(sorted(p for p in pack_dir(pack, root).glob("*.json") if p.name != "_meta.json"))


@register_source("fixture")
class FixtureCollector(BaseCollector):
    """Replays one committed JSON file as if it were an upstream response."""

    def __init__(self, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._path = path
        self._doc = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            raise ConfigError(f"fixture file not found: {self._path}")
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ConfigError(f"{self._path}: expected a JSON object")
        for key in ("source_name", "domain", "records"):
            if key not in raw:
                raise ConfigError(f"{self._path}: missing required key '{key}'")
        return raw

    @property
    def tier(self) -> str:
        return str(self._doc.get("tier", "support"))

    @property
    def unit(self) -> str | None:
        unit = self._doc.get("unit")
        return None if unit is None else str(unit)

    def capabilities(self) -> SourceCapabilities:
        symbols = tuple(dict.fromkeys(str(r["symbol"]) for r in self._doc["records"]))
        return SourceCapabilities(
            source_name=str(self._doc["source_name"]),
            domain=str(self._doc["domain"]),
            symbols=symbols,
            frequency=Frequency(str(self._doc.get("frequency", "DAILY"))),
            requires_credentials=False,
            supports_full_refresh=True,
            min_request_interval_s=0.0,
        )

    def _fetch_raw(self, window: FetchWindow) -> Iterable[RawRecord]:
        self.before_request()
        source_name = str(self._doc["source_name"])
        domain = str(self._doc["domain"])
        out: list[RawRecord] = []
        for index, row in enumerate(self._doc["records"]):
            try:
                event_time = parse_utc(str(row["event_time"]))
            except (KeyError, ValueError) as exc:
                raise CollectorError(f"{self._path}: record {index} has a bad event_time") from exc
            if not window.full_refresh and not (window.start <= event_time.date() <= window.end):
                continue
            payload = {k: v for k, v in row.items() if k not in ("symbol", "event_time")}
            out.append(
                RawRecord(
                    source_name=source_name,
                    domain=domain,
                    symbol=str(row["symbol"]),
                    event_time=event_time,
                    payload=payload,
                    source_url=f"fixture://{self._path.name}",
                )
            )
        return out


def load_pack_collectors(pack: str, root: Path = FIXTURES_DIR) -> tuple[FixtureCollector, ...]:
    files = pack_source_files(pack, root)
    if not files:
        raise ConfigError(f"fixture pack '{pack}' contains no source files")
    return tuple(FixtureCollector(path) for path in files)
