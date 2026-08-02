"""Topological planner for the daily chain.

Execution order is derived by topological sort; manual ordering is not
supported by design (ARCHITECTURE 5.2). `--only` / `--skip` prune the graph
but dependency integrity is preserved: pruning a step whose dependents remain
is an error, not a silent empty run.
"""

from __future__ import annotations

from apexfin.core.errors import ManifestError
from apexfin.pipeline.registry import Step, all_steps


def plan(
    *,
    keep_daily: bool = True,
    only: tuple[str, ...] = (),
    skip: tuple[str, ...] = (),
) -> list[Step]:
    """Select and topologically order the steps to execute."""
    steps = all_steps()
    selected: dict[str, Step] = {}
    for name, step in steps.items():
        if keep_daily and not step.keep_daily:
            continue
        if only and name not in only:
            continue
        if name in skip:
            continue
        selected[name] = step

    for name, step in selected.items():
        for dep in step.depends_on:
            if dep not in selected:
                raise ManifestError(
                    f"step '{name}' depends on '{dep}' which is not in the plan "
                    f"(skipped or filtered). Resolve upstream first."
                )

    return _toposort(selected)


def _toposort(steps: dict[str, Step]) -> list[Step]:
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(steps, white)
    order: list[Step] = []

    def visit(node: str) -> None:
        color[node] = gray
        for dep in steps[node].depends_on:
            if dep not in steps:
                continue
            if color[dep] == gray:
                raise ManifestError(f"dependency cycle detected at '{dep}'")
            if color[dep] == white:
                visit(dep)
        color[node] = black
        order.append(steps[node])

    for node in steps:
        if color[node] == white:
            visit(node)
    return order
