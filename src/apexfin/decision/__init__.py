"""Strategies and signal aggregation (L3).

A strategy sees a `MarketView` and nothing else -- no connection, no config,
no clock. That boundary is what makes a strategy replaceable and testable, and
what stops one from quietly writing to the database.
"""

from apexfin.decision.aggregator import EqualWeightAggregator
from apexfin.decision.base import BaseStrategy, MarketView, SignalAggregator
from apexfin.decision.views import MarketViewImpl

__all__ = [
    "BaseStrategy",
    "EqualWeightAggregator",
    "MarketView",
    "MarketViewImpl",
    "SignalAggregator",
]
