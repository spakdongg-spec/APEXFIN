"""Bull/bear debate engine -- port of APEXDATA's `debate_agent_synthesis.py`.

APEXDATA runs per-asset: N analyst roles each emit a direction + confidence,
the bull researcher consolidates the long evidence, the bear researcher the
short evidence, and a PM adjudicator weighs `confidence x role_weight` to emit
a single verdict: AFFIRM (bull dominates by >33pp), REJECT (bear dominates by
>33pp), or MODIFY (close). A rebuttal paragraph and risk notes round out the
output so the dashboard can show the disagreement, not just the verdict.

This module is pure: it takes `AnalystView` objects and returns a debate result.
The role weights mirror APEXDATA's priorities (options > cot > pa > macro >
factor > text > behavioral), scaled to the roles this skeleton ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apexfin.decision.analysts.contracts import AnalystView

#: Verdict margin (percentage points of weighted share) for AFFIRM / REJECT.
_ADJUDICATE_MARGIN = 0.33

#: Role weights mirroring APEXDATA's priority order, renormalised for the
#: roles this skeleton actually produces.
ROLE_WEIGHT: dict[str, float] = {
    "technical": 1.0,
    "macro": 0.9,
    "options": 0.8,
    "cot": 0.7,
    "text": 0.5,
    "behavioral": 0.4,
    "bull": 1.1,
    "bear": 1.1,
    "risk": 1.0,
}

ROLE_LABEL: dict[str, str] = {
    "technical": "技术面",
    "macro": "宏观流动性",
    "options": "期权/波动",
    "cot": "持仓博弈",
    "text": "叙事/文本",
    "behavioral": "行为金融",
    "bull": "多头研究员",
    "bear": "空头研究员",
    "risk": "风险压力测试",
}

_DIR_LABEL = {"long": "偏多", "short": "偏空", "flat": "中性", "neutral": "未覆盖"}


@dataclass(frozen=True)
class DebateResult:
    """The full debate output for one symbol (APEXDATA `analyze_asset` shape)."""

    symbol: str
    verdict_code: str  # AFFIRM | MODIFY | REJECT
    verdict_why: str
    conviction: float  # 0..1
    conviction_label: str  # 强 | 中 | 弱
    bull_case: str
    bear_case: str
    rebuttal: str
    risk_notes: str
    dimension_summary: str
    analyst_views: list[AnalystView] = field(default_factory=list)


def run_debate(views: list[AnalystView]) -> DebateResult:
    """Consolidate analyst views into a full bull/bear debate + verdict.

    Mirrors APEXDATA's `_consolidate` / `_build_rebuttal` / `_build_risk` /
    `_pm_adjudicate` pipeline.
    """
    available = [v for v in views if v.available]
    if not available:
        return DebateResult(
            symbol=views[0].symbol if views else "?",
            verdict_code="MODIFY",
            verdict_why="证据不足/全中性",
            conviction=0.0,
            conviction_label="弱",
            bull_case="（无任何可用分析师维度）",
            bear_case="（无任何可用分析师维度）",
            rebuttal="多空未形成实质分歧（无维度有证据），不假装中性。",
            risk_notes="未见极端风险信号；按辩论主导方向管理仓位，设置结构止损即可。",
            dimension_summary="无",
            analyst_views=views,
        )

    symbol = available[0].symbol
    bull_views = [v for v in available if v.direction == "long"]
    bear_views = [v for v in available if v.direction == "short"]

    bull_case = (
        _consolidate(bull_views)
        or "（无独立偏多源证据：当前各维度未给出偏多信号；主导方向由偏空维度驱动）"
    )
    bear_case = (
        _consolidate(bear_views)
        or "（无独立偏空源证据：当前各维度未给出偏空信号；主导方向由偏多维度驱动）"
    )

    verdict_code, bull_w, bear_w, why = _pm_adjudicate(available)
    rebuttal = _build_rebuttal(bull_views, bear_views)
    risk_notes = _build_risk(available)

    total = bull_w + bear_w
    conviction = abs(bull_w - bear_w) / total if total > 0 else 0.0
    conviction_label = (
        "强" if conviction > _ADJUDICATE_MARGIN else ("中" if conviction > 0.15 else "弱")
    )

    dimension_summary = "；".join(
        f"{ROLE_LABEL.get(v.role, v.role)}{_DIR_LABEL.get(v.direction, v.direction)}"
        for v in available
    )

    return DebateResult(
        symbol=symbol,
        verdict_code=verdict_code,
        verdict_why=why,
        conviction=round(conviction, 2),
        conviction_label=conviction_label,
        bull_case=bull_case,
        bear_case=bear_case,
        rebuttal=rebuttal,
        risk_notes=risk_notes,
        dimension_summary=dimension_summary,
        analyst_views=views,
    )


def _consolidate(views: list[AnalystView]) -> str | None:
    """Sort by confidence x weight and join the evidence sentences."""
    if not views:
        return None
    picks = sorted(views, key=lambda v: -v.confidence * ROLE_WEIGHT.get(v.role, 1.0))
    return "\n".join(str(v) for v in picks)


def _build_rebuttal(bull_views: list[AnalystView], bear_views: list[AnalystView]) -> str:
    """APEXDATA `_build_rebuttal`: acknowledge the other side's real weakness."""
    if not bull_views or not bear_views:
        dom = "多头" if bull_views else ("空头" if bear_views else "无")
        return (
            f"多空未形成实质分歧（仅 {dom} 维度有证据），按主导方向执行并设结构止损；"
            "缺失维度见各角色'未覆盖'标注，不假装中性。"
        )
    bn = "、".join(ROLE_LABEL.get(v.role, v.role) for v in bull_views)
    kn = "、".join(ROLE_LABEL.get(v.role, v.role) for v in bear_views)
    return (
        f"多头反驳：{bn} 论据占优，但 {kn} 指出真实的反向脆弱点——决策需对冲反向风险、勿满仓。\n"
        f"空头反驳：{kn} 论据成立，然 {bn} 提供实质支撑，单向重仓易被反向挤压。\n"
        "结论：论据存在真实分歧，按主导方执行但保留反向触发条件（见风险与关键位）。"
    )


