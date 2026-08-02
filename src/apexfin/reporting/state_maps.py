"""Centralised state-to-presentation maps for the dashboard.

The template must never decide, on its own, which icon or colour a state maps
to (ARCHITECTURE 9.1): the mapping lives here so it can be reviewed in one
place and so `reporting` does not have to import `quality` or `decision` to
render a verdict it already received as a string.

These are presentation facts, not business rules, so they belong in the
render layer next to the template they feed.
"""

from __future__ import annotations

# health/series state -> (label_zh, icon_id, tone)
STATE_PRESENTATION: dict[str, tuple[str, str, str]] = {
    "healthy": ("正常", "check-circle-2", "ok"),
    "degraded": ("降级", "alert-triangle", "warn"),
    "blocked": ("阻断", "x-octagon", "danger"),
    "unknown": ("未知", "circle-dashed", "muted"),
}

# gate verdict -> (verdict_label, icon_id, tone)
GATE_PRESENTATION: dict[str, tuple[str, str, str]] = {
    "PASS": ("通过", "check-circle-2", "ok"),
    "DEGRADED": ("降级", "alert-triangle", "warn"),
    "BLOCKED": ("阻断", "x-octagon", "danger"),
}

# step status -> (status_label, icon_id)
STATUS_PRESENTATION: dict[str, tuple[str, str]] = {
    "ok": ("成功", "check-circle-2"),
    "running": ("运行中", "loader"),
    "skipped": ("跳过", "circle-dashed"),
    "failed": ("失败", "x-octagon"),
}

# The six quality checks, in display order. `key` is the matrix cell key;
# `check_id` is the registered check id that produces findings for it.
CHECK_DEFS: list[dict[str, str]] = [
    {"key": "fresh", "label_zh": "新鲜度", "label_en": "FRESH", "check_id": "freshness"},
    {"key": "compl", "label_zh": "完整性", "label_en": "COMPL", "check_id": "completeness"},
    {"key": "dup", "label_zh": "重复性", "label_en": "DUP", "check_id": "duplicates"},
    {"key": "consist", "label_zh": "一致性", "label_en": "CONSIST", "check_id": "consistency"},
    {"key": "contin", "label_zh": "连续性", "label_en": "CONTIN", "check_id": "continuity"},
    {"key": "range", "label_zh": "合理性", "label_en": "RANGE", "check_id": "range"},
]

CHECK_KEY_BY_ID: dict[str, str] = {c["check_id"]: c["key"] for c in CHECK_DEFS}
