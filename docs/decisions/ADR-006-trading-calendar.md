# ADR-006: 自建 YAML 驱动的轻量交易日历

## Status

Accepted (2026-08-02) — 高见远

## Background

PRD 竞品分析给出的第一个真实空白是「数据新鲜的定义空白」：编排器看任务时间，dbt `source freshness` 看写入时间，没有工具看**业务时间**。APEXFIN 的核心差异化就是按**交易日**计算滞后——周一早晨检查上周五的数据不能误报（PRD 九·边界条件）。

这要求一个交易日历。候选：`exchange_calendars`、`pandas_market_calendars`、`holidays` 包、自建 YAML 日历、只用周末规则。

## Decision

自建 **`TradingCalendar` 协议 + `YamlTradingCalendar` 实现**：周末规则 + `config/calendars/nyse.yaml` 假日表。

| 候选 | 依赖代价 | 覆盖度 | 判定 |
|------|---------|-------|------|
| exchange_calendars | 依赖 pandas + numpy | 全球 50+ 交易所，含半日市 | 落选：与 ADR-008 直接冲突 |
| pandas_market_calendars | 依赖 pandas | 主要交易所 | 落选：同上 |
| holidays 包 | 轻量（无 pandas） | 各国法定假日，**非交易日历** | 落选：法定假日 ≠ 交易日历（NYSE 有自己的休市规则，如国葬临时休市） |
| 只用周末规则 | 0 | 完全不含假日 | 落选：7 月 4 日、感恩节这类会直接产生误报，砸的正是本项目的招牌 |
| 自建 YAML 日历 | 0 | 覆盖 NYSE 全休市日，需人工年更 | **选定** |

排除前两者的根本原因是 ADR-008：它们都强制拉入 pandas，而 pandas 一个包就吃掉「≤10 顶层依赖 + 5 分钟上手」预算的大半。为一个约 250 行就能自建的能力付出 60 MB 依赖，不成立。

实现约束（都指向「不猜」）：
- `trading_days_between(start, end)` 统计半开区间 `(start, end]`，`end <= start` 时返回 0。
- 查询日期超出假日表覆盖年份 -> `raise CalendarRangeError`，**不外推、不降级为周末规则**。猜出来的日历会产生看似正常的错误结论，正是本项目最反对的失效模式。
- 假日表在 YAML 中，任何人可提 PR 更新，不需要改代码。
- `TradingCalendar` 是 Protocol，需要其他交易所的使用者实现自己的版本注入即可。
- 该模块用 hypothesis 做属性测试（单调性、自反性、区间可加性）——日历是沉默逻辑错误的高发区。

## Consequences

正面：
- 零依赖，与依赖预算和 5 分钟指标一致。
- 超范围直接报错，杜绝「悄悄用错日历算出错误滞后」这类最危险的情况。
- 日历数据与代码分离，年度更新是数据 PR 而非代码 PR，社区可低成本贡献。

负面：
- **只覆盖 NYSE / 美国联邦假日，且假日表需人工年更。** 这是真实局限，必须在 README 与 `core/calendar.py` docstring 中诚实标注，不能含糊。
- 不处理半日休市（感恩节次日、平安夜提前收市）。对日频数据的滞后判定无影响，但需在文档中写明这个已知简化。
- 临时休市（如国葬）需要手工补进 YAML。缓解：`apexfin doctor` 会报告日历覆盖年份范围，提醒用户检查。

## Related ADRs

ADR-008（不引入 pandas 是本决策的直接约束来源）、ADR-002（`event_date` 单列存储正是为了让日历比对能命中索引）
