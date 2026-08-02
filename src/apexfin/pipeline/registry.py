"""Step registry backing the `@step` decorator (INTERFACES 六).

The decorator records each step's metadata in a module-level table. The
manifest validator reads this table to enforce the four-way consistency
between code and `pipeline_manifest.yaml` (ARCHITECTURE 5.2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ParamSpec

from apexfin.core.enums import Tier
from apexfin.core.models import StepResult
from apexfin.pipeline.context import RunContext

# A step may declare extra keyword-only parameters beyond ``ctx`` (e.g.
# ``collect_step(sources=..., symbols=...)``); the runner always calls it with
# just ``ctx`` and callers pre-bind extras via ``functools.partial``. The
# decorator preserves the full signature (ParamSpec) so mypy can still type
# check those pre-bound calls instead of erasing them to ``Callable[[RunContext], ...]``.
_P = ParamSpec("_P")

StepFn = Callable[[RunContext], StepResult]


@dataclass(frozen=True)
class Step:
    """A registered pipeline step and its declared metadata."""

    name: str
    tier: Tier
    depends_on: tuple[str, ...]
    critical: bool
    timeout_s: int
    keep_daily: bool
    why: str
    fn: Callable[..., StepResult]


_STEPS: dict[str, Step] = {}


def step(
    name: str,
    tier: Tier,
    *,
    depends_on: tuple[str, ...] = (),
    critical: bool = False,
    timeout_s: int = 120,
    keep_daily: bool = True,
    why: str = "",
) -> Callable[[Callable[_P, StepResult]], Callable[_P, StepResult]]:
    """Register a pipeline step. The wrapped function takes a RunContext."""

    def decorator(fn: Callable[_P, StepResult]) -> Callable[_P, StepResult]:
        if name in _STEPS:
            raise ValueError(f"duplicate step registration: {name}")
        _STEPS[name] = Step(
            name=name,
            tier=tier,
            depends_on=tuple(depends_on),
            critical=critical,
            timeout_s=timeout_s,
            keep_daily=keep_daily,
            why=why,
            fn=fn,
        )
        return fn

    return decorator


def all_steps() -> dict[str, Step]:
    """All registered steps. Names are the manifest's source of truth."""
    return dict(_STEPS)
