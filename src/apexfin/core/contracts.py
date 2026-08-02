"""Structural protocols shared across layers (INTERFACES 三/六/十).

Domain code depends on these narrow ports, never on a concrete repository.
That is what lets `quality/` be lifted out of this repository wholesale.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from apexfin.core.models import BronzeRecord, LedgerEntry, RawRecord, SilverPoint, UpsertStats


@runtime_checkable
class BronzeReadPort(Protocol):
    def latest_event_date(self, source_name: str, symbol: str) -> date | None: ...

    def count_between(self, source_name: str, symbol: str, start: date, end: date) -> int: ...

    def distinct_series(self) -> tuple[tuple[str, str], ...]: ...

    def duplicate_event_dates(self, source_name: str, symbol: str) -> tuple[str, ...]:
        """Event dates carrying more than one bronze row for the same series.

        On the port rather than derived from counts by the caller: a check that
        infers duplication from `count_between` can say 'something is doubled'
        but not which day, and a finding that cannot name the day is not
        actionable.
        """


@runtime_checkable
class BronzeWritePort(Protocol):
    def upsert(self, records: tuple[RawRecord, ...], run_id: str, now: datetime) -> UpsertStats: ...


@runtime_checkable
class SilverReadPort(Protocol):
    def series(self, source_name: str, symbol: str, lookback: int) -> tuple[SilverPoint, ...]: ...

    def latest_event_date(self, source_name: str, symbol: str) -> date | None: ...

    def distinct_series(self) -> tuple[tuple[str, str], ...]: ...

    def event_dates(self, source_name: str, symbol: str) -> tuple[date, ...]:
        """Every business date the series holds, ascending.

        Calendar-aware checks need the date spine without the values; loading
        full rows to read one column each is the kind of thing that makes a
        governance layer too slow to run daily.
        """


@runtime_checkable
class LedgerWritePort(Protocol):
    """The only thing `accounting` is allowed to know about storage.

    Narrow on purpose: the ledger writer must not be able to read decisions
    back, mutate them, or settle an entry as a side effect of writing it.
    """

    def write_ledger(self, entry: LedgerEntry) -> None: ...


@runtime_checkable
class LedgerSettlePort(Protocol):
    """Read pending entries and close them out. Separate from the write port so
    a caller that only records opinions cannot also grade them."""

    def pending_entries(self) -> tuple[tuple[int, LedgerEntry], ...]: ...

    def settle(
        self,
        entry_id: int,
        settled_on: date,
        settled_value: float | None,
        outcome: str,
        note: str,
    ) -> None: ...


@runtime_checkable
class Extractor(Protocol):
    """Turns one bronze payload into zero or more silver points."""

    source_name: str

    def extract(self, record: BronzeRecord) -> list[SilverPoint]: ...


class ConnectionFactory(Protocol):
    def __call__(self) -> sqlite3.Connection: ...