def _build_risk(views: list[AnalystView]) -> str:
    """Collect risk-flavoured evidence (APEXDATA `_build_risk`)."""
    risk_keys = ("极端", "紧张", "压制", "偏离", "背离", "约束")
    risks: list[str] = []
    for v in views:
        for e in v.evidence:
            if any(k in e for k in risk_keys):
                risks.append(f"【{ROLE_LABEL.get(v.role, v.role)}】{e}")
    if not risks:
        risks.append("未见极端风险信号；按辩论主导方向管理仓位，设置结构止损即可。")
    return "；".join(risks[:5])


def _pm_adjudicate(views: list[AnalystView]) -> tuple[str, float, float, str]:
    """Weighted bull vs bear scoring; AFFIRM/MODIFY/REJECT at >33pp margin."""
    bull_w = sum(
        v.confidence / 100.0 * ROLE_WEIGHT.get(v.role, 1.0) for v in views if v.direction == "long"
    )
    bear_w = sum(
        v.confidence / 100.0 * ROLE_WEIGHT.get(v.role, 1.0) for v in views if v.direction == "short"
    )
    total = bull_w + bear_w
    if total <= 0:
        return "MODIFY", 0.0, 0.0, "证据不足/全中性"
    bs, ks = bull_w / total, bear_w / total
    if bs - ks > _ADJUDICATE_MARGIN:
        return "AFFIRM", bull_w, bear_w, f"多头论据占优({(bs * 100):.0f}% vs {(ks * 100):.0f}%)"
    if ks - bs > _ADJUDICATE_MARGIN:
        return "REJECT", bull_w, bear_w, f"空头论据占优({(ks * 100):.0f}% vs {(bs * 100):.0f}%)"
    return "MODIFY", bull_w, bear_w, f"多空论据接近(多{(bs * 100):.0f}% vs 空{(ks * 100):.0f}%)"
