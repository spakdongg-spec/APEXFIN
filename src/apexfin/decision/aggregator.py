"""Equal-weight signal aggregation.

Equal weight is a choice, not a default. Any other weighting this project could
ship would encode a claim about which strategy is better, and the skeleton has
no evidence for such a claim. Weighting by backtest performance on the same
data the weights are fitted to is precisely the mistake this repository exists
to demonstrate the avoidance of.

Two outcomes are carefully kept apart:

* `flat` -- the strategies agree there is no move worth acting on.
* `no_call` -- the strategies contradict each other and cancel out.

Collapsing the second into the first would let a genuine disagreement be
reported as a considered view.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from math import fsum

from apexfin.core.models import Decision, Signal

#: Net score below which no directional claim is made.
STANCE_EPSILON = 0.05

_SIGN: dict[str, float] = {"long": 1.0, "short": -1.0, "flat": 0.0}

_STRATEGY_NAME = "equal_weight"


@dataclass(frozen=True)
class EqualWeightAggregator:
    """Average the signed strength of every signal for a symbol, equally.

    `degraded` is stamped onto every decision it produces: when the quality
    gate degraded the run, the opinions born from that run are degraded too,
    and the reader must be told without having to join back to the run row.
    """

    run_id: str
    degraded: bool = False
    strategy: str = field(default=_STRATEGY_NAME)

    def aggregate(self, signals: Sequence[Signal], as_of: date) -> list[Decision]:
        by_symbol: dict[str, list[Signal]] = defaultdict(list)
        for signal in signals:
            by_symbol[signal.symbol].append(signal)
        return [self._decide(symbol, group, as_of) for symbol, group in sorted(by_symbol.items())]

    def _decide(self, symbol: str, signals: list[Signal], as_of: date) -> Decision:
        scores = [_SIGN[s.direction] * abs(s.strength) for s in signals]
        net = fsum(scores) / len(scores)
        directions = {s.direction for s in signals}
        conflicted = "long" in directions and "short" in directions

        stance, confidence = _resolve(net, conflicted=conflicted)
        contributors = tuple(sorted({s.strategy for s in signals}))
        return Decision(
            run_id=self.run_id,
            as_of=as_of,
            symbol=symbol,
            stance=stance,  # type: ignore[arg-type]
            confidence=round(confidence, 4),
            strategy=self.strategy,
            rationale=_rationale(stance, net, signals, conflicted=conflicted),
            inputs={
                "net_score": round(net, 6),
                "signal_count": float(len(signals)),
                "long_count": float(sum(1 for s in signals if s.direction == "long")),
                "short_count": float(sum(1 for s in signals if s.direction == "short")),
            },
            contributing_signals=contributors,
            degraded=self.degraded,
        )


def _resolve(net: float, *, conflicted: bool) -> tuple[str, float]:
    """Map a net score to a stance and a confidence in [0, 1]."""
    if abs(net) >= STANCE_EPSILON:
        return ("long" if net > 0 else "short"), min(1.0, abs(net))
    if conflicted:
        # Signals exist and point opposite ways. There is no view here.
        return "no_call", 0.0
    # Agreement that nothing is happening. Confidence is highest at net == 0
    # and falls linearly to zero at the directional threshold.
    return "flat", max(0.0, 1.0 - abs(net) / STANCE_EPSILON)


def _rationale(stance: str, net: float, signals: list[Signal], *, conflicted: bool) -> str:
    names = "、".join(sorted({s.strategy for s in signals}))
    head = f"{len(signals)} 个信号（{names}）等权合成，净分 {net:+.4f}"

    if stance == "no_call":
        longs = [s.strategy for s in signals if s.direction == "long"]
        shorts = [s.strategy for s in signals if s.direction == "short"]
        return (
            f"{head}；看多（{'、'.join(sorted(set(longs)))}）与看空"
            f"（{'、'.join(sorted(set(shorts)))}）相互抵消，不形成观点。"
        )
    if stance == "flat":
        return f"{head}，低于 {STANCE_EPSILON:.2f} 方向阈值，判定横盘。"

    word = "看多" if stance == "long" else "看空"
    return f"{head}，超过 {STANCE_EPSILON:.2f} 方向阈值，判定{word}。仅作演示，不构成投资建议。"
