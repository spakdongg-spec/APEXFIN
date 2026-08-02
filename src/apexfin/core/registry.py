"""Decorator registries plus third-party entry-point discovery (INTERFACES 十一).

Name collisions resolve in favour of the builtin and are recorded, never
silently overwritten: a plugin quietly replacing the Yahoo collector would be
undetectable from the outside, which is the whole problem this project is about.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, TypeVar

REGISTRY_GROUPS = ("apexfin.sources", "apexfin.checks", "apexfin.strategies")

T = TypeVar("T")

_SOURCES: dict[str, Any] = {}
_CHECKS: dict[str, Any] = {}
_STRATEGIES: dict[str, Any] = {}
_BUILTIN_NAMES: dict[str, set[str]] = {"sources": set(), "checks": set(), "strategies": set()}


@dataclass(frozen=True)
class PluginEntry:
    group: str
    name: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    origin: str
    reason: str | None = None


@dataclass
class PluginReport:
    entries: list[PluginEntry] = field(default_factory=list)

    @property
    def failures(self) -> list[PluginEntry]:
        return [e for e in self.entries if e.status == "FAIL"]


def _make_registrar(
    table: dict[str, Any], kind: str
) -> Callable[[str], Callable[[type[T]], type[T]]]:
    def register(name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            table[name] = cls
            _BUILTIN_NAMES[kind].add(name)
            return cls

        return decorator

    return register


register_source = _make_registrar(_SOURCES, "sources")
register_check = _make_registrar(_CHECKS, "checks")
register_strategy = _make_registrar(_STRATEGIES, "strategies")


def get_source(name: str) -> Any | None:
    return _SOURCES.get(name)


def all_sources() -> dict[str, Any]:
    return dict(_SOURCES)


def all_checks() -> dict[str, Any]:
    return dict(_CHECKS)


def all_strategies() -> dict[str, Any]:
    return dict(_STRATEGIES)


def _table_for(group: str) -> tuple[dict[str, Any], str]:
    kind = group.rsplit(".", 1)[-1]
    return {"sources": _SOURCES, "checks": _CHECKS, "strategies": _STRATEGIES}[kind], kind


def discover_plugins() -> PluginReport:
    """Load third-party registrations. Failures are reported, never swallowed."""
    report = PluginReport()
    for group in REGISTRY_GROUPS:
        table, kind = _table_for(group)
        try:
            found = entry_points(group=group)
        except (TypeError, OSError) as exc:  # pragma: no cover - stdlib edge
            report.entries.append(PluginEntry(group, "*", "FAIL", "importlib", str(exc)))
            continue
        for ep in found:
            origin = getattr(ep, "value", ep.name)
            if ep.name in _BUILTIN_NAMES[kind]:
                report.entries.append(
                    PluginEntry(group, ep.name, "SKIP", origin, "shadowed by builtin")
                )
                continue
            try:
                table[ep.name] = ep.load()
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                report.entries.append(PluginEntry(group, ep.name, "FAIL", origin, repr(exc)))
            else:
                report.entries.append(PluginEntry(group, ep.name, "PASS", origin))
    return report


def builtin_entries() -> list[PluginEntry]:
    out: list[PluginEntry] = []
    for group in REGISTRY_GROUPS:
        _, kind = _table_for(group)
        out.extend(
            PluginEntry(group, name, "PASS", "builtin") for name in sorted(_BUILTIN_NAMES[kind])
        )
    return out
