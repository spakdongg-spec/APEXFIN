"""The concrete MarketView the strategies receive.

Built from the silver repository and the source catalog. It resolves a bare
symbol to its (source_name, symbol) pair so strategies never see storage
details, and it carries the set of healthy symbols computed upstream by the
quality gate so a strategy can refuse to guess on a stale series without
re-implementing freshness math.
"""

from __future__ import annotations

from datetime import date

from apexfin.core.catalog import SourceCatalog
from apexfin.core.models import SeriesSpec, SilverPoint
from apexfin.storage.silver_repo import SilverRepository


class MarketViewImpl:
    """Read-only projection over silver points, keyed by symbol."""

    def __init__(
        self,
        silver: SilverRepository,
        catalog: SourceCatalog,
        as_of: date,
        healthy_symbols: frozenset[str] = frozenset(),
    ) -> None:
        self._silver = silver
        self._as_of = as_of
        self._healthy = healthy_symbols
        self._by_symbol: dict[str, SeriesSpec] = {
            spec.symbol: spec for spec in catalog.series(enabled_only=True)
        }

    @property
    def as_of(self) -> date:
        return self._as_of

    def series(self, symbol: str, lookback: int = 250) -> tuple[SilverPoint, ...]:
        spec = self._by_symbol.get(symbol)
        if spec is None:
            return ()
        return self._silver.series(spec.source_name, spec.symbol, lookback)

    def symbols(self) -> tuple[str, ...]:
        return tuple(self._by_symbol)

    def is_healthy(self, symbol: str) -> bool:
        return symbol in self._healthy

    def __repr__(self) -> str:
        return f"MarketViewImpl(symbols={len(self._by_symbol)}, as_of={self._as_of.isoformat()})"
