"""Trend-regime reference strategy -- SMA-crossover view on tradeable assets.

Companion to `toy_momentum`: momentum measures the last N-day return, this
strategy measures where price sits relative to its own moving average. The two
frequently disagree (price can rip higher while sitting below a longer trend
line), and that disagreement is the point -- the aggregator must surface it as
`no_call` instead of pretending a view exists. Demonstrates the multi-strategy
workflow the skeleton is built to copy, not a market claim.

Demonstration only, not investment advice.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import ClassVar

from apexfin.core.models import Signal, SilverPoint
from apexfin.core.registry import register_strategy
from apexfin.decision.base import BaseStrategy, MarketView

#: Fast vs slow window in trading days. 5/20 is the classic demo pair.
_FAST = 5
_SLOW = 20
#: Minimum share of the slow window that must exist before a trend claim.
_MIN_COVERAGE = 0.5
#: SMA gap below which the trend is treated as flat (no directional claim).
_FLAT_BAND = 0.003


@register_strategy("trend_regime")
class TrendRegime(BaseStrategy):
    """Fast/Slow SMA comparison. Long above, short below, flat inside the band."""

    name: ClassVar[str] = "trend_regime"

    def generate(self, view: MarketView) -> list[Signal]:
        signals: list[Signal] = []
        for symbol in view.symbols():
            if not view.is_healthy(symbol):
                continue
            if view.domain_of(symbol) != "equity":
                continue
            points = view.series(symbol, lookback=_SLOW + 5)
            if len(points) < _SLOW * _MIN_COVERAGE:
                continue
            signal = self._signal_for(symbol, points, view.as_of)
            if signal is not None:
                signals.append(signal)
        return signals

    def _signal_for(self, symbol: str, points: Sequence[SilverPoint], as_of: date) -> Signal | None:
        fast_sma = _sma(points, _FAST)
        slow_sma = _sma(points, _SLOW)
        if slow_sma <= 0:
            return None
        gap = fast_sma / slow_sma - 1.0

        if abs(gap) < _FLAT_BAND:
            return Signal(
                strategy=self.name,
                symbol=symbol,
                direction="flat",
                strength=0.0,
                as_of=as_of,
                rationale=(
                    f"SMA{_FAST}（{fast_sma:.2f}）与 SMA{_SLOW}（{slow_sma:.2f}）"
                    f"偏离 {gap:+.2%}，处于 ±{_FLAT_BAND:.2%} 扁平带内，趋势未定，"
                    "不构成方向观点。仅作演示，不构成投资建议。"
                ),
                inputs={
                    "fast_sma": round(float(fast_sma), 4),
                    "slow_sma": round(float(slow_sma), 4),
                    "gap": round(float(gap), 6),
                },
            )

        direction = "long" if gap > 0 else "short"
        # Scale strength so a gap of 5% saturates.
        strength = max(-1.0, min(1.0, abs(gap) / 0.05))
        trend_word = "上方" if direction == "long" else "下方"
        signals_plural = f"SMA{_FAST}（{fast_sma:.2f}）在 SMA{_SLOW}（{slow_sma:.2f}）{trend_word}"
        return Signal(
            strategy=self.name,
            symbol=symbol,
            direction=direction,  # type: ignore[arg-type]
            strength=round(strength, 4),
            as_of=as_of,
            rationale=(
                f"{signals_plural}，偏离 {gap:+.2%}，"
                f"趋势{'偏多' if direction == 'long' else '偏空'}。"
                "均线样本为演示数据，不构成投资建议。"
            ),
            inputs={
                "fast_sma": round(float(fast_sma), 4),
                "slow_sma": round(float(slow_sma), 4),
                "gap": round(float(gap), 6),
            },
        )


def _sma(points: Sequence[SilverPoint], window: int) -> float:
    """Mean of the last `window` closes; falls back to available points."""
    windowed = points[-window:]
    if not windowed:
        return 0.0
    return sum(float(p.value) for p in windowed) / len(windowed)
