"""The DataPack schema, expressed as pydantic models.

The dashboard template does no computation (ARCHITECTURE 9.3), which means the
contract between backend and frontend is the *shape of this object* and nothing
else. A dict literal cannot be that contract: a renamed key or a stringified
number ships silently and breaks a panel in the browser, three steps away from
the code that caused it.

Every model is frozen with `extra="forbid"`, so an unexpected key fails here
rather than being ignored by the template. `tools/export_schemas.py` dumps
`DataPack.model_json_schema()` to `contracts/datapack.schema.json`, and CI
validates `tests/fixtures/sample_datapack.json` against it -- the fixture the
frontend was built from is therefore a test of this schema, not a parallel
truth that can drift away from it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_FROZEN = ConfigDict(frozen=True, extra="forbid")

#: Colour intent. Only these four exist; the template maps them to CSS.
Tone = Literal["ok", "warn", "danger", "muted"]

#: Series/source health. `unknown` is a real state, not a missing value: it
#: means "never collected", which is different from "collected and fine".
StateName = Literal["healthy", "degraded", "blocked", "unknown"]

#: Step lifecycle as the dashboard shows it (lower case; the DB stores upper).
StatusName = Literal["ok", "running", "skipped", "failed"]

#: Visual direction of a decision. `no_call` also renders `flat` -- the arrow
#: has nowhere else to point -- and is distinguished by `direction_label`.
DirectionName = Literal["up", "down", "flat"]


class SourceChip(BaseModel):
    """One source pill in the gate banner."""

    model_config = _FROZEN

    source_name: str
    state: StateName
    label_text: str
    icon_id: str
    tone: Tone


class GateBlock(BaseModel):
    """The verdict banner: the first thing a reader sees and the only thing
    that tells them whether to trust the rest of the page."""

    model_config = _FROZEN

    verdict: Literal["PASS", "DEGRADED", "BLOCKED"]
    verdict_label: str
    icon_id: str
    tone: Tone
    summary: str
    sources: list[SourceChip] = Field(default_factory=list)


class CheckDef(BaseModel):
    """A column header of the quality matrix.

    Deliberately without `check_id`: the matrix is presentation, and leaking
    the registered check id into the page would invite the frontend to build
    logic on it.
    """

    model_config = _FROZEN

    key: str
    label_zh: str
    label_en: str


class MatrixCell(BaseModel):
    model_config = _FROZEN

    state: StateName
    cell_value: str
    icon_id: str
    cell_tooltip: str


class MatrixRow(BaseModel):
    model_config = _FROZEN

    source_name: str
    cells: dict[str, MatrixCell]
    pass_count: int = Field(ge=0)
    total: int = Field(gt=0)
    rate: float = Field(ge=0.0, le=1.0)
    rate_state: Literal["ok", "warn"]


class QualityMatrix(BaseModel):
    model_config = _FROZEN

    checks: list[CheckDef]
    rows: list[MatrixRow] = Field(default_factory=list)


class Freshness(BaseModel):
    """Pre-computed progress bar. The template must not divide.

    `bar_value` is clamped to `bar_max` so an eight-day-late series does not
    render an eight-times-oversized bar; `overdue` carries the fact that the
    clamp happened, so the visual truth is not lost.
    """

    model_config = _FROZEN

    bar_value: int = Field(ge=0)
    bar_max: int = Field(gt=0)
    overdue: bool
    label: str


class HealthRow(BaseModel):
    """One (source, symbol) row of the freshness table.

    `lag_trading_days` is `None` only when the series has never been seen. It
    is never 0 in that case -- zero would read as "perfectly fresh".
    """

    model_config = _FROZEN

    source_name: str
    symbol: str
    state: StateName
    label_text: str
    icon_id: str
    tone: Tone
    lag_trading_days: int | None
    max_lag_trading_days: int = Field(gt=0)
    freshness: Freshness | None
    last_event_date: str | None
    last_event_label: str | None
    note: str | None


class StepRow(BaseModel):
    """One row of the run timeline.

    `duration_s` and `duration_label` are both nullable because a running step
    has no duration yet, and printing `0.0 秒` for it would be a lie.
    """

    model_config = _FROZEN

    step_name: str
    tier: str
    tier_state: Literal["ok", "warn"]
    status: StatusName
    status_label: str
    icon_id: str
    duration_s: float | None
    duration_label: str | None
    ran_at: str | None
    note: str | None


class DecisionRow(BaseModel):
    model_config = _FROZEN

    decision_id: str
    symbol: str
    direction: DirectionName
    direction_label: str
    rationale: str
    score: float = Field(ge=0.0, le=1.0)
    as_of: str
    #: Per-strategy breakdown of the aggregate; the visible analysis chain.
    signals: list[SignalDetail] = Field(default_factory=list)


class SignalDetail(BaseModel):
    """One strategy's contribution to a decision, as rendered on the board."""

    model_config = _FROZEN

    strategy: str
    direction: Literal["long", "short", "flat"]
    strength: float = Field(ge=0.0, le=1.0)
    rationale: str


class Chart(BaseModel):
    """A chart plus the table that replaces it when JavaScript is unavailable.

    `fallback_rows` is not a nicety: a governance dashboard that shows nothing
    without a CDN is not a governance dashboard.
    """

    model_config = _FROZEN

    chart_id: str
    title: str
    kind: Literal["candlestick", "macro", "line"]
    icon_id: str
    option: dict[str, Any]
    fallback_columns: list[str]
    fallback_rows: list[list[str | float]]


class Notice(BaseModel):
    model_config = _FROZEN

    level: Literal["info", "warn", "danger"]
    icon_id: str
    text: str


class RunFooter(BaseModel):
    """Provenance line at the bottom of the page.

    `finished_at` is `None` when the run never finished -- a crash, a kill, a
    container eviction. In that case the labels say so instead of quietly
    substituting the render time and reporting a duration of zero.
    """

    model_config = _FROZEN

    finished_at: str | None
    finished_label: str
    duration_label: str


class DataPack(BaseModel):
    """Everything the dashboard renders, and nothing it has to compute."""

    model_config = _FROZEN

    generated_at: str
    run_id: str
    gate: GateBlock
    quality_matrix: QualityMatrix
    health_rows: list[HealthRow] = Field(default_factory=list)
    steps: list[StepRow] = Field(default_factory=list)
    decisions: list[DecisionRow] = Field(default_factory=list)
    charts: list[Chart] = Field(default_factory=list)
    notices: list[Notice] = Field(default_factory=list)
    run_footer: RunFooter
