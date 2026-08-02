"""Composition root internals: registration imports and `build_context`.

Kept out of `app.py` so that file stays a thin Typer wiring table under the
300-line cap. Importing this module is what makes the decorator registries
non-empty: the six checks, the strategy, the collectors and the extractors all
register at import time and nothing else in the codebase imports them all.
"""

from __future__ import annotations

import apexfin.pipeline.collect
import apexfin.processing.extractors
import apexfin.quality.check_completeness
import apexfin.quality.check_consistency
import apexfin.quality.check_continuity
import apexfin.quality.check_duplicates
import apexfin.quality.check_freshness
import apexfin.quality.check_range
import apexfin.sources.fixture
import apexfin.sources.yahoo
from apexfin.cli.state import CliState
from apexfin.core.catalog import load_catalog
from apexfin.core.clock import FrozenClock, SystemClock, parse_utc
from apexfin.core.config import Settings
from apexfin.core.enums import GateVerdict
from apexfin.core.ids import new_run_id
from apexfin.core.trading_calendar import NyseTradingCalendar
from apexfin.pipeline.context import RunContext
from apexfin.quality.expectations import load_expectations
from apexfin.sources.fixture import load_pack_meta
from apexfin.storage.bronze_repo import BronzeRepository
from apexfin.storage.decision_repo import DecisionRepository
from apexfin.storage.engine import connect
from apexfin.storage.migrator import migrate
from apexfin.storage.quality_repo import QualityRepository
from apexfin.storage.run_repo import RunRepository
from apexfin.storage.silver_repo import SilverRepository

#: The imports above exist for their decorator side effects (they fill the
#: registries). The tuple makes the imports visibly used so a linter cannot
#: "fix" them away and silently empty the pipeline.
_REGISTRATION_MODULES = (
    apexfin.pipeline.collect,
    apexfin.processing.extractors,
    apexfin.quality.check_completeness,
    apexfin.quality.check_consistency,
    apexfin.quality.check_continuity,
    apexfin.quality.check_duplicates,
    apexfin.quality.check_freshness,
    apexfin.quality.check_range,
    apexfin.sources.fixture,
    apexfin.sources.yahoo,
)


def _clock(state: CliState, fixture_pack: str | None) -> FrozenClock | SystemClock:
    """Freeze priority (O-12): explicit --as-of > pack meta.as_of > system clock.

    A fixture pack is a self-contained scenario whose `_meta.json` as_of drives
    the FrozenClock, so a bare `run daily --fixture-pack stale` reproduces the
    stale scenario on any machine on any day instead of depending on when it is
    run (this is what makes `make demo-stale`'s exit-4 assertion reproducible).
    """
    if state.as_of is not None:
        return FrozenClock(parse_utc(f"{state.as_of}T12:00:00Z"))
    if fixture_pack is not None:
        return FrozenClock(load_pack_meta(fixture_pack).as_of)
    return SystemClock()


def build_context(
    state: CliState, *, run_id: str | None = None, fixture_pack: str | None = None
) -> RunContext:
    """Open one connection, migrate, and assemble the RunContext (O-11/B-8/O-12)."""
    settings = Settings()  # honours APEXFIN_* env vars first
    if state.db is not None:
        settings = settings.model_copy(update={"db": state.db})
    if state.config_dir is not None:
        settings = settings.model_copy(update={"config_dir": state.config_dir})
    settings = settings.model_copy(update={"log_level": state.log_level}).resolved(state.root)

    conn = connect(settings.db)
    clock = _clock(state, fixture_pack)
    migrate(conn, clock.now())

    catalog = load_catalog(
        settings.config_dir / "sources.yaml",
        state.root / "contracts" / "sources.schema.json",
    )
    expectations = load_expectations(
        settings.config_dir / "expectations.yaml",
        state.root / "contracts" / "expectations.schema.json",
    )
    expectations.assert_covers(
        ((s.source_name, s.symbol) for s in catalog.series(enabled_only=True)),
        settings.config_dir / "expectations.yaml",
    )

    return RunContext(
        run_id=run_id or new_run_id(clock.now()),
        clock=clock,
        calendar=NyseTradingCalendar(),
        settings=settings,
        conn=conn,
        gate_state=GateVerdict.PASS,
        catalog=catalog,
        expectations=expectations,
        bronze=BronzeRepository(conn),
        silver=SilverRepository(conn),
        quality=QualityRepository(conn),
        run=RunRepository(conn),
        decision=DecisionRepository(conn),
    )
