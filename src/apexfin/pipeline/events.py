"""Structured step lifecycle events.

The runner is the only caller. Events exist so the log stream is
machine-parseable without scraping prose -- the same stream feeds `doctor`
and any future observability hook.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger("apexfin.pipeline")


def log_step_started(name: str, tier: str) -> None:
    log.info("step.started", step=name, tier=tier)


def log_step_finished(name: str, status: object, duration_s: float) -> None:
    log.info("step.finished", step=name, status=str(status), duration_s=duration_s)
