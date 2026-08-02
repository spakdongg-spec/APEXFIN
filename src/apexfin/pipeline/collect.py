"""The collect step: raw record ingestion (L4).

Split out of `pipeline.steps.py` so that the fail-loud guards around collection
live with the code that can silently do nothing -- a no-op collect is the exact
failure this project is written to make impossible (CLI_CONTRACT 四).

Fail-loud guarantees enforced here:
  1. If no collector could be constructed at all, the step raises
     `AllSourcesFailedError` (exit 5) instead of reporting a successful no-op.
     Fixture collectors need a pack path, so a fixture-backed catalog without
     `--fixture-pack` fails here with a message that says so.
  2. Every failing source writes a `collect` finding into `quality_findings`
     (SPEC AC-04), so a blocked upstream is observable after the fact, not just
     logged.
  3. A run that wrote nothing (`inserted == 0 and duplicates == 0`) writes a
     WARNING finding rather than being reported as success (CLI_CONTRACT 四).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from apexfin.core.enums import Severity, StepStatus, Tier
from apexfin.core.errors import AllSourcesFailedError, ConfigError
from apexfin.core.models import CollectResult, FetchWindow, QualityFinding, StepResult
from apexfin.pipeline.context import RunContext
from apexfin.pipeline.registry import step
from apexfin.sources.fixture import FIXTURES_DIR, load_pack_collectors, pack_source_files

log = structlog.get_logger("apexfin.pipeline.collect")


def _build_collectors(
    ctx: RunContext, *, sources: tuple[str, ...] = (), symbols: tuple[str, ...] = ()
) -> list[Any]:
    """Construct the collectors for this run, honouring CLI filters.

    With `--fixture-pack` the pack files decide the sources; `--source` narrows
    which files in the pack are replayed. Without it, `--source` selects from
    *all* declared sources (including disabled ones -- an explicit request) and
    an undeclared source name is a ConfigError, never a silent skip.
    """
    if ctx.fixture_pack is not None:
        collectors = list(load_pack_collectors(ctx.fixture_pack, FIXTURES_DIR))
        if sources:
            wanted = set(sources)
            collectors = [c for c in collectors if c.capabilities().source_name in wanted]
        # A fixture pack is a self-contained scenario: it must replace, not
        # pile onto, previously collected data, or freshness keeps reading
        # the old latest date.
        covered = {c.capabilities().source_name for c in collectors}
        for source_name in covered:
            ctx.bronze.clear_source(source_name)
            ctx.silver.clear_source(source_name)
        return collectors

    from apexfin.core.registry import get_source

    if sources:
        by_name = {s.name: s for s in ctx.catalog.sources}
        missing = [name for name in sources if name not in by_name]
        if missing:
            declared = ", ".join(sorted(by_name)) or "<none>"
            raise ConfigError(
                f"collect: unknown source(s): {', '.join(missing)}. "
                f"config/sources.yaml declares: {declared}"
            )
        pool = [by_name[name] for name in dict.fromkeys(sources)]
    else:
        pool = list(ctx.catalog.enabled())

    out: list[Any] = []
    for source in pool:
        cls = get_source(source.collector)
        if cls is None:
            log.warning("collector.unknown", source=source.name, collector=source.collector)
            continue
        chosen = tuple(s.symbol for s in source.series if not symbols or s.symbol in symbols)
        if symbols and not chosen:
            continue
        try:
            out.append(cls(symbols=chosen, domain=source.domain))
        except Exception as exc:  # noqa: BLE001 - a broken collector is skipped, not fatal
            log.warning("collector.construct_failed", source=source.name, error=repr(exc))
            continue
    return out


@step(
    "collect",
    Tier.RISK_ESSENTIAL,
    depends_on=(),
    critical=True,
    timeout_s=180,
    why="Without fresh raw records every downstream conclusion is stale by construction.",
)
def collect_step(
    ctx: RunContext, sources: tuple[str, ...] = (), symbols: tuple[str, ...] = ()
) -> StepResult:
    now = ctx.clock.now()
    window = FetchWindow(start=date(2000, 1, 1), end=ctx.clock.today(), full_refresh=True)
    collectors = _build_collectors(ctx, sources=sources, symbols=symbols)

    inserted = duplicates = revisions = 0
    ok_count = 0
    failures: list[str] = []
    source_findings: list[QualityFinding] = []
    for collector in collectors:
        result: CollectResult = collector.fetch(window)
        if not result.ok:
            failures.append(f"{result.source_name}: {result.error}")
            source_findings.append(
                QualityFinding(
                    check_id="collect",
                    severity=Severity.WARNING,
                    source_name=result.source_name,
                    symbol=None,
                    message=(
                        f"collect failed for source {result.source_name} (status={result.status})"
                    ),
                    observed=str(result.error),
                    expected="source returns at least one record",
                    tier=Tier.SUPPORT,
                )
            )
            continue
        ok_count += 1
        stats = ctx.bronze.upsert(result.records, ctx.run_id, now)
        inserted += stats.inserted
        duplicates += stats.duplicates
        revisions += stats.revisions

    if ok_count == 0:
        if not collectors:
            if ctx.fixture_pack is not None:
                files = ", ".join(p.name for p in pack_source_files(ctx.fixture_pack, FIXTURES_DIR))
                requested = ", ".join(sources) or "<none>"
                raise AllSourcesFailedError(
                    f"no collectors matched --source ({requested}) inside fixture pack "
                    f"'{ctx.fixture_pack}'; pack files: {files}"
                )
            enabled = ", ".join(s.name for s in ctx.catalog.enabled()) or "<none>"
            raise AllSourcesFailedError(
                f"no collectors could be constructed from configured source(s): {enabled}. "
                "Fixture sources require --fixture-pack (O-01)."
            )
        raise AllSourcesFailedError(
            f"all {len(collectors)} source(s) failed to collect. " + "; ".join(failures)
        )

    if source_findings:
        ctx.quality.write_findings(tuple(source_findings), ctx.run_id, now)
    if inserted == 0 and duplicates == 0:
        ctx.quality.write_findings(
            (
                QualityFinding(
                    check_id="collect",
                    severity=Severity.WARNING,
                    source_name="collect",
                    symbol=None,
                    message=(
                        "collection wrote nothing: inserted==0 and duplicates==0; "
                        "a no-op collection is a warning, not a success (CLI_CONTRACT 四)"
                    ),
                    observed=f"inserted={inserted}, duplicates={duplicates}, revisions={revisions}",
                    expected="inserted>0 or duplicates>0",
                    tier=Tier.SUPPORT,
                ),
            ),
            ctx.run_id,
            now,
        )

    metrics = {
        "inserted": float(inserted),
        "duplicates": float(duplicates),
        "revisions": float(revisions),
        "sources_ok": float(ok_count),
    }
    message = (
        f"collected {inserted} new, {duplicates} duplicate, {revisions} revised "
        f"across {ok_count} source(s)"
    )
    return StepResult(
        step_name="collect",
        status=StepStatus.OK,
        duration_s=0.0,
        message=message,
        metrics=metrics,
    )
