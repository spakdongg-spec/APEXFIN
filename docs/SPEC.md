# Spec - APEXFIN v0.1.0

> 生成日期：2026-08-02
> 基于：PRD v1 + 架构文档 v1 + UIUX 文档 v1
> 状态：已确认（用户 2026-08-02 确认三文档 + O-01）

---

## 1. 产品定义
- **一句话描述**：APEXFIN 是从 APEXDATA 抽取的可 fork 金融数据工程参考实现骨架——Medallion 分层 + 五层架构 + fail-loud 质量门 + 静态 HTML 看板，离线 fixture 即可跑通端到端。
- **目标用户**：想自建数据管线的量化研究者 / 开源学习者 / 需要可审计数据工程的团队。
- **核心问题**：数据管线容易"看起来在跑、实则已腐化"；本项目用治理层 + 质量门让腐化在最早一刻显形，而非在下游报告里悄悄污染结论。

## 2. MVP 范围（锁定——不在此列表的功能一律不做）

| 优先级 | 功能 | 验收标准摘要 | RICE |
|--------|------|-------------|------|
| P0 | 离线 fixture demo 生成 HTML 看板 | `make demo` 退 0 生成 `dist/index.html` | — |
| P0 | 五层骨架 + 单库 9 表 | 目录分层合规、依赖只向下、单库 9 表 DDL 通过 | — |
| P0 | fail-loud 质量门 6 类检查 | 输出 PASS/DEGRADED/BLOCKED，BLOCKED 退 4 | — |
| P0 | CLI 命令契约 | init/collect/process/quality/decide/render/run daily/manifest/plugins/doctor；`make demo` / `make demo-stale` 为稳定演示入口（CLI_CONTRACT §五） | — |
| P0 | 静态 HTML 看板（Jinja2+ECharts+Lucide） | 零 emoji、双通道色彩、四态图标 | — |
| P1 | Yahoo 真实源进阶路径 | `apex collect --source yahoo` 可拉数据写 bronze | — |
| P1 | 可注入 Clock + FrozenClock | `make demo-stale`（= `apexfin run daily --fixture-pack stale`）退 4 作为差异化回归测试 | — |

## 3. 明确不做（Out-of-Scope — 锁定）

| 不做的功能 | 原因 | 何时考虑 |
|------------|------|----------|
| 券商源 Futu / IB / 持仓 | 用户决策全删，避免密钥与私有数据进公开仓库 | 永不（参考实现不绑定私人券商） |
| 实时流式管线 | MVP 批处理 + 日频已足够演示全链路 | v2 |
| HTTP 服务端 / openapi.yaml | 无服务端，CLI 即唯一对外接口（O-04 已裁决） | 如需 SaaS 化 |
| 真正 alpha 算法 | 只留抽象基类 + 玩具实现，抽的是骨架不是策略 | 用户自行扩展 |
| pandas 运行时依赖 | 体积 / 可移植性 / 依赖面（ADR-008） | 若出现性能瓶颈再评估 |

## 4. 技术架构（锁定 — 含版本锚定，2026-08-02 PyPI/npm 实测）

| 层 | 技术 | 实际版本 | 锁定原因 |
|----|------|----------|----------|
| 包管理 | uv | latest | 快、可复现锁文件 |
| CLI | typer | 0.x | 类型安全 CLI |
| 配置 | pydantic-settings + pyyaml | — | 强类型配置 |
| 模板 | jinja2 | 3.x | 静态看板渲染 |
| HTTP | httpx | — | 真实源抓取 |
| 重试 | tenacity | — | 退避 |
| 日志 | structlog | — | 结构化 |
| 图标 | lucide-static | 1.28.0 | 零 emoji、可 sprite 提交 |
| 图表 | echarts | 6.1.0 | 看板 |
| 测试 | pytest + hypothesis + ruff + mypy | — | 质量门 |
| 存储 | sqlite3（stdlib） | — | 零依赖 |
| 日历 | 自建轻量交易日历（约 250 行，覆盖 NYSE） | — | 替代 pandas/exchange_calendars |

## 5. CLI 命令清单（锁定——等价 openapi 契约，见 O-04）

> 本项目无 HTTP 服务端，CLI 即唯一对外接口。`docs/CLI_CONTRACT.md` + `contracts/*.schema.json` + `docs/INTERFACES.md` 为等价契约。

