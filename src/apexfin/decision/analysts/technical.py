"""Technical analyst -- price-structure read (port of APEXDATA `technical` role).

Turns the tradeable symbol's own price history into a directional stance using
two reference measures (momentum and trend regime), then fuses them into one
verdict with evidence sentences. Pure computation, no storage access.

Reference implementation, not investment advice.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from apexfin.core.models import SilverPoint
from apexfin.decision.analysts.contracts import AnalystView

#: Momentum window (trading days) and threshold below which no signal.
_MOMENTUM_DAYS = 5
_RETURN_EPSILON = 0.005
_STRENGTH_PER_UNIT = 10.0

#: Trend regime SMA windows and the flat band around parity.
_FAST = 5
_SLOW = 20
_MIN_COVERAGE = 0.5
_FLAT_BAND = 0.003

#: Confidence mapping: how signal strength in [0,1] becomes APEXDATA 0..100.
_CONF_SCALE = 60.0
_FLAT_CONF = 35.0


def analyze_technical(
    symbol: str, points: Sequence[SilverPoint], as_of: date | None
) -> AnalystView:
    """Technical verdict from a price series, or unavailable if too short."""
    if len(points) < _SLOW * _MIN_COVERAGE:
        return AnalystView(
            role="technical",
            symbol=symbol,
            direction="neutral",
            confidence=0.0,
            available=False,
            note="价格序列不足（少于 10 个交易日），无法评估趋势",
            as_of=as_of,
        )

    evidence: list[str] = []
    # Momentum leg.
    latest = points[-1]
    window = points[-(_MOMENTUM_DAYS + 1)] if len(points) >= _MOMENTUM_DAYS + 1 else points[0]
    base = window.value
    mom_return = (latest.value / base - 1.0) if base > 0 else 0.0
    if abs(mom_return) >= _RETURN_EPSILON:
        mom_dir = "long" if mom_return > 0 else "short"
        evidence.append(
            f"近 {_MOMENTUM_DAYS} 日收盘 {base:.2f}→{latest.value:.2f}，区间收益 {mom_return:+.2%}"
        )
    else:
        mom_dir = "flat"
        evidence.append(f"近 {_MOMENTUM_DAYS} 日区间收益 {mom_return:+.2%}，处于噪声带")

    # Trend leg.
    fast_sma = sum(float(p.value) for p in points[-_FAST:]) / _FAST
    slow_sma = sum(float(p.value) for p in points[-_SLOW:]) / _SLOW
    gap = (fast_sma / slow_sma - 1.0) if slow_sma > 0 else 0.0
    if abs(gap) < _FLAT_BAND:
        trend_dir = "flat"
        evidence.append(f"SMA{_FAST}（{fast_sma:.2f}）≈ SMA{_SLOW}（{slow_sma:.2f}），趋势未定")
    else:
        trend_dir = "long" if gap > 0 else "short"
        trend_word = "上方" if trend_dir == "long" else "下方"
        evidence.append(
            f"SMA{_FAST}（{fast_sma:.2f}）在 SMA{_SLOW}（{slow_sma:.2f}）"
            f"{trend_word}，偏离 {gap:+.2%}"
        )

    # Fuse: momentum and trend agreeing -> strong; disagreeing -> weak/no stance.
    stance = _fuse(mom_dir, trend_dir, mom_return, gap)
    direction, confidence, note = stance

    return AnalystView(
        role="technical",
        symbol=symbol,
        direction=direction,
        confidence=round(confidence, 1),
        evidence=evidence,
        note=note,
        available=True,
        as_of=as_of,
    )


def _fuse(mom_dir: str, trend_dir: str, mom_return: float, gap: float) -> tuple[str, float, str]:
    """Fuse momentum + trend into a stance and APEXDATA-style confidence."""
    if mom_dir == "flat" and trend_dir == "flat":
        return "flat", _FLAT_CONF, "动量和趋势均无方向，判定横盘"

    if mom_dir == trend_dir:
        strength = min(1.0, max(abs(mom_return) * _STRENGTH_PER_UNIT, abs(gap) / 0.05))
        conf = round(min(100.0, 35.0 + strength * _CONF_SCALE), 1)
        word = "偏多" if mom_dir == "long" else "偏空"
        return mom_dir, conf, f"动量和趋势同向{word}，信号共振"

    # Disagree: momentum vs trend. Weight trend slightly for the medium frame.
    return "flat", 30.0, "动量和趋势背离（动量短周期与趋势中周期相反），暂不形成方向"
