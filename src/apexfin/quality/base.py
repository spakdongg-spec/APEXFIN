"""`QualityCheck` and the read-only context it runs in (INTERFACES 四).

A check never raises for a data problem. Data problems are findings; an
exception means the check itself is broken. The distinction matters because
the runner treats them differently: findings feed the gate, exceptions fail
the step.

The context carries read ports only. A check cannot write to the database even
by accident, so "the freshness check quietly backfilled a row" is not a bug
that can exist here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from apexfin.core.clock import Clock
from apexfin.core.contracts import BronzeReadPort, SilverReadPort
from apexfin.core.enums import Severity
from apexfin.core.models import QualityFinding, SeriesSpec
from apexfin.core.trading_calendar import TradingCalendar
from apexfin.quality.expectations import ExpectationTable, SourceExpectation


class QualityContext(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: str
    clock: Clock
    calendar: TradingCalendar
    expectations: ExpectationTable
    series: tuple[SeriesSpec, ...]
    silver: SilverReadPort
    bronze: BronzeReadPort

    def expectation_for(self, spec: SeriesSpec) -> SourceExpectation:
        return self.expectations.for_series(spec.source_name, spec.symbol)


class QualityCheck(ABC):
    check_id: ClassVar[str]
    default_severity: ClassVar[Severity]
    title: ClassVar[str] = ""

    @abstractmethod
    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        """Return findings. An empty list means the check passed."""

    def finding(
        self,
        spec: SeriesSpec,
        message: str,
        *,
        observed: str,
        expected: str,
        severity: Severity | None = None,
    ) -> QualityFinding:
        return QualityFinding(
            check_id=self.check_id,
            severity=severity or self.default_severity,
            source_name=spec.source_name,
            symbol=spec.symbol,
            message=message,
            observed=observed,
            expected=expected,
            tier=spec.tier,
        )


ALL_CHECK_IDS = (
    "freshness",
    "completeness",
    "duplicates",
    "consistency",
    "continuity",
    "range",
)
