"""Error tree. Every error carries the CLI exit code it maps to.

Rationale: the exit code is part of the CLI contract, so it belongs to the
error that causes it, not to a translation table in the command layer that
someone will forget to update.
"""

from __future__ import annotations

from apexfin.core.enums import ExitCode


class ApexfinError(Exception):
    """Base of every error this project raises on purpose."""

    exit_code: int = ExitCode.RUNTIME_ERROR


class ConfigError(ApexfinError):
    """Missing or malformed configuration, or a secret in the wrong place."""

    exit_code = ExitCode.CONFIG_ERROR


class MigrationError(ConfigError):
    """Applied migration checksum no longer matches the file on disk."""


class CalendarRangeError(ApexfinError):
    """A date falls outside the years the trading calendar can vouch for.

    Deliberately an error and not a guess: an unbacked calendar answer would
    silently corrupt every freshness verdict downstream.
    """

    exit_code = ExitCode.CONFIG_ERROR


class QualityBlockedError(ApexfinError):
    """The quality gate blocked the run; downstream steps must not proceed."""

    exit_code = ExitCode.QUALITY_BLOCKED


class SourceError(ApexfinError):
    """Base for collector failures. One failing source never aborts a run."""

    exit_code = ExitCode.SOURCE_UNAVAILABLE


class CollectorError(SourceError):
    """Transport or parse failure inside a collector."""


class EmptyResultError(SourceError):
    """A collector returned zero records.

    Treated as failure, never as a successful no-op: the base class cannot
    distinguish 'genuinely no data' from 'silently broken', and guessing the
    friendly interpretation is exactly how silent data rot starts.
    """


class SourceBlockedError(SourceError):
    """Upstream returned an access-control signal (429/403).

    Not retryable, not routable around. Backoff applies to transient network
    faults only -- see ARCHITECTURE 8.2 C4 and ADR-009.
    """


class AllSourcesFailedError(SourceError):
    """Every configured source failed. Only this maps to exit code 5."""


class ManifestError(ApexfinError):
    """Manifest failed one of the four consistency assertions."""

    exit_code = ExitCode.MANIFEST_INVALID


class ExtractorNotFound(ApexfinError):
    """No extractor registered for a source seen in bronze.

    Raised rather than skipped: skipping would leave bronze rows that never
    become silver, and nothing would ever report it.
    """


class RegistryConflict(ApexfinError):
    """A plugin tried to shadow a builtin registration."""
