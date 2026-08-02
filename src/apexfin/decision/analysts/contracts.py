"""Analyst role contracts (port from APEXDATA debate engine, interface shape only).

APEXDATA ships an 8-role analyst framework whose outputs feed a bull/bear
debate and a PM adjudication. The role *shape* is what this skeleton copies:
each analyst emits a direction, a confidence, evidence sentences and a note;
downstream consumers (bull/bear consolidation, PM adjudication, the dashboard)
only depend on that shape. Real data sources are the fork's job -- this project
ships a fixture-driven reference implementation.

Direction values are ``"long"``/``"short"``/``"flat"`` (tradeable stance) and
``"neutral"`` (no stance; used by roles that read inputs rather than targets).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

Direction = str  # "long" | "short" | "flat" | "neutral"


@dataclass(frozen=True)
class AnalystView:
    """One analyst's verdict on one symbol. Mirrors APEXDATA's analyst dict."""

    role: str  # technical | macro | options | cot | text | behavioral | bull | bear | risk
    symbol: str
    direction: Direction
    confidence: float  # 0..100, APEXDATA convention
    evidence: list[str] = field(default_factory=list)
    note: str = ""
    available: bool = True
    as_of: date | None = None

    def __str__(self) -> str:
        """Renderable one-liner: `【角色 @conf】证据句` (APEXDATA _role_block shape)."""
        body = "；".join(self.evidence) if self.evidence else (self.note or "无具体证据")
        return f"【{self.role} @{self.confidence:.0f}】{body}"
