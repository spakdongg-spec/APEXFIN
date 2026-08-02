"""A deliberately small JSON Schema subset validator.

Why not `jsonschema`: the runtime dependency budget is 10 packages and eight
are spent (ARCHITECTURE 4.2). Config validation is worth having, a ninth
dependency for it is not.

Supported keywords: ``type``, ``const``, ``enum``, ``required``,
``properties``, ``additionalProperties: false``, ``items``, ``minItems``,
``uniqueItems``, ``minLength``, ``pattern``, ``minimum``, ``maximum``,
``$ref`` into ``#/$defs/...``, ``allOf``, and ``if``/``then``.

Everything else in a schema file is ignored on purpose. The limits are stated
rather than hidden so nobody assumes a `format` or `dependentRequired` keyword
is being enforced when it is not. Unsupported keywords never fail silently in
a way that matters: they simply do not constrain, and the three contract files
in `contracts/` were written against this subset.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def load_schema(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def validate(instance: Any, schema: dict[str, Any], *, origin: str = "<data>") -> list[str]:
    """Return a list of human-readable violations. Empty means valid."""
    errors: list[str] = []
    _check(instance, schema, schema, origin, errors)
    return errors


def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    cursor: Any = root
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(cursor, dict) or part not in cursor:
            return {}
        cursor = cursor[part]
    return cursor if isinstance(cursor, dict) else {}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    target = _TYPES.get(expected)
    return target is not None and isinstance(value, target)


def _check(value: Any, node: dict[str, Any], root: dict[str, Any], at: str, out: list[str]) -> None:
    node = _resolve(node, root)
    if not node:
        return

    expected = node.get("type")
    if isinstance(expected, str) and not _type_ok(value, expected):
        out.append(f"{at}: expected type {expected}, got {type(value).__name__}")
        return

    if "const" in node and value != node["const"]:
        out.append(f"{at}: expected the constant {node['const']!r}, got {value!r}")
    if "enum" in node and value not in node["enum"]:
        out.append(f"{at}: {value!r} is not one of {node['enum']}")

    if isinstance(value, str):
        _check_string(value, node, at, out)
    if isinstance(value, int | float) and not isinstance(value, bool):
        _check_number(value, node, at, out)
    if isinstance(value, list):
        _check_array(value, node, root, at, out)
    if isinstance(value, dict):
        _check_object(value, node, root, at, out)

    for index, sub in enumerate(node.get("allOf", [])):
        _check_conditional(value, sub, root, f"{at}/allOf[{index}]", out)


def _check_conditional(
    value: Any, sub: dict[str, Any], root: dict[str, Any], at: str, out: list[str]
) -> None:
    if "if" in sub:
        if not validate(
            value,
            {**_resolve(sub["if"], root), "$defs": root.get("$defs", {})},
            origin=at,
        ):
            _check(value, sub.get("then", {}), root, at, out)
        return
    _check(value, sub, root, at, out)


def _check_string(value: str, node: dict[str, Any], at: str, out: list[str]) -> None:
    minimum = node.get("minLength")
    if isinstance(minimum, int) and len(value) < minimum:
        out.append(f"{at}: needs at least {minimum} characters, got {len(value)}")
    pattern = node.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, value) is None:
        out.append(f"{at}: {value!r} does not match {pattern}")


def _check_number(value: float, node: dict[str, Any], at: str, out: list[str]) -> None:
    low = node.get("minimum")
    if isinstance(low, int | float) and value < low:
        out.append(f"{at}: {value} is below the minimum {low}")
    high = node.get("maximum")
    if isinstance(high, int | float) and value > high:
        out.append(f"{at}: {value} is above the maximum {high}")


def _check_array(
    value: list[Any], node: dict[str, Any], root: dict[str, Any], at: str, out: list[str]
) -> None:
    minimum = node.get("minItems")
    if isinstance(minimum, int) and len(value) < minimum:
        out.append(f"{at}: needs at least {minimum} items, got {len(value)}")
    if node.get("uniqueItems") is True:
        seen = [json.dumps(item, sort_keys=True, default=str) for item in value]
        if len(set(seen)) != len(seen):
            out.append(f"{at}: items must be unique")
    item_schema = node.get("items")
    if isinstance(item_schema, dict):
        for index, item in enumerate(value):
            _check(item, item_schema, root, f"{at}[{index}]", out)


def _check_object(
    value: dict[str, Any], node: dict[str, Any], root: dict[str, Any], at: str, out: list[str]
) -> None:
    properties = node.get("properties", {})
    for name in node.get("required", []):
        if name not in value:
            out.append(f"{at}: missing required property '{name}'")
    if node.get("additionalProperties") is False:
        for key in value:
            if key not in properties:
                out.append(f"{at}: unknown property '{key}'")
    if isinstance(properties, dict):
        for key, sub in properties.items():
            if key in value and isinstance(sub, dict):
                _check(value[key], sub, root, f"{at}.{key}", out)
