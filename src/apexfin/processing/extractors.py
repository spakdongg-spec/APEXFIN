"""Extractor registry, dispatched by `source_name` (INTERFACES 三).

A bronze row whose source has no registered extractor raises
`ExtractorNotFound`. It is not skipped: skipping leaves rows that never become
silver and nothing downstream would ever say so, which is precisely the silent
rot this project exists to make impossible.

Returning an empty list *is* legal -- some payloads carry no usable number --
but every empty return records a reason, so "extracted nothing" and "found
nothing worth extracting" stay distinguishable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from apexfin.core.errors import ExtractorNotFound
from apexfin.core.models import BronzeRecord, SilverPoint

_EXTRACTORS: dict[str, type[BaseExtractor]] = {}

# Placeholder score. `silver_builder` overwrites it with the real product of
# reliability x staleness x completeness; extractors do not know the clock.
_UNSCORED = 1.0


class ExtractionSkipped(Exception):
    """Raised internally by an extractor to report a reasoned empty result."""


class BaseExtractor(ABC):
    """Turns one bronze payload into zero or more silver points."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    @abstractmethod
    def extract(self, record: BronzeRecord) -> list[SilverPoint]: ...

    def _point(
        self,
        record: BronzeRecord,
        value: float,
        secondary: float | None,
        unit: str | None,
    ) -> SilverPoint:
        return SilverPoint(
            source_name=record.source_name,
            domain=record.domain,
            symbol=record.symbol,
            event_time=record.event_time,
            event_date=record.event_date,
            value=value,
            value_secondary=secondary,
            unit=unit,
            quality_score=_UNSCORED,
            is_filled=False,
            payload_json=None,
            bronze_id=record.id,
        )


def register_extractor(*source_names: str) -> Callable[[type[BaseExtractor]], type[BaseExtractor]]:
    def decorator(cls: type[BaseExtractor]) -> type[BaseExtractor]:
        for name in source_names:
            _EXTRACTORS[name] = cls
        return cls

    return decorator


def get_extractor(source_name: str) -> BaseExtractor:
    cls = _EXTRACTORS.get(source_name)
    if cls is None:
        known = ", ".join(sorted(_EXTRACTORS)) or "<none registered>"
        raise ExtractorNotFound(
            f"no extractor registered for source '{source_name}'. "
            f"Registered: {known}. Register one with @register_extractor "
            f"('{source_name}') or the bronze rows for this source can never "
            "become silver points."
        )
    return cls(source_name)


def registered_sources() -> tuple[str, ...]:
    return tuple(sorted(_EXTRACTORS))


def _number(payload: dict[str, Any], key: str) -> float | None:
    raw = payload.get(key)
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)
    try:
        return float(str(raw))
    except ValueError:
        return None


@register_extractor("yahoo", "fixture_equity", "fixture_volatility")
class OhlcvExtractor(BaseExtractor):
    """Close price as the value, volume as the secondary value."""

    def extract(self, record: BronzeRecord) -> list[SilverPoint]:
        close = _number(record.payload, "close")
        if close is None:
            raise ExtractionSkipped(
                f"payload has no numeric 'close' key (keys: "
                f"{', '.join(sorted(record.payload)) or 'none'})"
            )
        unit = record.payload.get("unit")
        point = self._point(
            record,
            value=close,
            secondary=_number(record.payload, "volume"),
            unit=str(unit) if unit is not None else "usd",
        )
        ohlc = self._ohlc(record)
        return [point if ohlc is None else point.model_copy(update={"payload_json": ohlc})]

    @staticmethod
    def _ohlc(record: BronzeRecord) -> dict[str, float] | None:
        """Carry the full bar into silver when the source actually supplies one.

        `value` stays the close, so every consumer that only wants a number is
        unaffected. Without this the render layer could only ever draw a line:
        it reads silver, and a close-only silver row cannot be reconstructed
        into a candle. Partial bars are dropped whole rather than back-filled
        from the close, which would draw four identical prices and look like a
        real flat session.
        """
        bar = {key: _number(record.payload, key) for key in ("open", "high", "low", "close")}
        if any(v is None for v in bar.values()):
            return None
        return {key: float(v) for key, v in bar.items() if v is not None}


@register_extractor("fred", "fixture_macro")
class ScalarExtractor(BaseExtractor):
    """One observation, one number. Used by macro and rates series."""

    def extract(self, record: BronzeRecord) -> list[SilverPoint]:
        value = _number(record.payload, "value")
        if value is None:
            raise ExtractionSkipped(
                "payload has no numeric 'value' key; upstream reports missing "
                "observations as '.', which is data absence, not a zero"
            )
        unit = record.payload.get("unit")
        return [
            self._point(
                record,
                value=value,
                secondary=None,
                unit=str(unit) if unit is not None else "percent",
            )
        ]
