"""Chart assembly, including the no-JavaScript fallback table.

The chart `kind` is decided by what the data actually is, not by a hard-coded
list of symbols:

* every point carries a full OHLC bar in `payload_json` -> `candlestick`
* the series is expressed in percent -> `macro` (a line with an end label,
  which is how a rate or an index level is normally read)
* anything else -> `line`

A series that only has closes gets a line and says so by its `kind`. Faking a
candle out of a close -- four identical prices -- would render a row of flat
doji bars that look like real sessions with no range, which is worse than an
honest line.
"""

from __future__ import annotations

from typing import Any

from apexfin.core.models import SeriesSpec, SilverPoint
from apexfin.reporting.models import Chart

#: How many trading days of history each chart shows.
LOOKBACK = 60

_OHLC_KEYS = ("open", "high", "low", "close")


def build_charts(catalog: Any, silver: Any) -> list[Chart]:
    charts: list[Chart] = []
    for spec in catalog.series(enabled_only=True):
        points = silver.series(spec.source_name, spec.symbol, LOOKBACK)
        if len(points) < 2:
            # One point is not a chart. Rendering it would imply a trend that
            # a single observation cannot support.
            continue
        bars = _bars(points)
        if bars is not None:
            charts.append(_candlestick(spec, points, bars))
        elif (spec.unit or points[-1].unit) == "percent":
            charts.append(_macro(spec, points))
        else:
            charts.append(_line(spec, points))
    return charts


def _bars(points: tuple[SilverPoint, ...]) -> list[dict[str, float]] | None:
    """Full OHLC for every point, or `None` if even one bar is incomplete."""
    out: list[dict[str, float]] = []
    for p in points:
        payload = p.payload_json
        if not payload or any(k not in payload for k in _OHLC_KEYS):
            return None
        try:
            out.append({k: float(payload[k]) for k in _OHLC_KEYS})
        except (TypeError, ValueError):
            return None
    return out


def _axis(points: tuple[SilverPoint, ...]) -> list[str]:
    return [p.event_date.strftime("%m-%d") for p in points]


def _candlestick(
    spec: SeriesSpec, points: tuple[SilverPoint, ...], bars: list[dict[str, float]]
) -> Chart:
    xs = _axis(points)
    # ECharts wants [open, close, low, high] -- not the OHLC order a human
    # reads. Getting this wrong swaps the body and the wicks and produces a
    # chart that is confidently wrong, so the two orderings are built
    # separately: this one for the renderer, the fallback table for the reader.
    series_data = [[b["open"], b["close"], b["low"], b["high"]] for b in bars]
    rows: list[list[str | float]] = [
        [xs[i], b["open"], b["high"], b["low"], b["close"]] for i, b in enumerate(bars)
    ]
    return Chart(
        chart_id=f"price-{spec.symbol}",
        title=f"{spec.label or spec.symbol} 日K（演示）",
        kind="candlestick",
        icon_id="candlestick-chart",
        option={
            "xAxis": {"type": "category", "data": xs},
            "yAxis": {"scale": True},
            "series": [{"type": "candlestick", "data": series_data}],
        },
        fallback_columns=["日期", "开盘", "最高", "最低", "收盘"],
        fallback_rows=rows,
    )


def _macro(spec: SeriesSpec, points: tuple[SilverPoint, ...]) -> Chart:
    xs = _axis(points)
    ys = [round(float(p.value), 4) for p in points]
    return Chart(
        chart_id=f"macro-{spec.symbol}",
        title=f"{spec.label or spec.symbol}（演示）",
        kind="macro",
        icon_id="line-chart",
        option={
            "xAxis": {"type": "category", "data": xs},
            "yAxis": {},
            "series": [{"type": "line", "data": ys, "endLabel": {"show": True}}],
        },
        fallback_columns=["日期", f"{spec.symbol}(%)"],
        fallback_rows=[[xs[i], ys[i]] for i in range(len(xs))],
    )


def _line(spec: SeriesSpec, points: tuple[SilverPoint, ...]) -> Chart:
    xs = _axis(points)
    ys = [round(float(p.value), 4) for p in points]
    unit = spec.unit or points[-1].unit or ""
    header = f"{spec.symbol}（{unit}）" if unit else spec.symbol
    return Chart(
        chart_id=f"series-{spec.symbol}",
        title=f"{spec.label or spec.symbol} 收盘（演示）",
        kind="line",
        icon_id="line-chart",
        option={
            "xAxis": {"type": "category", "data": xs},
            "yAxis": {"scale": True},
            "series": [{"type": "line", "data": ys}],
        },
        fallback_columns=["日期", header],
        fallback_rows=[[xs[i], ys[i]] for i in range(len(xs))],
    )
