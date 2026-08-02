"""structlog configuration.

Two hard rules encoded here:
  - logs go to stderr, always. `--json` puts a single JSON object on stdout and
    nothing else may contaminate it (CLI_CONTRACT 3.2).
  - no emoji in any renderer. Status is spelled `[PASS]` / `[FAIL]`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(level: str = "info", *, json_output: bool = False) -> None:
    numeric = _LEVELS.get(level.lower(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=numeric, force=True)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def bind_run(run_id: str) -> None:
    structlog.contextvars.bind_contextvars(run_id=run_id)


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
