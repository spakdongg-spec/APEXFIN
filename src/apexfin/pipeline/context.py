"""The run context handed to every pipeline step (INTERFACES 六, extended).

`pipeline` is L4 so it may import {core, storage, L3}; the context therefore
carries the concrete repositories a step needs plus the clock, calendar and
catalog. `reporting` receives an instance of this as a loosely-typed `object`
and touches only `core`/`storage` through the repositories on it -- it never
imports `pipeline`, so `reporting` stays liftable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from apexfin.core.catalog import SourceCatalog
from apexfin.core.clock import Clock
from apexfin.core.config import Settings
from apexfin.core.enums import GateVerdict
from apexfin.core.trading_calendar import TradingCalendar
from apexfin.quality.expectations import ExpectationTable
from apexfin.storage.bronze_repo import BronzeRepository
from apexfin.storage.decision_repo import DecisionRepository
from apexfin.storage.quality_repo import QualityRepository
from apexfin.storage.run_repo import RunRepository
from apexfin.storage.silver_repo import SilverRepository


@dataclass
class RunContext:
    """Everything a step is allowed to touch during one run."""

    run_id: str
    clock: Clock
    calendar: TradingCalendar
    settings: Settings
    conn: sqlite3.Connection
    gate_state: GateVerdict
    catalog: SourceCatalog
    expectations: ExpectationTable
    bronze: BronzeRepository
    silver: SilverRepository
    quality: QualityRepository
    run: RunRepository
    decision: DecisionRepository
    fixture_pack: str | None = None
    manifest_hash: str = ""
