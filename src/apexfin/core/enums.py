"""Enumerations shared across every layer.

The string values are contract surface: they land in SQLite CHECK constraints
(DATA_CONTRACT), in the `--json` CLI envelope (CLI_CONTRACT) and in the
dashboard `data-*` attributes (DESIGN 2.5). Renaming a value breaks all three.
"""

from __future__ import annotations

from enum import StrEnum


class Tier(StrEnum):
    """Governance tier of a source or pipeline step (ARCHITECTURE 5.2)."""

    RISK_ESSENTIAL = "risk_essential"
    SUPPORT = "support"
    DISPLAY_ONLY = "display_only"
    RESEARCH = "research"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class GateVerdict(StrEnum):
    PASS = "PASS"  # noqa: S105 - gate verdict label, not a credential
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class StepStatus(StrEnum):
    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RunState(StrEnum):
    RUNNING = "RUNNING"
    PASS = "PASS"  # noqa: S105 - run state label, not a credential
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class HealthState(StrEnum):
    """`series_health.state`. Four values, four distinct icon outlines."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class Frequency(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class Outcome(StrEnum):
    HIT = "hit"
    MISS = "miss"
    VOID = "void"
    PENDING = "pending"


# Stance -> (direction token for the UI, Chinese label).
# Shared so `decision` and `reporting` can both render a stance without one
# importing the other (ARCHITECTURE 7.3: L5 may import L3, but L3 must not
# cross-import, and reporting is constrained to {core, storage}).
STANCE_PRESENTATION: dict[str, tuple[str, str]] = {
    "long": ("up", "看多"),
    "short": ("down", "看空"),
    "flat": ("flat", "中性"),
    "no_call": ("flat", "无观点"),
}


class ExitCode:
    """CLI exit codes (CLI_CONTRACT 二). CI depends on these numbers."""

    OK = 0
    RUNTIME_ERROR = 1
    USAGE_ERROR = 2
    CONFIG_ERROR = 3
    QUALITY_BLOCKED = 4
    SOURCE_UNAVAILABLE = 5
    MANIFEST_INVALID = 6
