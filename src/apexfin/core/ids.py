"""Run identifiers.

Format `YYYYMMDDThhmmssZ-<4 hex>`: sortable by time, unique enough for a
single-node CLI, and readable in a log line without decoding.
"""

from __future__ import annotations

import secrets
from datetime import datetime


def new_run_id(now: datetime) -> str:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"
