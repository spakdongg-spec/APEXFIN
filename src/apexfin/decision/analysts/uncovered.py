"""Data-source analyst roles -- interface shape only (APEXDATA port).

APEXDATA's options / COT / text / behavioral roles each read a dedicated data
source (option chain, CFTC positioning, news narrative, behavioural signals)
that this skeleton does not ship -- and, being a forkable reference, should not
fabricate. The *role contract* is what is ported: when the data is absent the
analyst reports `available=False` with an explicit "未覆盖" note, so the debate
engine and dashboard can show which dimensions were actually covered instead of
pretending neutrality. Forkers wire their own collectors in and the same shape
works unchanged.

Reference implementation, not investment advice.
"""

from __future__ import annotations

from datetime import date

from apexfin.decision.analysts.contracts import AnalystView


def _unavailable(role: str, symbol: str, note: str, as_of: date | None) -> AnalystView:
    return AnalystView(
        role=role,
        symbol=symbol,
        direction="neutral",
        confidence=0.0,
        available=False,
        note=note,
        as_of=as_of,
    )


def analyze_options(symbol: str, as_of: date | None) -> AnalystView:
    """Option-chain smart-money read. Needs a real option data source."""
    return _unavailable(
        "options",
        symbol,
        "期权链数据未接入（接口形状：需要交易商/投机者头寸方向源）",
        as_of,
    )


def analyze_cot(symbol: str, as_of: date | None) -> AnalystView:
    """CFTC positioning crowding read. Needs a COT data source."""
    return _unavailable(
        "cot",
        symbol,
        "CFTC 持仓数据未接入（接口形状：需要机构/CTA/交易商拥挤度源）",
        as_of,
    )


def analyze_text(symbol: str, as_of: date | None) -> AnalystView:
    """News-narrative direction read. Needs a news factor source."""
    return _unavailable(
        "text",
        symbol,
        "新闻叙事数据未接入（接口形状：需要叙事方向/分裂度源）",
        as_of,
    )


def analyze_behavioral(symbol: str, as_of: date | None) -> AnalystView:
    """Behavioural signal read (fear/greed, positioning extremes)."""
    return _unavailable(
        "behavioral",
        symbol,
        "行为金融数据未接入（接口形状：需要恐慌/贪婪与极端仓位源）",
        as_of,
    )
