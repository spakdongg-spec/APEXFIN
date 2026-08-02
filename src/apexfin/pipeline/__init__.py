"""Pipeline orchestration (L4).

`pipeline` may depend on {core, storage, L3}. It owns the daily-chain
definition (the `@step` registry), the topological planner, the four-way
manifest assertion, and the runner that executes steps each inside its own
SAVEPOINT. It deliberately does not import `reporting`: the `render` step is
registered by the composition root (`cli`) so that the only module that has to
see both `reporting` and the step registry is `cli`.
"""

from apexfin.pipeline.context import RunContext
from apexfin.pipeline.registry import Step, all_steps, step

__all__ = ["RunContext", "Step", "all_steps", "step"]