| 命令 | 功能 | 退出码 | 说明 |
|------|------|--------|------|
| `apexfin init` | 初始化工作区 + sqlite schema | 0/2/3 | 生成目录与建表 |
| `apexfin collect --source yahoo` | 抓取真实源 → bronze | 0/1/5 | 进阶路径，默认不访问 |
| `apexfin process` | bronze → silver 点 | 0/1 | 计算 silver_points |
| `apexfin quality` | 跑 6 类检查 | 0/4 | BLOCKED 退 4 |
| `apexfin decide` | 治理层裁决 | 0/4 | 依赖 quality 结果 |
| `apexfin render` | 渲染 HTML 看板 | 0/1 | 输出 `dist/index.html` |
| `apexfin run daily --fixture-pack {fresh,stale}` | 离线 fixture 跑通端到端 | 0/4 | fresh 退 0、stale 退 4（差异化回归） |
| `apexfin manifest validate/show` · `apexfin plugins list` · `apexfin doctor` | 运维面 | 见 CLI_CONTRACT §四 | 见 CLI_CONTRACT §四 |

**演示入口**：`make demo` / `make demo-stale` 是稳定演示入口（等价命令与预期退出码见 CLI_CONTRACT §五），**不是独立 CLI 命令**——CLI 只提供 `apexfin run daily --fixture-pack {fresh,stale}`，make 目标是其包装。

**退出码契约**：`0` OK / `1` RUNTIME / `2` USAGE / `3` CONFIG / `4` QUALITY_BLOCKED / `5` SOURCE_UNAVAILABLE / `6` MANIFEST_INVALID。`--json` 输出统一信封。

## 6. 数据库表清单（锁定，单库 = 9 业务表 + 1 元表）

**9 业务表**：`bronze_records` / `bronze_revisions` / `silver_points` / `quality_findings` / `series_health` / `pipeline_runs` / `step_runs` / `decisions` / `opinion_ledger`。
**1 元表**：`schema_migrations`（迁移版本，只前进不回滚，不计入业务表计数）。

> DDL 唯一真值以 `docs/DATA_CONTRACT.md` 的 10 个 `CREATE TABLE` 为准；QA 验收时按「9 业务 + 1 元 = 10 张实际表」核对，不要按字面「9 表」判定失败。

`series_health` 关键字段：`last_event_date TEXT`、`lag_trading_days INTEGER`、`max_lag_trading_days INTEGER`（检查时快照，O-07 落地）。**无 hours 字段**。
`no_call` 是一等公民：质量闸门拦下时仍写记录，不静默丢弃。

## 7. 页面清单（锁定）

| 页面 | 路由/产物 | 核心组件 | 对应命令 | 设计 Token 主题 |
|------|-----------|----------|----------|-----------------|
| 看板总览 | `dist/index.html` | 健康轨 + 质量矩阵 + 流水线 + 决策 | `apexfin render` / `make demo` | 双通道色彩 + Lucide |

单页 dashboard：ECharts 图表 + 四态图标，由 `render` 命令从 DataPack JSON 渲染（Jinja2 模板）。

## 8. 设计 Token（锁定）
- **主色**：行情绿 160°（量级 `#1F9D55`）/ 状态青 189°（`#2E9BAF`），相差 29.3° 消除「红涨绿跌 vs 红失败绿通过」歧义。
- **四态**：`healthy→#2E9BAF` / `degraded→#C99A3B` / `blocked→#E14A63` / `unknown→#5E6B7E`。
- **字体**：Inter + Noto Sans SC。
- **图标**：Lucide（lucide-static 1.28.0），16/20/24px，零 emoji，CI 双闸（sprite 比对 + `#icon-*` 引用校验）。
- **主题**：浅色为主，深色可选。
- **对标**：干净、数据密集、可审计的参考实现质感（非营销页）。

## 9. 验收标准（锁定——QA 测试时以此为唯一依据，EARS 格式）

