"""CLI shared state, populated by the global-option callback (CLI_CONTRACT 一)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CliState:
    """Global options resolved by `apexfin`'s top-level callback.

    `db`/`config_dir` stay `None` when the flag was not given so the caller can
    fall back to `APEXFIN_*` environment variables and code defaults, in that
    order (CLI_CONTRACT 一: config precedence).
    """

    root: Path
    db: Path | None = None
    config_dir: Path | None = None
    log_level: str = "info"
    json_output: bool = False
    as_of: str | None = None
    dry_run: bool = False
