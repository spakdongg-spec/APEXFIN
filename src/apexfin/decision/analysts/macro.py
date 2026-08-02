"""Macro analyst -- global regime read (port of APEXDATA `macro` role).

Reads the collected macro series (VIX / 10Y yield / CPI) and produces a
risk-environment stance. Unlike `technical`, this role reads *inputs*, not the
tradeable symbol's own history, so it reports the same regime for every symbol
with an `as_of` anchor. High VIX + rising yields + hot CPI -> risk-off.

Reference implementation, not investment advice.
"""

from __future__ import annotations

from datetime import date

from apexfin.core.models import SilverPoint
from apexfin.decision.analysts.contracts import AnalystView
from apexfin.decision.views import MarketViewImpl

_VIX_STRESS = 20.0
_YIELD_RISE_PCT = 0.25
_CPI_HOT = 3.0
_LOOKBACK = 20


def analyze_macro(view: MarketViewImpl, symbol: str, as_of: date | None) -> AnalystView:
    """Regime verdict for one symbol, driven by macro inputs."""
    vix = _latest(view, "VIX")
    if vix is None:
        return AnalystView(
            role="macro",
            symbol=symbol,
            direction="neutral",
            confidence=0.0,
            available=False,
            note="VIX 数据缺失，无法评估风险环境",
            as_of=as_of,
        )

    score = 0.0
    evidence: list[str] = []

    if vix.value >= _VIX_STRESS:
        score -= 0.6
        evidence.append(f"VIX {vix.value:.1f} 高于 {_VIX_STRESS:.0f}，市场处于紧张状态")
    else:
        score += 0.4
        evidence.append(f"VIX {vix.value:.1f} 低于 {_VIX_STRESS:.0f}，波动环境温和")

    dgs10 = _latest(view, "DGS10")
    if dgs10 is not None:
        rise = _series_change(view, "DGS10")
        if rise > _YIELD_RISE_PCT:
            score -= 0.3
            evidence.append(f"10Y 收益率近 20 日上行 {rise:+.2f}%，压制风险资产")
        elif rise < -_YIELD_RISE_PCT:
            score += 0.2
            evidence.append(f"10Y 收益率近 20 日下行 {rise:+.2f}%，宽松预期支撑风险偏好")

    cpi = _latest(view, "CPI")
    if cpi is not None and cpi.value > _CPI_HOT:
        score -= 0.2
        evidence.append(f"CPI 同比 {cpi.value:.1f}% 高于 {_CPI_HOT:.1f}%，通胀约束宽松空间")

    if not evidence:
        evidence.append("宏观读数不足，仅以 VIX 基准评估")

    score = max(-1.0, min(1.0, score))
    if abs(score) < 0.15:
        return AnalystView(
            role="macro",
            symbol=symbol,
            direction="flat",
            confidence=30.0,
            evidence=evidence,
            note="宏观环境中性",
            as_of=as_of,
        )

    direction = "long" if score > 0 else "short"
    conf = round(min(90.0, 35.0 + abs(score) * 55.0), 1)
    word = "风险偏好（risk-on）" if direction == "long" else "风险规避（risk-off）"
    return AnalystView(
        role="macro",
        symbol=symbol,
        direction=direction,
        confidence=conf,
        evidence=evidence,
        note=f"宏观环境{word}",
        as_of=as_of,
    )


def _latest(view: MarketViewImpl, symbol: str) -> SilverPoint | None:
    """Most recent healthy reading of a macro series, or None."""
    if not view.is_healthy(symbol):
        return None
    points = view.series(symbol, lookback=_LOOKBACK)
    return points[-1] if points else None


def _series_change(view: MarketViewImpl, symbol: str) -> float:
    """Total % change over the two latest readings of a macro series."""
    points = view.series(symbol, lookback=_LOOKBACK)
    if len(points) < 2:
        return 0.0
    base = float(points[-2].value)
    if base == 0:
        return 0.0
    return float(points[-1].value) / base - 1.0
