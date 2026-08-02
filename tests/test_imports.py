"""Every module in the package must import. This test exists because it caught
things nothing else did.

`pkgutil.walk_packages` is used deliberately but not naively: with the default
`onerror`, an `ImportError` raised inside a sub-package's `__init__.py` is
*silently swallowed* and the entire subtree below it is skipped. A run that
reports "47 modules OK" while quietly never visiting `reporting/*` is worse
than no test at all, so this module collects errors through an explicit
`onerror` hook and asserts the discovered module count never falls.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import apexfin

#: Raise this when modules are added. It only exists to make the "walk_packages
#: silently skipped a subtree" failure mode impossible to miss: a refactor that
#: breaks a package `__init__` shows up as a count drop, not as a green run.
MINIMUM_MODULES = 45


def _walk() -> tuple[list[str], list[tuple[str, str]]]:
    """Import every `apexfin.*` module. Returns (imported, failures)."""
    walk_errors: list[tuple[str, str]] = []

    def on_error(name: str) -> None:
        # walk_packages calls this instead of propagating; without it the
        # failing package's whole subtree disappears from the walk.
        import sys
        import traceback

        exc = sys.exc_info()[1]
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        walk_errors.append((name, detail))

    imported: list[str] = []
    failures: list[tuple[str, str]] = []
    for info in pkgutil.walk_packages(apexfin.__path__, "apexfin.", onerror=on_error):
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 - the point is to report all of them
            failures.append((info.name, f"{type(exc).__name__}: {exc}"))
        else:
            imported.append(info.name)

    seen = {name for name, _ in failures}
    failures.extend((n, d) for n, d in walk_errors if n not in seen)
    return imported, failures


def test_every_module_imports() -> None:
    imported, failures = _walk()
    if failures:
        report = "\n".join(f"  {name}\n      {detail}" for name, detail in failures)
        pytest.fail(f"{len(failures)} module(s) failed to import:\n{report}")
    assert imported, "walk_packages discovered no modules at all"


def test_module_count_does_not_regress() -> None:
    """A subtree that vanishes from the walk is a silent failure. Catch it."""
    imported, _ = _walk()
    assert len(imported) >= MINIMUM_MODULES, (
        f"only {len(imported)} modules were discovered, expected at least "
        f"{MINIMUM_MODULES}. A package `__init__` that raises makes "
        f"walk_packages skip its whole subtree. Discovered: {sorted(imported)}"
    )
