"""O-12 regression: a fixture pack freezes the clock to its `_meta.json` as_of.

Without this, `run daily --fixture-pack stale` depends on the wall clock: the
stale scenario only blocks when the real "today" is far enough past the pack's
frozen date, which makes `make demo-stale`'s exit-4 assertion machine- and
date-dependent. The architect's ruling (O-12) fixes the freeze priority --
explicit `--as-of` > pack `meta.as_of` > system clock -- and this test locks
the two bare fixture-pack runs that must be reproducible on any machine on any
day.
"""

from __future__ import annotations

from pathlib import Path

from apexfin.cli.context import build_context
from apexfin.cli.pipeline_cmds import cmd_run
from apexfin.cli.state import CliState

ROOT = Path(__file__).resolve().parents[1]


def _run(tmp_path: Path, fixture_pack: str) -> tuple[int, str]:
    state = CliState(root=ROOT, db=tmp_path / "qa.db")
    ctx = build_context(state, fixture_pack=fixture_pack)
    code = cmd_run(
        ctx,
        manifest_path=None,
        fixture_pack=fixture_pack,
        only=(),
        skip=(),
        continue_on_error=False,
    )
    row = ctx.run.run_row(ctx.run_id)
    assert row is not None
    return code, str(row["state"])


def test_stale_pack_blocks_without_as_of(tmp_path: Path) -> None:
    code, state = _run(tmp_path, "stale")
    assert code == 4
    assert state == "BLOCKED"


def test_fresh_pack_passes_without_as_of(tmp_path: Path) -> None:
    code, state = _run(tmp_path, "fresh")
    assert code == 0
    assert state == "PASS"


def test_explicit_as_of_overrides_pack(tmp_path: Path) -> None:
    state = CliState(root=ROOT, db=tmp_path / "qa.db", as_of="2026-08-07")
    ctx = build_context(state, fixture_pack="fresh")
    # The fresh pack freezes at 2026-07-31, but an explicit --as-of wins (O-12).
    assert ctx.clock.today().isoformat() == "2026-08-07"
