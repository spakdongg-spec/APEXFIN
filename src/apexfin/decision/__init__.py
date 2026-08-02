"""Analyst roles and the bull/bear debate framework (L3).

A role sees a `MarketView` and nothing else -- no connection, no config, no
clock. That boundary is what makes a role replaceable and testable, and what
stops one from quietly writing to the database. Decisions are produced by the
debate engine (`debate.py`) from the per-role verdicts; `orchestrate.py` wires
both into the pipeline.
"""

from apexfin.decision.base import BaseStrategy, MarketView, SignalAggregator
from apexfin.decision.debate import DebateResult, run_debate
from apexfin.decision.orchestrate import decide_all
from apexfin.decision.views import MarketViewImpl

__all__ = [
    "BaseStrategy",
    "DebateResult",
    "MarketView",
    "MarketViewImpl",
    "SignalAggregator",
    "decide_all",
    "run_debate",
]
