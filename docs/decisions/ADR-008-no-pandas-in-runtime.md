# ADR-008: 运行时不引入 pandas / numpy

## Status

Accepted (2026-08-02) — 高见远

## Background

APEXDATA 的 `requirements.txt` 含 `pandas>=2.0`、`numpy>=1.24`、`polars>=0.20`。金融数据项目默认用 pandas 几乎是行业条件反射，把它带过来是阻力最小的路径。

但 PRD 给了两条互相咬合的硬指标：
- 核心运行时顶层依赖 ≤ 10（PRD 十四·给架构师）
- 从 `git clone` 到看到看板 < 5 分钟，含依赖安装（PRD 十·NFR、AC-1）；`make demo` 全链路 < 60 秒

## Decision

**核心运行时不引入 pandas、numpy、polars。** pandas 降级为可选 extra `apexfin[pandas]`，仅供使用者在自己的 `DataSource` / `BaseStrategy` 实现里按需使用，框架本身不 import。

论证：

1. **依赖预算**。pandas 3.0.5 安装体积在 60 MB 量级，并强制拉入 numpy、tzdata 等。单它一个就吃掉「≤10 顶层依赖」预算的显著份额与安装时间预算的大半。
2. **冷启动**。`import pandas` 在普通笔记本上耗时 0.6–1.2 秒。对 60 秒全链路预算，这是纯粹的浪费——尤其它被浪费在「什么都还没算」的阶段。
3. **必要性存疑**。MVP 的实际计算只有四类：拉 JSON、写 SQLite、按符号取最近 N 条算收益率、算滞后交易日。这些用标准库 `sqlite3` + `statistics` + 纯 Python 完全覆盖，且 SQLite 3.25+ 的窗口函数（`LAG`、`ROW_NUMBER`）能把序列计算下推到 SQL，比在 Python 侧构造 DataFrame 更直接。
4. **数据规模**。fixture 总量 < 1 MB，真实使用是日频数据，量级在千行到万行。这个规模下 DataFrame 的向量化优势不存在，反而多一层内存拷贝。
5. **可读性**。参考实现的读者要看懂的是「质量检查怎么判定」，不是「怎么用 pandas 写得优雅」。纯 Python 的循环在这个规模下更易读。

连带排除（这是本决策代价最大的部分）：
- `yfinance`（依赖 pandas）-> 自建约 180 行的 `sources/yahoo.py`
- `exchange_calendars` / `pandas_market_calendars`（依赖 pandas）-> 自建约 250 行的 YAML 日历（ADR-006）
- `pandera`（依赖 pandas）-> 用 pydantic + JSON Schema 做校验

自建成本合计约 430 行，已评估为可接受，且这些代码本身就是参考实现要展示的内容（「一个采集器该处理哪些边界」比「调用 yfinance 一行搞定」对读者更有价值）。

## Consequences

正面：
- 顶层运行时依赖控制在 8 个，留 2 个余量。
- 安装与冷启动都显著变快，直接服务两条硬指标。
- 无科学栈依赖冲突风险。PRD 竞品分析中明确记录 Qlib 曾因 LightGBM/pandas 版本问题破坏用户工作流——本项目从根上不暴露这个面。
- 纯标准库处理数据，与 ADR-002（裸 sqlite3）形成一致的技术取向，整个项目只有一种数据处理范式。

负面：
- **自建 Yahoo 采集器需要自己处理 JSON 解析、增量窗口、退避重试、空结果防护**，这些 yfinance 已经做过。缓解：这部分代码有独立单测与 fixture 回放测试；且 yfinance 本身的静默返回空 DataFrame 行为，正是 PRD 痛点 1 列举的问题源，自己实现反而能保证「空结果视为失败」这条关键语义。
- 若未来要做统计分析类功能，缺 pandas 会明显吃力。缓解：届时评估把该功能放进 optional extra，或明确划到 Out of Scope。
- 部分贡献者会觉得「不用 pandas 是自找麻烦」。缓解：本 ADR 即答复，README 的 FAQ 中引用。

## Related ADRs

ADR-001（依赖预算的另一半）、ADR-002（裸 sqlite3，同一取向）、ADR-006（自建日历是本决策的直接后果）