| 编号 | 功能 | EARS 格式验收标准 | 优先级 |
|------|------|-------------------|--------|
| AC-01 | demo | While 用户运行 `make demo`（= `apexfin init && apexfin run daily --fixture-pack fresh`），系统**必须**用离线 fixture 生成 `dist/index.html` 且退出码 0 | P0 |
| AC-02 | demo-stale | If fixture 标记 stale（`apexfin run daily --fixture-pack stale`，即 `make demo-stale`），系统**必须**退出码 4 且 `state=BLOCKED` | P0 |
| AC-03 | collect | While 用户运行 `apexfin collect --source yahoo`，系统**必须**拉取并写 bronze | P1 |
| AC-04 | Yahoo 429 | If Yahoo 返回 429，系统**必须**停止本源并写 finding，不重试绕行 | P0 |
| AC-05 | 质量门 | While 质量门运行，系统**必须**按 6 类检查输出 PASS/DEGRADED/BLOCKED | P0 |
| AC-06 | BLOCKED | If 状态 BLOCKED，系统**必须**退出码 4 | P0 |
| AC-07 | 看板图标 | While 渲染看板，系统**必须**零 emoji 并用锁定 Lucide 图标 | P0 |
| AC-08 | 图标缺失 | If 图表请求缺失图标，构建**必须**失败（sprite fail-loud） | P0 |
| AC-09 | 新鲜度 | While 渲染健康轨，系统**必须**用 `lag_trading_days / max_lag_trading_days` 进度条（O-07） | P0 |
| AC-10 | 时间语义隔离 | While 渲染健康行，系统**必须**显示业务日期 `last_event_label`（含周几），且健康行内**不得**出现任何写入时间或相对时间串（O-08） | P0 |
| AC-11 | 运行页脚 | While 渲染看板，系统**必须**将管道存活时间全局渲染于 `run_footer` 一处，措辞指向采集动作而非数据年龄（O-08） | P0 |

### 9.1 机械验证方式（QA 照此执行，不靠肉眼，不自行发明手段）

> 为什么这一节必须存在：一条验收标准如果只写「必须正确显示 X」，执行者会自然退化成「找到 X 就算过」。Phase 3 已实证——前端拿到「不得出现任何选择器」这条通用规则后，用三个点名项的字面量 grep 自检并报 pass，而文件里还躺着两块它没想到要找的选择器。**通用规则必须配可执行的验证命令**，否则规则的解释权就落到了被约束的一方手里。

| AC | 机械验证 | 通过判据 |
|----|----------|----------|
| AC-01 | `apexfin run daily --fixture-pack fresh; echo $?` + `test -s dist/index.html` | 退出码 `0`；产物非空且含 `<html`；产物 mtime 晚于命令启动时刻（防拿旧产物冒充） |
| AC-02 | `apexfin run daily --fixture-pack stale; echo $?` + `SELECT state FROM pipeline_runs ORDER BY started_at DESC LIMIT 1` | 退出码 `4`；查询结果 `BLOCKED`。**两者必须同时成立**——只验退出码无法区分「正确阻断」与「崩溃退 4」 |
| AC-03 | `apexfin collect --source yahoo` + `SELECT COUNT(*) FROM bronze_records WHERE source_name='yahoo'` | 计数 `> 0`。需网络，CI 中标记为可跳过，但本地交付验收必须实跑一次 |
| AC-04 | 单测 mock Yahoo 返回 429，断言 HTTP 客户端**请求次数 == 1** + `SELECT COUNT(*) FROM quality_findings WHERE check_id LIKE '%source%'` | 请求次数严格等于 1（≥2 即为绕行重试，直接 fail）；finding 计数 `>= 1`。此即 ADR-009 的 C4 断言 |
| AC-05 | 跑一次完整管道后 `SELECT DISTINCT check_id FROM quality_findings` + `SELECT DISTINCT state FROM series_health` | check_id 去重后覆盖全部 6 类（freshness/completeness/duplicates/consistency/continuity/range）；state 取值只出现在 `healthy/degraded/blocked/unknown` 枚举内 |
| AC-06 | 构造任一 BLOCKED 场景（非 demo-stale 路径）后 `echo $?` | 退出码 `4`。与 AC-02 的区别：AC-02 验的是 stale fixture 这条具体路径，AC-06 验的是「BLOCKED 一律退 4」这条通用规则，须另找一条 BLOCKED 成因验证 |
| AC-07 | emoji 正则扫 `dist/index.html` + `templates/**` + `static/**`；并提取 dist 中全部 `#icon-xxx` 引用，逐个在 `static/sprite.svg` 中查 `<symbol id="xxx">` | emoji 计数 `0`；每个引用的 icon id **都能在 sprite 中找到对应 symbol**（只数引用次数不算验证，断链的引用同样会计数） |
| AC-08 | 临时向 `config/icons.yaml` 追加一个不存在的图标名，跑 `python tools/build_sprite.py; echo $?`，跑完还原 | 退出码 `3`（fail-loud）。**必须实际触发一次失败**，不能只读代码确认有 raise |
| AC-09 | 解析 `dist/index.html` 中进度条元素的 `aria-valuenow` / `aria-valuemax`，与 fixture 各行的 `lag_trading_days` / `max_lag_trading_days` 逐行比对 | 三条同时成立：① `aria-valuemax == max(max_lag_trading_days, 1)`；② `aria-valuenow == min(lag_trading_days, aria-valuemax)`（进度条截断至 100% 是正确行为，不是 bug）；③ **凡 `lag > max_lag` 的行，页面必须另有超期标记**（`overdue` 态 class 或文案「超 N」），截断后 valuenow==valuemax 会让超期与刚好达标在视觉上不可区分——这是本条真正要防的东西。**只确认「页面上有进度条」不算通过** |
| AC-10 | ① `HealthRow` 类型定义中不存在 `last_checked_at` 或任何写入时间字段；② `dist/index.html` 健康区块内「小时前」「分钟前」「秒前」计数；③ `src/apexfin/**` 与 `templates/**` 中标识符 `lag_hours` / `sla_hours` / `sla_ratio` 计数（沿用 ARCHITECTURE:460 既有门禁） | ① 无；② `0`；③ `0` |
| AC-11 | `grep -c 'run-footer' dist/index.html` + 页脚文本措辞检查 | 计数 **恰为 1**（全局一处，多处即违反 O-08 的物理分离）；页脚措辞含「采集完成」类指向动作的表述，不得出现「数据更新于」类指向数据年龄的表述 |

