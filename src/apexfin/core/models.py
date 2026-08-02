"""Core pydantic models (INTERFACES 一/二/四/六/七).

All models are frozen with `extra="forbid"`. Frozen because these objects
travel across layers and an in-place mutation three layers down is untraceable;
`extra="forbid"` because a typo in a field name must fail at the boundary, not
turn into a silently ignored attribute.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from apexfin.core.enums import Frequency, Severity, StepStatus, Tier

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class RawRecord(BaseModel):
    """One untouched unit fetched from an upstream source."""

    model_config = _FROZEN

    source_name: str
    domain: str
    symbol: str
    event_time: datetime
    payload: dict[str, Any]
    source_url: str | None = None


class BronzeRecord(BaseModel):
    model_config = _FROZEN

    id: int
    source_name: str
    domain: str
    symbol: str
    event_time: datetime
    event_date: date
    payload: dict[str, Any]
    payload_hash: str
    revision: int
    ingested_at: datetime


class SilverPoint(BaseModel):
    model_config = _FROZEN

    source_name: str
    domain: str
    symbol: str
    event_time: datetime
    event_date: date
    value: float
    value_secondary: float | None = None
    unit: str | None = None
    quality_score: float = Field(ge=0.0, le=1.0)
    is_filled: bool = False
    payload_json: dict[str, Any] | None = None
    bronze_id: int | None = None


class FetchWindow(BaseModel):
    """Closed interval the collector is asked to cover."""

    model_config = _FROZEN

    start: date
    end: date
    full_refresh: bool = False


class SourceCapabilities(BaseModel):
    model_config = _FROZEN

    source_name: str
    domain: str
    symbols: tuple[str, ...]
    frequency: Frequency
    requires_credentials: bool
    supports_full_refresh: bool
    min_request_interval_s: float = 0.0


class SeriesSpec(BaseModel):
    """One (source, symbol) series the pipeline is accountable for.

    `tier` is the symbol-level tier from `sources.yaml`, which overrides the
    source-level tier (contracts/sources.schema.json). It travels with the
    series so that a check never has to reach back into configuration to work
    out how severe its own finding is.
    """

    model_config = _FROZEN

    source_name: str
    symbol: str
    domain: str
    tier: Tier
    frequency: Frequency
    unit: str | None = None
    label: str | None = None


class CollectResult(BaseModel):
    model_config = _FROZEN

    source_name: str
    records: tuple[RawRecord, ...]
    ok: bool
    status: Literal["ok", "failed", "blocked"] = "ok"
    error: str | None = None
    requests_made: int = 0
    duration_s: float = 0.0


class UpsertStats(BaseModel):
    """Proof-of-progress returned by every bronze write.

    `inserted == duplicates == 0` means the write did nothing at all, which is
    reported as a finding rather than accepted as success (CLI_CONTRACT 四).
    """

    model_config = _FROZEN

    inserted: int = 0
    duplicates: int = 0
    revisions: int = 0

    @property
    def touched(self) -> int:
        return self.inserted + self.duplicates + self.revisions


class QualityFinding(BaseModel):
    model_config = _FROZEN

    check_id: str
    severity: Severity
    source_name: str
    symbol: str | None
    message: str
    observed: str | None = None
    expected: str | None = None
    tier: Tier


class SeriesHealth(BaseModel):
    """Snapshot row of `series_health`.

    `max_lag_trading_days` is the threshold captured at check time, not the
    current config value (DATA_CONTRACT 四). No hour-based fields exist here
    or anywhere else (O-07).
    """

    model_config = _FROZEN

    source_name: str
    symbol: str
    last_event_date: date | None
    lag_trading_days: int | None
    max_lag_trading_days: int
    state: str
    last_checked_at: datetime
    consecutive_fails: int = 0
    note: str | None = None


class StepResult(BaseModel):
    model_config = _FROZEN

    step_name: str
    status: StepStatus
    duration_s: float
    message: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class Signal(BaseModel):
    model_config = _FROZEN

    strategy: str
    symbol: str
    direction: Literal["long", "short", "flat"]
    strength: float = Field(ge=-1.0, le=1.0)
    as_of: date
    rationale: str
    inputs: dict[str, float] = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = _FROZEN

    run_id: str
    as_of: date
    symbol: str
    stance: Literal["long", "short", "flat", "no_call"]
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: str
    rationale: str
    inputs: dict[str, float] = Field(default_factory=dict)
    contributing_signals: tuple[str, ...] = ()
    degraded: bool = False


class LedgerEntry(BaseModel):
    model_config = _FROZEN

    decision_id: int
    symbol: str
    stated_on: date
    horizon_days: int
    due_on: date
    stance: str
    reference_value: float
    settled_on: date | None = None
    settled_value: float | None = None
    outcome: str = "pending"
    settled_note: str | None = None
