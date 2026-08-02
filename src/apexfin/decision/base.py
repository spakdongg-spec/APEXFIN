"""Decision contracts (INTERFACES 七).

A strategy's only input is a `MarketView` -- a read-only projection that never
hands it a database connection. That boundary is what keeps a strategy
replaceable (PRD AC-5), testable, and unable to write anywhere it shouldn't.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from typing import ClassVar, Protocol, runtime_checkable

from apexfin.core.models import Decision, Signal, SilverPoint


@runtime_checkable
class MarketView(Protocol):
    """Read-only projection handed to strategies."""

    as_of: date

    def series(self, symbol: str, lookback: int = 250) -> tuple[SilverPoint, ...]: ...
    def symbols(self) -> tuple[str, ...]: ...
    def is_healthy(self, symbol: str) -> bool: ...


class BaseStrategy(ABC):
    """Produce per-symbol signals from a MarketView."""

    name: ClassVar[str]

    @abstractmethod
    def generate(self, view: MarketView) -> list[Signal]:
        """Return signals. MUST return [] rather than guess when the symbol
        is not healthy -- a fabricated signal is worse than no signal."""


@runtime_checkable
class SignalAggregator(Protocol):
    """Turn signals into decisions."""

    def aggregate(self, signals: Sequence[Signal], as_of: date) -> list[Decision]: ...
