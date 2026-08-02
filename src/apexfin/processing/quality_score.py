"""Per-point quality score (DATA_CONTRACT 三).

    score = source_reliability * staleness_factor * completeness_factor

    source_reliability  : per-source constant from sources.yaml
    staleness_factor    : max(0, 1 - lag_trading_days / max_lag_trading_days * 0.5)
    completeness_factor : 1.0 when every expected field is present,
                          0.8 when value_secondary is missing but expected

Thresholds arrive as plain mappings rather than by importing
`quality.expectations`: L3 packages are not allowed to know about each other,
so the composition layer (L4) is what joins governance config to processing.
That indirection is the whole reason `quality/` can be lifted out of this
repository wholesale.

The score never reaches 0 from staleness alone -- the 0.5 coefficient means a
series at exactly its threshold still scores half. A stale point is worth less
than a fresh one, but it is not worthless, and pretending otherwise would let
the score silently do the gate's job.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_RELIABILITY = 0.85
MISSING_SECONDARY_FACTOR = 0.8
STALENESS_COEFFICIENT = 0.5


@dataclass(frozen=True)
class ScoringPolicy:
    """Everything the score needs, resolved by the caller."""

    reliability: Mapping[str, float] = field(default_factory=dict)
    max_lag: Mapping[str, int] = field(default_factory=dict)
    expects_secondary: Mapping[str, bool] = field(default_factory=dict)
    default_reliability: float = DEFAULT_RELIABILITY
    default_max_lag: int = 1

    def reliability_of(self, source_name: str) -> float:
        return float(self.reliability.get(source_name, self.default_reliability))

    def max_lag_of(self, source_name: str) -> int:
        return int(self.max_lag.get(source_name, self.default_max_lag))

    def wants_secondary(self, source_name: str) -> bool:
        return bool(self.expects_secondary.get(source_name, False))


def staleness_factor(lag_trading_days: int, max_lag_trading_days: int) -> float:
    """Linear decay, floored at zero. `max_lag == 0` means same-day or nothing."""
    if lag_trading_days <= 0:
        return 1.0
    if max_lag_trading_days <= 0:
        return 0.0
    decayed = 1.0 - (lag_trading_days / max_lag_trading_days) * STALENESS_COEFFICIENT
    return max(0.0, decayed)


def completeness_factor(*, has_secondary: bool, expects_secondary: bool) -> float:
    if expects_secondary and not has_secondary:
        return MISSING_SECONDARY_FACTOR
    return 1.0


def compute(
    policy: ScoringPolicy,
    source_name: str,
    lag_trading_days: int,
    *,
    has_secondary: bool,
) -> float:
    score = (
        policy.reliability_of(source_name)
        * staleness_factor(lag_trading_days, policy.max_lag_of(source_name))
        * completeness_factor(
            has_secondary=has_secondary,
            expects_secondary=policy.wants_secondary(source_name),
        )
    )
    return round(min(1.0, max(0.0, score)), 4)
