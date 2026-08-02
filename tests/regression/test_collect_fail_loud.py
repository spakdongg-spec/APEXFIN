"""Regression: collect must fail loud instead of silently doing nothing.

Discovered 2026-08-02 by QA (Phase 4) against the original delivery:
- D-1: bare `apexfin collect` returned exit 0 with 0 bronze rows. The two
  fixture collectors could not be constructed (they need a pack path) but the
  failure was swallowed and the "no collectors" guard was vacuous, so the step
  reported success. Fixed: `AllSourcesFailedError` (exit 5) with a message that
  names the configured sources and the missing `--fixture-pack`.
- D-2: `collect --source yahoo` (undeclared in config/sources.yaml) returned 0
  with nothing collected -- a misleading success. Fixed: `ConfigError` (exit 3)
  naming the unknown source and the declared ones.
- D-3 (SPEC AC-04): a blocked upstream source wrote no `quality_findings` row,
  so the refusal was only visible in logs. Fixed: every failing source writes a
  `collect`/WARNING finding while healthy sources still produce data.
- D-4 (CLI_CONTRACT 四): a run that wrote nothing (`inserted==0 && duplicates==0`)
  was reported as success. Fixed: a WARNING finding is written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import apexfin.pipeline.collect as collect_mod
from apexfin.cli.context import build_context
from apexfin.cli.pipeline_cmds import run_steps
from apexfin.cli.state import CliState
from apexfin.core.clock import parse_utc
from apexfin.core.enums import Frequency
from apexfin.core.errors import AllSourcesFailedError, ConfigError, SourceBlockedError
from apexfin.core.models import RawRecord, SourceCapabilities, UpsertStats
from apexfin.sources.base import BaseCollector

ROOT = Path(__file__).resolve().parents[2]


class _OkCollector(BaseCollector):
    def capabilities(self) -> SourceCapabilities:
        return SourceCapabilities(
            source_name="oksrc",
            domain="equity",
            symbols=("A",),
            frequency=Frequency.DAILY,
            requires_credentials=False,
            supports_full_refresh=True,
            min_request_interval_s=0.0,
        )

    def _fetch_raw(self, window):
        return [
            RawRecord(
                source_name="oksrc",
                domain="equity",
                symbol="A",
                event_time=parse_utc("2026-07-31T00:00:00Z"),
                payload={"close": 1.0},
            )
        ]


class _BlockedCollector(BaseCollector):
    def capabilities(self) -> SourceCapabilities:
        return SourceCapabilities(
            source_name="blksrc",
            domain="equity",
            symbols=("B",),
            frequency=Frequency.DAILY,
            requires_credentials=False,
            supports_full_refresh=True,
            min_request_interval_s=0.0,
        )

    def _fetch_raw(self, window):
        raise SourceBlockedError("blksrc: upstream returned HTTP 429 for B.")


def _ctx(tmp_path: Path):
    state = CliState(root=ROOT, db=tmp_path / "qa.db")
    return build_context(state)


def _patch_collectors(monkeypatch: pytest.MonkeyPatch, collectors: list) -> None:
    monkeypatch.setattr(
        collect_mod, "_build_collectors", lambda c, sources=(), symbols=(): collectors
    )


def test_bare_collect_without_fixture_pack_raises_all_sources_failed(tmp_path: Path) -> None:
    """D-1: the default catalog's fixture collectors need a pack; empty must not be silent."""
    ctx = _ctx(tmp_path)
    with pytest.raises(AllSourcesFailedError) as excinfo:
        collect_mod.collect_step(ctx)
    message = str(excinfo.value)
    assert "no collectors could be constructed" in message
    assert "--fixture-pack" in message
    assert "fixture_equity" in message


def test_unknown_source_is_config_error(tmp_path: Path) -> None:
    """D-2: an undeclared --source must be a loud ConfigError, not a silent no-op."""
    ctx = _ctx(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        collect_mod.collect_step(ctx, sources=("yahoo",))
    message = str(excinfo.value)
    assert "unknown source(s): yahoo" in message
    assert "config/sources.yaml declares" in message


def test_blocked_source_writes_finding_and_healthy_source_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-3 (AC-04): one blocked source -> WARNING finding; healthy source still ingested."""
    ctx = _ctx(tmp_path)
    _patch_collectors(monkeypatch, [_OkCollector(), _BlockedCollector()])
    code = run_steps(ctx, [("collect", collect_mod.collect_step)])
    assert code == 0  # single-source failure does not abort the run
    assert (
        ctx.conn.execute(
            "SELECT COUNT(*) FROM bronze_records WHERE source_name='oksrc'"
        ).fetchone()[0]
        == 1
    )
    rows = ctx.conn.execute(
        "SELECT check_id, severity, source_name, message FROM quality_findings"
    ).fetchall()
    assert any(r[0] == "collect" and r[1] == "WARNING" and r[2] == "blksrc" for r in rows)


def test_noop_collection_writes_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-4 (CLI_CONTRACT 四): inserted==0 and duplicates==0 is a warning, not success."""
    ctx = _ctx(tmp_path)
    _patch_collectors(monkeypatch, [_OkCollector()])

    class _NoopBronze:
        def __init__(self, real):
            self._real = real

        def upsert(self, records, run_id, now):
            return UpsertStats(inserted=0, duplicates=0, revisions=0)

        def clear_source(self, *args, **kwargs):
            return self._real.clear_source(*args, **kwargs)

    ctx.bronze = _NoopBronze(ctx.bronze)  # type: ignore[assignment]
    code = run_steps(ctx, [("collect", collect_mod.collect_step)])
    assert code == 0
    rows = ctx.conn.execute("SELECT check_id, severity, message FROM quality_findings").fetchall()
    assert any(r[0] == "collect" and r[1] == "WARNING" and "wrote nothing" in r[2] for r in rows)