**执行纪律三条**：

1. **不得用「代码里有这个逻辑」代替「实际跑出这个结果」**。AC-08 尤其——读到 `raise SystemExit(3)` 不等于它会被触发。
2. **失败即失败，不得自行降级判据**。若某条 AC 因环境原因无法执行（如 AC-03 无网络），标记为 `BLOCKED-BY-ENV` 上报，不得改判为 PASS。
3. **AC-01 与 AC-02 必须在同一次验收中先后执行**，证明退出码 0 与 4 的差异来自 fixture pack 与 Clock 注入，而非两条各自 hack 的分支。

## 10. 边界与约束
- Python ≥ 3.11；仅 8 个顶层依赖（typer/pydantic/pydantic-settings/pyyaml/jinja2/httpx/tenacity/structlog）。
- 交易日历覆盖 NYSE（advisory：仅 NYSE，扩展需补其他交易所）。
- 单文件 ≤ 300 行；入口文件（cli/app.py）只装配、零业务。
- 300 行红线的适用范围：防的是「单文件多职责 + 控制流膨胀」，不是防纯声明表。`static/tokens.css` 为已豁免的纯 token 声明表（O-10），豁免带三条机械条件：除两块 `@font-face` 外不得出现任何类/元素/属性选择器（只允许 `:root` 及 `[data-theme=*]`/`[data-palette=*]` 作为 token 作用域）；`@media` 内只允许改 token 值不得含组件规则；文件顶部注释写明豁免判定依据——引入任何选择器则豁免自动失效。
- P0 红线：禁 emoji 图标 / 禁紫粉渐变 / 禁弹跳缓动 / 禁空洞文案。
- MIT 许可。
- CI 双闸：sprite 比对 + `#icon-*` 引用校验；`denylist` 作为扫描器**输入**而非扫描对象（O-06）。

## 11. 内嵌已知坑（从项目记忆拉取）

| 坑 | 技术栈指纹 | 根因 | 修法 |
|----|------------|------|------|
| 密钥明文泄露 | APEXDATA fetch_fred.py:22 | 硬编码 32 位 key | 只读 env `APEXFIN_FRED_API_KEY`；U-01 吊销重发 |
| 依赖倒置 | APEXDATA POST_STEPS | 手工顺序脆弱 | `depends_on` + 拓扑排序 + 环检测 |
| 扫描器自伤 | CI P0 扫描 | 红线声明文本被扫 | `denylist` 作输入，扫 `src/**`+`config/**`（O-06） |
| 图标名变更 | lucide-static 1.28.0 | 旧名几何不同 | `icons.yaml` 语义锁定，构建期 fail-loud（O-02） |
| 小时级 SLA 脆弱 | 日历/质量 | 周末假期下不准 | 改用交易日历语义（O-07） |

## 12. 端到端验证步骤（Spec 锁定的最后一项）

```bash
make demo            # 退 0，生成 dist/index.html
make demo-stale      # 退 4，CI 断言必返 4
apexfin quality      # 退 0；注入陈旧 fixture 时退 4
# 断言 dist/index.html 含 #icon-check-circle-2 且无 emoji 字符
# 断言 健康轨进度条 = lag_trading_days / max_lag_trading_days
```

