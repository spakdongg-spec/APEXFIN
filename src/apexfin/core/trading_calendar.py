"""Self-built NYSE trading calendar.

Why not `exchange_calendars` / `pandas_market_calendars`: both pull pandas,
which alone would blow the dependency and cold-start budget (ADR-008). The
rules below are small, auditable and stable.

Honest boundaries, stated rather than hidden:
  - NYSE only. Other exchanges need their own TradingCalendar implementation.
  - Full-day closures only. Half sessions (day after Thanksgiving, Christmas
    Eve) are ordinary trading days here, because this project's freshness math
    counts whole business days.
  - Rule-based years 2000..2100. Outside that range the answer would be a
    guess, so it raises CalendarRangeError instead.
  - One-off closures (9/11, state funerals, Sandy) come from
    `config/calendars/nyse.yaml`; the builtin set covers the well-known ones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta

from apexfin.core.errors import CalendarRangeError

MIN_YEAR = 2000
MAX_YEAR = 2100

_SATURDAY = 5
_SUNDAY = 6

# Unscheduled full-day closures. Kept explicit because a rule cannot derive them.
_UNSCHEDULED_CLOSURES: frozenset[date] = frozenset(
    {
        date(2001, 9, 11),
        date(2001, 9, 12),
        date(2001, 9, 13),
        date(2001, 9, 14),
        date(2004, 6, 11),  # Reagan state funeral
        date(2007, 1, 2),  # Ford state funeral
        date(2012, 10, 29),  # Hurricane Sandy
        date(2012, 10, 30),
        date(2018, 12, 5),  # G.H.W. Bush state funeral
        date(2025, 1, 9),  # Carter state funeral
    }
)


def easter_sunday(year: int) -> date:
    """Gregorian Easter (anonymous computus). Good Friday is two days before."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month, day = divmod(h + ll - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """`nth` (1-based) occurrence of `weekday` (Mon=0) in the given month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Last occurrence of `weekday` in the given month."""
    following = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = following - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date, *, roll_back_from_saturday: bool = True) -> date | None:
    """Apply the weekend observance rule to a fixed-date holiday.

    Saturday rolls back to Friday, Sunday rolls forward to Monday. New Year's
    Day is the documented exception: NYSE does not close on 31 December when
    1 January lands on a Saturday, so the caller passes
    `roll_back_from_saturday=False` and the holiday simply disappears.
    """
    if day.weekday() == _SATURDAY:
        return day - timedelta(days=1) if roll_back_from_saturday else None
    if day.weekday() == _SUNDAY:
        return day + timedelta(days=1)
    return day


def nyse_holidays(year: int) -> frozenset[date]:
    """Full-day NYSE closures for one calendar year."""
    days: set[date] = set()

    new_year = _observed(date(year, 1, 1), roll_back_from_saturday=False)
    if new_year is not None and new_year.year == year:
        days.add(new_year)

    days.add(_nth_weekday(year, 1, 0, 3))  # MLK Day
    days.add(_nth_weekday(year, 2, 0, 3))  # Washington's Birthday
    days.add(easter_sunday(year) - timedelta(days=2))  # Good Friday
    days.add(_last_weekday(year, 5, 0))  # Memorial Day

    if year >= 2022:
        juneteenth = _observed(date(year, 6, 19))
        if juneteenth is not None:
            days.add(juneteenth)

    independence = _observed(date(year, 7, 4))
    if independence is not None:
        days.add(independence)

    days.add(_nth_weekday(year, 9, 0, 1))  # Labor Day
    days.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving

    christmas = _observed(date(year, 12, 25))
    if christmas is not None:
        days.add(christmas)

    return frozenset(d for d in days if d.year == year)


class TradingCalendar(ABC):
    """Business-day arithmetic. The only source of 'how many days late'."""

    name: str

    @abstractmethod
    def is_trading_day(self, day: date) -> bool: ...

    @abstractmethod
    def previous_trading_day(self, day: date) -> date: ...

    @abstractmethod
    def next_trading_day(self, day: date) -> date: ...

    @abstractmethod
    def trading_days_between(self, start: date, end: date) -> int:
        """Count trading days in the half-open interval (start, end].

        Zero when `end <= start`. Half-open on purpose: a series whose last
        event is today is zero trading days late, not one.
        """

    def add_trading_days(self, start: date, count: int) -> date:
        """The date `count` trading days after `start`.

        Concrete rather than abstract: it is `next_trading_day` applied `count`
        times, and an implementation that disagreed with that would be
        inconsistent with its own definition of a session. Horizons are stated
        in trading days everywhere in this project (O-07), so a 5-day call made
        on a Friday is due the following Friday, not the following Wednesday.
        """
        if count < 0:
            raise ValueError(f"add_trading_days expects count >= 0, got {count}")
        cursor = start
        for _ in range(count):
            cursor = self.next_trading_day(cursor)
        return cursor

    def trading_days_in(self, start: date, end: date) -> tuple[date, ...]:
        """Trading days in the closed interval [start, end], ascending."""
        if end < start:
            return ()
        out: list[date] = []
        cursor = start
        while cursor <= end:
            if self.is_trading_day(cursor):
                out.append(cursor)
            cursor += timedelta(days=1)
        return tuple(out)


class NyseTradingCalendar(TradingCalendar):
    """Weekends + US federal holidays as observed by NYSE."""

    name = "NYSE"

    def __init__(
        self,
        extra_holidays: frozenset[date] | set[date] | None = None,
        extra_sessions: frozenset[date] | set[date] | None = None,
    ) -> None:
        self._extra_holidays = frozenset(extra_holidays or ())
        self._extra_sessions = frozenset(extra_sessions or ())
        self._cache: dict[int, frozenset[date]] = {}

    def _holidays(self, year: int) -> frozenset[date]:
        if year < MIN_YEAR or year > MAX_YEAR:
            raise CalendarRangeError(
                f"{self.name} calendar covers {MIN_YEAR}..{MAX_YEAR}; "
                f"year {year} is outside the range this calendar can vouch for"
            )
        cached = self._cache.get(year)
        if cached is None:
            builtin = nyse_holidays(year)
            unscheduled = frozenset(d for d in _UNSCHEDULED_CLOSURES if d.year == year)
            extra = frozenset(d for d in self._extra_holidays if d.year == year)
            cached = builtin | unscheduled | extra
            self._cache[year] = cached
        return cached

    def is_trading_day(self, day: date) -> bool:
        if day in self._extra_sessions:
            return True
        if day.weekday() >= _SATURDAY:
            return False
        return day not in self._holidays(day.year)

    def previous_trading_day(self, day: date) -> date:
        cursor = day - timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(cursor):
                return cursor
            cursor -= timedelta(days=1)
        raise CalendarRangeError(f"no trading day found in the 30 days before {day.isoformat()}")

    def next_trading_day(self, day: date) -> date:
        cursor = day + timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(cursor):
                return cursor
            cursor += timedelta(days=1)
        raise CalendarRangeError(f"no trading day found in the 30 days after {day.isoformat()}")

    def trading_days_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        # Touch both endpoints so an out-of-range query fails loudly rather
        # than quietly returning a count computed over a partial range.
        self._holidays(start.year)
        self._holidays(end.year)
        count = 0
        cursor = start + timedelta(days=1)
        while cursor <= end:
            if self.is_trading_day(cursor):
                count += 1
            cursor += timedelta(days=1)
        return count
