"""Injectable clock.

Nothing in this project may call `datetime.now()` or `date.today()` directly.
Every timestamp goes through a Clock so that stale-data injection is a normal
capability of production code rather than a demo-only hack (ARCHITECTURE 2.3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, time


class Clock(ABC):
    """Wall-clock source. Always tz-aware UTC."""

    @abstractmethod
    def now(self) -> datetime:
        """Current instant, tz-aware UTC."""

    def today(self) -> date:
        """Current business date in UTC terms."""
        return self.now().date()


class SystemClock(Clock):
    """The real clock. The only place `datetime.now` is allowed to appear."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class FrozenClock(Clock):
    """A clock stuck at one instant.

    Used by tests and by demo fixture packs so that `make demo` produces a
    byte-identical dashboard on any machine on any day.
    """

    def __init__(self, at: datetime | date) -> None:
        if isinstance(at, datetime):
            instant = at if at.tzinfo is not None else at.replace(tzinfo=UTC)
        else:
            instant = datetime.combine(at, time(0, 0), tzinfo=UTC)
        self._at = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._at

    def __repr__(self) -> str:
        return f"FrozenClock({self._at.isoformat()})"


def to_utc_iso(value: datetime) -> str:
    """Serialize an instant the way DATA_CONTRACT 一 requires."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 instant stored by `to_utc_iso`."""
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
