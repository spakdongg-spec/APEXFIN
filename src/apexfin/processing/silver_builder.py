"""Incremental bronze to silver build.

Two properties this file is responsible for:

1. **Nothing is dropped quietly.** A bronze row either produces silver points
   or lands in `BuildOutcome.skipped` with a stated reason. The caller reports
   the reasons; an empty `points` tuple with an empty `skipped` tuple is only
   possible when there was genuinely no input.
2. **Forward-fill is never implicit.** This builder emits exactly the points
   its extractors produced. Any `is_filled=True` row must come from a separate,
   visible step (DATA_CONTRACT 三).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from apexfin.core.models import BronzeRecord, SilverPoint
from apexfin.core.trading_calendar import TradingCalendar
from apexfin.processing import quality_score
from apexfin.processing.extractors import ExtractionSkipped, get_extractor
from apexfin.processing.quality_score import ScoringPolicy


@dataclass(frozen=True)
class SkippedRecord:
    bronze_id: int
    source_name: str
    symbol: str
    reason: str


@dataclass(frozen=True)
class BuildOutcome:
    points: tuple[SilverPoint, ...]
    skipped: tuple[SkippedRecord, ...]

    @property
    def metrics(self) -> dict[str, float]:
        return {"points": float(len(self.points)), "skipped": float(len(self.skipped))}


def build(
    records: Sequence[BronzeRecord],
    *,
    calendar: TradingCalendar,
    as_of: date,
    policy: ScoringPolicy,
) -> BuildOutcome:
    points: list[SilverPoint] = []
    skipped: list[SkippedRecord] = []

    for record in records:
        extractor = get_extractor(record.source_name)
        try:
            produced = extractor.extract(record)
        except ExtractionSkipped as reason:
            skipped.append(SkippedRecord(record.id, record.source_name, record.symbol, str(reason)))
            continue
        if not produced:
            skipped.append(
                SkippedRecord(
                    record.id,
                    record.source_name,
                    record.symbol,
                    f"{type(extractor).__name__} returned no points and gave no reason",
                )
            )
            continue
        lag = calendar.trading_days_between(record.event_date, as_of)
        points.extend(_scored(point, lag, policy) for point in produced)

    return BuildOutcome(tuple(points), tuple(skipped))


def _scored(point: SilverPoint, lag: int, policy: ScoringPolicy) -> SilverPoint:
    score = quality_score.compute(
        policy,
        point.source_name,
        lag,
        has_secondary=point.value_secondary is not None,
    )
    return point.model_copy(update={"quality_score": score})
