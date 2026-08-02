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


def _equity_records(end: date, count: int) -> list[dict[str, object]]:
    """Deterministic OHLCV walk for AAPL. High/low enclose open and close."""
    # Deterministic demo data, not a security boundary: a seeded PRNG is the
    # whole point (byte-reproducible packs), so S311 does not apply here.
    rng = random.Random(_SEED)  # noqa: S311
    close = 230.0
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
                "symbol": "AAPL",
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


def _macro_records(end: date, count: int) -> list[dict[str, object]]:
    """Deterministic CPI YoY percent walk. Stays in a plausible band."""
    rng = random.Random(_SEED + 1)  # noqa: S311 - demo data, see _equity_records
    value = 2.9
    rows: list[dict[str, object]] = []
    for day in _trading_days(end, count):
        value = max(1.5, min(4.5, value + rng.uniform(-0.08, 0.08)))
        rows.append(
            {
                "symbol": "CPI",
                "event_time": f"{day.isoformat()}T12:00:00Z",
                "value": round(value, 2),
                "unit": "percent",
            }
        )
    return rows


def _equity_doc(end: date) -> dict[str, object]:
    return {
        "source_name": "fixture_equity",
        "domain": "equity",
        "tier": "risk_essential",
        "frequency": "DAILY",
        "records": _equity_records(end, 30),
    }


def _macro_doc(end: date) -> dict[str, object]:
    return {
        "source_name": "fixture_macro",
        "domain": "macro",
        "tier": "support",
        "frequency": "DAILY",
        "records": _macro_records(end, 30),
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
