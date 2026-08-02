"""Macro-regime reference strategy -- risk environment read from macro inputs.

Unlike the equity strategies, this one does not look at a single symbol's own
price history: it reads the macro series the pipeline collected (VIX, 10Y
yield, CPI) and turns them into a risk-environment stance applied to every
tradeable asset. High VIX + rising yields + accelerating CPI -> risk-off
(short the equity basket); calm VIX + stable yields -> risk-on (long).

Demonstration only, not investment advice. The weights are illustrative, and
the skeleton's point is the shape of the workflow, not the stance itself.
"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from apexfin.core.models import Signal, SilverPoint
from apexfin.core.registry import register_strategy
from apexfin.decision.base import BaseStrategy, MarketView

#: VIX above this is treated as a stressed regime.
_VIX_STRESS = 20.0
#: 10Y yield change over the lookback beyond this adds risk-off pressure.
_YIELD_RISE_PCT = 0.25
#: CPI YoY above this is treated as hot.
_CPI_HOT = 3.0
_LOOKBACK = 20


@register_strategy("macro_regime")
class MacroRegime(BaseStrategy):
    """Regime stance (long/short/flat) derived from macro series, applied to
    every healthy tradeable symbol."""

    name: ClassVar[str] = "macro_regime"

    def generate(self, view: MarketView) -> list[Signal]:
        vix = _latest(view, "VIX")
        dgs10 = _latest(view, "DGS10")
        cpi = _latest(view, "CPI")
        if vix is None:
            # Without a volatility reading there is no regime claim to make.
            return []

        regime_strength, stance, rationale = _regime(view, vix, dgs10, cpi, view.as_of)

        signals: list[Signal] = []
        for symbol in view.symbols():
            if not view.is_healthy(symbol):
                continue
            if view.domain_of(symbol) != "equity":
                continue
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=symbol,
                    direction=stance,  # type: ignore[arg-type]
                    strength=regime_strength,
                    as_of=view.as_of,
                    rationale=rationale,
                    inputs={
                        "vix": round(float(vix.value), 4),
                        **({"dgs10": round(float(dgs10.value), 4)} if dgs10 is not None else {}),
                        **({"cpi": round(float(cpi.value), 4)} if cpi is not None else {}),
                    },
                )
            )
        return signals


def _latest(view: MarketView, symbol: str) -> SilverPoint | None:
    """The most recent healthy reading of a macro series, or None."""
    if not view.is_healthy(symbol):
        return None
    points = view.series(symbol, lookback=_LOOKBACK)
    return points[-1] if points else None


def _regime(
    view: MarketView,
    vix: SilverPoint,
    dgs10: SilverPoint | None,
    cpi: SilverPoint | None,
    as_of: date,
) -> tuple[float, str, str]:
    """Score the risk environment: positive = risk-on, negative = risk-off."""
    score = 0.0
    factors: list[str] = []

    # VIX level: the dominant risk gauge.
    if vix.value >= _VIX_STRESS:
        score -= 0.6
        factors.append(f"VIX {vix.value:.1f} 高于 {_VIX_STRESS:.0f}，市场处于紧张状态")
    else:
        score += 0.4
        factors.append(f"VIX {vix.value:.1f} 低于 {_VIX_STRESS:.0f}，波动环境温和")

    # 10Y yield trend: rising yields pressure risk assets.
    if dgs10 is not None:
        yield_rise = _series_change(view, "DGS10")
        if yield_rise > _YIELD_RISE_PCT:
            score -= 0.3
            factors.append(f"10Y 收益率近 20 日上行 {yield_rise:+.2f}%，压制风险资产")
        elif yield_rise < -_YIELD_RISE_PCT:
            score += 0.2
            factors.append(f"10Y 收益率近 20 日下行 {yield_rise:+.2f}%，宽松预期支撑风险偏好")

    # CPI level: hot inflation erodes the dovish case.
    if cpi is not None and cpi.value > _CPI_HOT:
        score -= 0.2
        factors.append(f"CPI 同比 {cpi.value:.1f}% 高于 {_CPI_HOT:.1f}%，通胀约束宽松空间")

    if not factors:
        factors.append("宏观读数不足，仅以 VIX 基准评估")

    score = max(-1.0, min(1.0, score))
    if abs(score) < 0.15:
        stance = "flat"
        head = "宏观环境中性"
    elif score > 0:
        stance = "long"
        head = "宏观环境偏风险偏好（risk-on）"
    else:
        stance = "short"
        head = "宏观环境偏风险规避（risk-off）"

    detail = "；".join(factors)
    return (
        round(abs(score), 4),
        stance,
        f"{head}：{detail}。宏观信号作用于全部可交易资产。仅作演示，不构成投资建议。"
        f"（评估基准日 {as_of.isoformat()}）",
    )


def _series_change(view: MarketView, symbol: str) -> float:
    """Total % change of a macro series over its two latest readings."""
    points = view.series(symbol, lookback=_LOOKBACK)
    if len(points) < 2:
        return 0.0
    base = float(points[-2].value)
    if base == 0:
        return 0.0
    return float(points[-1].value) / base - 1.0
