"""Generate the committed offline fixture packs for `src/apexfin/sources/fixtures/`.

The pipeline's demo path (O-01) replays committed JSON files through the
fixture collector: zero network, zero credentials, byte-reproducible on any
machine on any day. Two packs live side by side:

  fresh -- AAPL (OHLCV, risk_essential) and CPI (macro YoY %, support), both
           current through `as_of`. The daily chain passes and exits 0.
  stale -- AAPL frozen one week behind `as_of` while CPI stays current. The
           risk-essential freshness check fires BLOCKING, the gate blocks and
           the run exits 4 (the `make demo-stale` contract).

The files are the deliverable; this script is only the reproducible way to
regenerate them. Run: `.venv/bin/python tools/build_fixtures.py`.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from apexfin.core.trading_calendar import NyseTradingCalendar

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "apexfin" / "sources" / "fixtures"

_CALENDAR = NyseTradingCalendar()
_SEED = 20260802

_FRESH_AS_OF = date(2026, 7, 31)  # a Friday
_STALE_AS_OF = date(2026, 8, 7)  # one week later


def _trading_days(end: date, count: int) -> list[date]:
    """The `count` trading days ending at `end`, ascending."""
    cursor = end
    days: list[date] = []
    while len(days) < count:
        if _CALENDAR.is_trading_day(cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _equity_records(
    end: date, count: int, symbol: str, seed: int, start_close: float
) -> list[dict[str, object]]:
    """Deterministic OHLCV walk for one equity symbol. High/low enclose open
    and close. Each symbol gets its own seed and price base so the walk is
    symbol-specific while remaining byte-reproducible."""
    # Deterministic demo data, not a security boundary: a seeded PRNG is the
    # whole point (byte-reproducible packs), so S311 does not apply here.
    rng = random.Random(seed)  # noqa: S311
    close = start_close
    rows: list[dict[str, object]] = []
    for day in _trading_days(end, count):
        gap = rng.uniform(-0.004, 0.004)
        open_ = round(close * (1 + gap), 2)
        move = rng.uniform(-0.018, 0.018)
        close = max(1.0, open_ * (1 + move))
        high = round(max(open_, close) * (1 + rng.uniform(0.001, 0.012)), 2)
        low = round(min(open_, close) * (1 - rng.uniform(0.001, 0.012)), 2)
        volume = rng.randint(38_000_000, 68_000_000)
        rows.append(
            {
                "symbol": symbol,
                "event_time": f"{day.isoformat()}T20:00:00Z",
                "open": open_,
                "high": high,
                "low": low,
                "close": round(close, 2),
                "volume": volume,
                "unit": "usd",
            }
        )
    return rows


#: (symbol, seed, start_close) per equity series in the fixture pack.
_EQUITIES = [
    ("AAPL", _SEED, 230.0),
    ("SPY", _SEED + 10, 545.0),
    ("QQQ", _SEED + 20, 470.0),
]


def _macro_records(
    end: date, count: int, symbol: str, seed: int, start_value: float
) -> list[dict[str, object]]:
    """Deterministic macro series walk. Stays in a plausible band per series."""
    band = _MACRO_BANDS.get(symbol, (0.5, 6.0))
    low, high = band
    rng = random.Random(seed)  # noqa: S311 - demo data, see _equity_records
    value = start_value
    rows: list[dict[str, object]] = []
    for day in _trading_days(end, count):
        value = max(low, min(high, value + rng.uniform(-0.08, 0.08)))
        rows.append(
            {
                "symbol": symbol,
                "event_time": f"{day.isoformat()}T12:00:00Z",
                "value": round(value, 2),
                "unit": "percent",
            }
        )
    return rows


#: Plausible bands per macro symbol so VIX stays in a stress-meaningful range
#: (12-28) instead of being clipped to the same [0.5, 6.0] band as yields.
_MACRO_BANDS: dict[str, tuple[float, float]] = {
    "CPI": (2.0, 5.0),
    "DGS10": (3.0, 5.5),
    "VIX": (12.0, 28.0),
}

#: (symbol, seed, start_value, unit) per macro series in the fixture pack.
_MACROS = [
    ("CPI", _SEED + 1, 2.9, "percent"),
    ("DGS10", _SEED + 2, 4.1, "percent"),
    ("VIX", _SEED + 3, 16.5, "index"),
]


def _equity_doc(end: date) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for symbol, seed, start in _EQUITIES:
        records.extend(_equity_records(end, 30, symbol, seed, start))
    return {
        "source_name": "fixture_equity",
        "domain": "equity",
        "tier": "risk_essential",
        "frequency": "DAILY",
        "records": records,
    }


def _macro_doc(end: date) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for symbol, seed, start, _unit in _MACROS:
        records.extend(_macro_records(end, 30, symbol, seed, start))
    return {
        "source_name": "fixture_macro",
        "domain": "macro",
        "tier": "support",
        "frequency": "DAILY",
        "records": records,
    }


def _meta(pack: str, as_of: date, description: str) -> dict[str, object]:
    instant = datetime.combine(as_of, time(12, 0))
    return {
        "pack": pack,
        "as_of": instant.isoformat(timespec="seconds") + "Z",
        "description": description,
    }


def _write(pack_dir: Path, name: str, doc: dict[str, object]) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / name).write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> None:
    # fresh: everything current through 2026-07-31.
    fresh = FIXTURES / "fresh"
    _write(fresh, "fixture_equity.json", _equity_doc(_FRESH_AS_OF))
    _write(fresh, "fixture_macro.json", _macro_doc(_FRESH_AS_OF))
    _write(
        fresh,
        "_meta.json",
        _meta("fresh", _FRESH_AS_OF, "All series within SLA; demo exits 0."),
    )

    # stale: AAPL frozen at 07-31 while the clock runs to 08-07, so the
    # risk-essential freshness check lags 5 trading days and blocks the run.
    stale = FIXTURES / "stale"
    _write(stale, "fixture_equity.json", _equity_doc(_FRESH_AS_OF))
    _write(stale, "fixture_macro.json", _macro_doc(_STALE_AS_OF))
    _write(
        stale,
        "_meta.json",
        _meta(
            "stale",
            _STALE_AS_OF,
            "AAPL intentionally one week behind; demo exits 4 (BLOCKED).",
        ),
    )

    for pack_dir in (fresh, stale):
        files = sorted(p.name for p in pack_dir.glob("*.json"))
        print(f"{pack_dir.relative_to(ROOT)}: {', '.join(files)}")


if __name__ == "__main__":
    main()