## 13. 变更记录
| 日期 | 变更内容 | 原因 | 影响范围 |
|------|----------|------|----------|
| 2026-08-02 | 初版 Spec 锁定 | 三文档确认 + O-01（离线默认）/ O-07（新鲜度语义）裁决 | 全项目依据 |
| 2026-08-02 | §6 表计数消歧：9 业务表 + 1 元表 | 原文「9 表」却列出 10 个表名，会导致 Phase 4 QA 计数验收误判 | 仅澄清表述，DDL 无变更 |
| 2026-08-02 | O-08 时间语义拆分：健康行去相对时间，新增 `last_event_label` + `DataPack.run_footer`；新增 AC-10 / AC-11 | 相对时间只能由写入时间派生，而写入时间测「管道多久前碰过源」≠「数据多旧」，周日跑管道会把滞后 2 交易日的数据显示为「2 分钟前」，系统性低估陈旧度 | **小改**：无新增 CLI 命令、无新增表（`pipeline_runs.finished_at` / `last_checked_at` 本就存在）、影响单页看板、不改核心流程。已实时传导前后端（施工早期，零返工） |
| 2026-08-02 | §9 拆出 9.1「机械验证方式」，为 AC-01..11 全部 11 条补可执行验证命令与通过判据，并立执行纪律三条 | Phase 3 实证：给出通用规则而不给验证命令，执行方会退化成按点名清单勾选——前端拿到「不得出现任何选择器」后用三个字面量 grep 自检报 pass，漏掉两块未想到要找的选择器。同一失效模式会在 Phase 4 重演，且 QA 阶段无人再复核 | **零契约影响**：不改功能、API、表、页面，只规定 QA 怎么验。对施工中的前后端 agent 无影响（该节由 QA 消费）。AC-04/08/09 的判据从「有无」升级为「实跑触发 + 数值逐行比对」 |
| 2026-08-02 | O-09 阈值缺省边界（`expectations.yaml` 的 `defaults` 段必填、缺键 fail-loud）；O-10 `tokens.css` 300 行豁免（带三条机械条件） | O-09：dataclass 默认值构成「配置里没有、代码里补上」的隐形路径，使 DATA_CONTRACT「阈值永远已知」的前提失效。O-10：300 行红线约束逻辑单元而非纯声明表，但豁免必须可验证，否则等于放宽红线 | **小改**：均无新增 CLI/表/页面。O-09 影响 `quality/expectations.py` + 新增 `config/expectations.yaml`；O-10 影响 `static/tokens.css` 与 `static/dashboard.css` 的职责划分。详见 `docs/decisions/OPEN-DECISIONS.md` |
| 2026-08-02 | 修正 AC-09 判据：由「valuenow/valuemax 与 lag/max 逐行相等」改为「valuemax==max(max_lag,1) ∧ valuenow==min(lag,valuemax) ∧ 超期行必须另有 overdue 标记」 | team-lead 原判据有误。进度条截断至 100% 是正确 UI 行为（`_build_health_rows` 已如此实现），原判据会让所有超期行假失败；同时该冲突暴露了真正的风险——截断后 valuenow==valuemax 使「超期」与「刚好达标」视觉不可区分，故补第三条 | **零契约影响**：只改 QA 判据，不改实现。AC-09 由「数值相等」升级为「截断规则正确 + 超期不被截断掩盖」 |
| 2026-08-02 | 命令面收敛：§2/§5/§7/§9/§9.1 命令清单对齐 CLI_CONTRACT——删 `apexfin demo/demo-stale`（非 CLI 命令）、`report`→`render`，AC-01/02 改 `make demo`/`make demo-stale`，§9.1 机械验证改裸命令 `apexfin run daily --fixture-pack {fresh,stale}`；§10 补 O-10 的 300 行豁免适用范围 | 封版裁决（高见远裁决 · team-lead 确认）：CLI 实际命令为准（10 条命令），make 目标即 demo 抽象层，不新增别名命令；裸命令验证解耦 QA 与发布文件时序（Makefile 由 DevOps 在 QA 后补齐） | **零契约影响**：AC-01/02 判据（0+产物 / 4+state=BLOCKED）不变，纪律3（同次验收先后执行）不变；仅文档命令名与验证命令 |
| 2026-08-02 | §9.1 列名对齐 DDL：AC-02 `run_state`→`state`、AC-04/AC-05 `check_name`→`check_id` | QA 最终复验发现 SPEC 机械验证 SQL 用了旧列名，照抄会报 `no such column`；真实 DDL 与 INTERFACES/DATA_CONTRACT 均用 `state`/`check_id` | **零契约影响**：纯文档正确性修正，判据不变（QA 验收时已用正确列名） |
