"""Toy momentum -- deliberately naive, deliberately honest.

This is the reference implementation the project is *about* copying the shape
of, not the alpha. It compares the close N trading days ago to the latest
close and emits a directional signal. No optimisation, no parameters the user
can tune into a backtest artefact.

The file header states plainly that this is demonstration-only and not
investment advice -- that disclaimer is a project requirement, not boilerplate.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import ClassVar

from apexfin.core.models import Signal, SilverPoint
from apexfin.core.registry import register_strategy
from apexfin.decision.base import BaseStrategy, MarketView

# Signal threshold on the 5-trading-day return: below this in either direction
# the move is treated as noise and the symbol gets no signal.
_RETURN_EPSILON = 0.005
# Maps a return magnitude to a signal strength in [-1, 1]. A 10% move saturates.
_STRENGTH_PER_UNIT = 10.0


@register_strategy("toy_momentum")
class ToyMomentum(BaseStrategy):
    """5-trading-day close-to-close momentum. Demonstration only."""

    name: ClassVar[str] = "toy_momentum"

    def generate(self, view: MarketView) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in view.symbols():
            if not view.is_healthy(symbol):
                # is_healthy already checked -- but be explicit and never guess.
                continue
            points = view.series(symbol, lookback=10)
            if len(points) < 2:
                continue
            signal = self._signal_for(symbol, points, view.as_of)
            if signal is not None:
                signals.append(signal)
        return signals

    def _signal_for(self, symbol: str, points: Sequence[SilverPoint], as_of: date) -> Signal | None:
        latest = points[-1]
        window = points[-6] if len(points) >= 6 else points[0]
        base = window.value
        if base <= 0:
            return None
        total_return = latest.value / base - 1.0
        if abs(total_return) < _RETURN_EPSILON:
            return None

        direction = "long" if total_return > 0 else "short"
        strength = max(-1.0, min(1.0, abs(total_return) * _STRENGTH_PER_UNIT))
        rationale = (
            f"近 5 交易日收盘 {window.value:.2f} -> {latest.value:.2f}，"
            f"区间收益 {total_return:+.2%}；动量信号{'为正' if direction == 'long' else '为负'}。"
            "样本量小，仅作演示，不构成投资建议。"
        )
        return Signal(
            strategy=self.name,
            symbol=symbol,
            direction=direction,  # type: ignore[arg-type]
            strength=round(strength, 4),
            as_of=as_of,
            rationale=rationale,
            inputs={
                "close_base": round(float(base), 4),
                "close_latest": round(float(latest.value), 4),
                "return": round(float(total_return), 6),
            },
        )
