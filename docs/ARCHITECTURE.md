# APEXFIN 架构设计文档

| 项目 | 内容 |
|------|------|
| 文档 | ARCHITECTURE.md |
| 版本 | v1.0 |
| 撰写 | 高见远（首席架构师） |
| 日期 | 2026-08-02 |
| 上游输入 | `docs/PRD.md` v1.0（许清楚） |
| 配套文档 | `docs/INTERFACES.md`、`docs/DATA_CONTRACT.md`、`docs/CLI_CONTRACT.md`、`docs/ALPHA_BOUNDARY.md`、`docs/decisions/ADR-001..008` |
| 机器可读契约 | `contracts/manifest.schema.json`、`contracts/sources.schema.json`、`contracts/silver_point.schema.json` |

本文档不使用 emoji。全项目图标方案见第九章，已锁定 lucide-static，禁止 emoji 作为功能图标。

---

## 一、架构目标与约束

### 1.1 从 PRD 继承的硬约束

| 约束 | 来源 | 对架构的直接影响 |
|------|------|-----------------|
| 零外部服务 | PRD 十·NFR | 只用 SQLite；不引入 Redis/PG/MQ/Scheduler 进程 |
| 核心运行时顶层依赖 ≤ 10 | PRD 十四·给架构师 | 排除 pandas/numpy/yfinance/exchange_calendars（见 1.2） |
| 零 API key 可跑通 demo | PRD 六·AC-1 | demo 走内置 fixture 数据源，网络源为可选路径 |
| `make demo` < 60 秒 | PRD 十·性能 | 禁止导入重型科学栈；冷启动导入时间进入预算 |
| fail-loud 必须真中断 | PRD 十四 | 质量门以非零退出码终止 run，且写入 `run_state=BLOCKED` 阻断下游 |
| 新鲜度按业务时间 + 交易日历 | PRD 十四 | 需要自建轻量交易日历（见 ADR-006） |
| 故障注入不得是脏 hack | PRD 十四 | 注入点做成一等公民：可替换 Clock + fixture pack 切换 |
| 治理层可被单独抄走 | PRD 十四 | `quality/`、`pipeline/manifest.py` 只依赖 `core/` 与 `storage/` 协议，不反向依赖采集与决策 |
| 单文件 ≤ 300 行 | 团队 P0 | 每个质量检查独立文件；CLI 每个子命令独立文件 |
| 禁 emoji / 禁紫粉渐变 | 团队 P0 | 见第九章 |
| MIT 许可 | PRD 十·NFR | 依赖必须 MIT/BSD/Apache-2.0/ISC 兼容，见 8.3 |

### 1.2 一条关键取舍：运行时不引入 pandas

APEXDATA 依赖 pandas + numpy + polars + akshare。APEXFIN 全部剔除，理由：

- 依赖预算：pandas 3.0.5 安装体积在 60 MB 量级并强制拉入 numpy、pytz、tzdata，单它一个就吃掉「≤10 顶层依赖 + 5 分钟上手」的大半预算。
- 冷启动：`import pandas` 在普通笔记本上 0.6–1.2 秒，直接冲击 60 秒全链路指标里最不该被浪费的部分。
- 必要性存疑：MVP 的实际计算只有「拉 JSON、写 SQLite、按符号取最近 N 条算收益率、算滞后交易日」。这些用标准库 `sqlite3` + `statistics` + 纯 Python 即可，SQL 侧还能用窗口函数（SQLite 3.25+ 支持 `LAG`/`ROW_NUMBER`）。
- 副作用：这条取舍连带排除了 `yfinance`（依赖 pandas）、`exchange_calendars` / `pandas_market_calendars`（依赖 pandas）。因此采集与日历都需自建薄实现，成本已评估为约 250 行，可接受。

风险与缓解：使用者若要接自己的付费源并用 pandas 处理，可在自己的 `DataSource` 实现里自行 `import pandas`，框架不阻止；pandas 被列为 optional extra `apexfin[pandas]`，不进核心。

---

## 二、分层架构

```
+---------------------------------------------------------------+
|  L5 表现层  cli/            Typer 命令，只做参数解析与装配      |
|             reporting/      Jinja2 渲染静态 HTML + SVG sprite   |
+---------------------------------------------------------------+
                              | 只向下调用
+---------------------------------------------------------------+
|  L4 编排层  pipeline/       manifest 加载与校验、拓扑规划、     |
|                             步骤执行、run 状态机、闸门裁决       |
+---------------------------------------------------------------+
                              | 只向下调用
+---------------------------------------------------------------+
|  L3 领域层                                                     |
|   sources/     采集适配器（fixture / yahoo / fred）             |
|   processing/  bronze -> silver 归一与 quality_score            |
|   quality/     6 类检查 + 新鲜度闸门（治理核心，可独立抄走）     |
|   decision/    信号与决策抽象 + 玩具参考实现                     |
|   analysis/    多角色 prompt 契约 + 确定性 mock provider        |
|   accounting/  观点对账台账（P1）                               |
+---------------------------------------------------------------+
                              | 只向下调用
+---------------------------------------------------------------+
|  L2 存储层  storage/        SQLite 连接、迁移、Repository        |
+---------------------------------------------------------------+
                              | 只向下调用
+---------------------------------------------------------------+
|  L1 内核    core/           协议(Protocol)、模型、错误、注册表、  |
|                             配置、时钟、日历、日志。零业务依赖   |
+---------------------------------------------------------------+
```

### 2.1 依赖方向铁律

1. 依赖只能从上层指向下层，**不允许跨层反向**。`core/` 不 import 任何本项目其它包。
2. L3 各领域包**互不 import**。`quality/` 不认识 `sources/`，`decision/` 不认识 `quality/`。它们之间只通过 L4 编排层传递数据，或通过 `core/contracts.py` 的协议类型交流。这是「治理层可被单独抄走」的技术前提。
3. `cli/app.py` 是唯一的装配点（Composition Root），负责构造容器并注入实现；任何深层模块**不得**自行 `from apexfin.sources.yahoo import ...` 这类具体实现导入。
4. CI 用 `import-linter` 契约（或等价的自研 AST 检查，见 7.3）在流水线中强制以上三条，违反即红灯。

### 2.2 数据流（正常态）

```
fixture / yahoo / fred
        |  RawRecord（未解释的原始 payload）
        v
[collect]  ---> bronze_records（原样留痕 + payload_hash 去重 + 修订链）
        |
        v
[process]  ---> silver_points（归一化 value + quality_score + is_filled）
        |
        v
[quality]  ---> quality_findings + series_health
        |        裁决：PASS / DEGRADED / BLOCKED
        |
        +--BLOCKED--> 终止 run，退出码 4，decision 不执行
        |
        v (PASS / DEGRADED)
[decide]   ---> decisions（玩具动量；DEGRADED 时只对健康 series 产出）
        |
        v
[render]   ---> dist/dashboard.html（单文件；顶部数据健康度区块）
```

### 2.3 数据流（陈旧注入态，`make demo-stale`）

```
fixture pack = "stale"（committed 的一组 event_time 落后的样本）
        v
[collect] 正常写入 bronze/silver（数据本身没坏，只是旧）
        v
[quality] check_freshness 判定 risk_essential 源滞后 > 阈值
        -> QualityFinding(severity=BLOCKING)
        -> gate 裁决 BLOCKED，写 pipeline_runs.state='BLOCKED'
        -> 进程退出码 4，stderr 打印：源名 / 最新业务日 / 滞后交易日 / 阈值
        v
[decide] 不执行（编排层按 state 短路）
        v
[render --degraded] 读取 BLOCKED 状态，渲染降级态看板：
        健康度区块红 + 文字标签 + 形状不同的图标；
        决策区显示「因数据陈旧未产出结论」，不显示任何旧数字
```

关键设计：**陈旧不是靠改数据库制造的**，而是靠切换 fixture pack + 可注入 `Clock`。两者都是生产代码里正常存在的能力（fixture 源用于离线 demo，Clock 用于测试），不存在只为演示而生的 hack 分支。

---

## 三、包结构

```
APEXFIN/
├── pyproject.toml                  # PEP 621 + hatchling + uv 锁定
├── uv.lock                         # 提交入库，保证可复现
├── Makefile                        # demo / demo-stale / test / lint / typecheck
├── README.md / README.zh-CN.md
├── LICENSE                         # MIT
├── .env.example
├── .github/workflows/ci.yml
│
├── src/apexfin/
│   ├── __init__.py                 # 只暴露 __version__
│   ├── __main__.py                 # python -m apexfin
│   │
│   ├── core/                       # L1 内核：零本项目依赖
│   │   ├── contracts.py            # 所有 Protocol 定义（见 INTERFACES.md）
│   │   ├── models.py               # pydantic 模型：RawRecord/BronzeRecord/SilverPoint/...
│   │   ├── enums.py                # Tier / Severity / RunState / GateVerdict
│   │   ├── errors.py               # ApexfinError 树，含 exit_code 语义
│   │   ├── registry.py             # 装饰器注册表 + entry_points 发现
│   │   ├── config.py               # pydantic-settings，YAML + env 覆盖
│   │   ├── clock.py                # Clock 协议 + SystemClock + FrozenClock
│   │   ├── calendar.py             # TradingCalendar 协议 + YAML 驱动实现
│   │   ├── logging.py              # structlog 配置，run_id 绑定
│   │   └── ids.py                  # run_id 生成
│   │
│   ├── storage/                    # L2
│   │   ├── engine.py               # 连接、PRAGMA、SAVEPOINT 上下文管理器
│   │   ├── migrator.py             # 顺序 SQL 迁移执行器
│   │   ├── migrations/0001_init.sql
│   │   ├── bronze_repo.py
│   │   ├── silver_repo.py
│   │   ├── quality_repo.py         # quality_findings + series_health
│   │   ├── run_repo.py             # pipeline_runs + step_runs（自观测事件）
│   │   └── decision_repo.py        # decisions + opinion_ledger
│   │
│   ├── sources/                    # L3 采集
│   │   ├── base.py                 # BaseCollector 抽象基类 + 重试/退避骨架
│   │   ├── fixture.py              # 离线 fixture 源（demo 默认，零网络零 key）
│   │   ├── yahoo.py                # Yahoo chart JSON，单 host、保守限速
│   │   ├── fred.py                 # FRED observations，key 只从 env 读
│   │   └── fixtures/               # fresh/ 与 stale/ 两套样本 JSON
│   │
│   ├── processing/                 # L3 归一
│   │   ├── extractors.py           # Extractor 注册表（按 source_name 派发）
│   │   ├── silver_builder.py       # 增量构建 silver_points
│   │   └── quality_score.py        # 来源可靠性 x 时效性衰减
│   │
│   ├── quality/                    # L3 治理核心（低耦合，可整包抄走）
│   │   ├── base.py                 # QualityCheck 抽象 + QualityContext
│   │   ├── expectations.py         # SourceExpectation 加载（YAML 驱动）
│   │   ├── check_freshness.py
│   │   ├── check_completeness.py
│   │   ├── check_duplicates.py
│   │   ├── check_consistency.py    # bronze <-> silver 一致性
│   │   ├── check_continuity.py     # 交易日历感知的跳空识别
│   │   ├── check_range.py          # 数值合理性
│   │   ├── gate.py                 # findings -> GateVerdict（tier 感知）
│   │   └── health.py               # series_health 维护
│   │
│   ├── decision/                   # L3 决策骨架（抽 alpha 后）
│   │   ├── base.py                 # BaseSignal / BaseStrategy 抽象
│   │   ├── views.py                # MarketView 只读投影（策略的唯一输入）
│   │   ├── toy_momentum.py         # 玩具参考实现，文件头显式声明非投资建议
│   │   └── aggregator.py           # 等权聚合，无任何调优参数
│   │
│   ├── analysis/                   # L3 多角色 AI 契约层（P1）
│   │   ├── roles.py                # 角色卡加载与校验
│   │   ├── prompts/                # 8 个角色 md 模板（去个人化）
│   │   ├── schema.py               # 结构化输出 schema（pydantic）
│   │   ├── client.py               # LLMClient 协议
│   │   └── providers/mock.py       # 确定性 mock，demo 离线可跑
│   │
│   ├── accounting/                 # L3 观点对账（P1）
│   │   ├── ledger.py               # 观点落库
│   │   └── settle.py               # 到期用后续行情判定命中
│   │
│   ├── pipeline/                   # L4 编排
│   │   ├── manifest.py             # 加载 + JSON Schema 校验 + 双向一致性断言
│   │   ├── planner.py              # depends_on 拓扑排序 + 环检测
│   │   ├── steps.py                # 内置步骤注册（@step 装饰器）
│   │   ├── runner.py               # 执行、超时、critical、状态机
│   │   └── events.py               # 自观测事件写入
│   │
│   ├── reporting/                  # L5 渲染
│   │   ├── renderer.py             # Jinja2 Environment 装配，autoescape
│   │   ├── datapack.py             # 视图模型组装（模板只读 DataPack）
│   │   ├── templates/base.html + partials/*.html
│   │   ├── icons.py                # sprite 校验：模板引用的 id 必须存在
│   │   └── static/
│   │       ├── icons/sprite.svg    # 由 lucide-static 抽取生成，提交入库
│   │       ├── app.css
│   │       └── vendor/echarts.min.js
│   │
│   └── cli/                        # L5 装配点
│       ├── app.py                  # Typer 应用装配，仅注册与注入
│       ├── context.py              # CliContext 容器
│       ├── cmd_init.py / cmd_collect.py / cmd_process.py
│       ├── cmd_quality.py / cmd_decide.py / cmd_render.py
│       ├── cmd_run.py / cmd_manifest.py / cmd_plugins.py / cmd_doctor.py
│       └── output.py               # [PASS]/[FAIL]/[DEGRADED] 文字前缀，禁 emoji
│
├── config/
│   ├── pipeline_manifest.yaml      # 治理单一真源
│   ├── sources.yaml                # 符号/系列清单，数据驱动
│   ├── expectations.yaml           # 各源频率与最大滞后交易日
│   ├── icons.yaml                  # 图标白名单（sprite 生成输入）
│   └── calendars/nyse.yaml         # 假日表
│
├── contracts/                      # 机器可读契约
│   ├── manifest.schema.json
│   ├── sources.schema.json
│   └── silver_point.schema.json
│
├── tests/                          # 单测 + 契约测试 + 端到端 demo 测试
├── tools/build_sprite.py           # 从 lucide-static 生成 sprite（开发期）
└── docs/
```

文件粒度规则：每个质量检查、每个 CLI 子命令、每个 Repository 各占一个文件，天然满足单文件 ≤ 300 行。预估最大文件为 `pipeline/runner.py`（约 220 行）与 `sources/yahoo.py`（约 180 行）。

---

## 四、技术选型

全部版本号于 2026-08-02 通过 PyPI JSON API 与 npm registry 实时查询确认存在，非记忆推断。

### 4.1 选型结论表

| 维度 | 选定 | 版本约束 | 候选对比与理由 |
|------|------|---------|---------------|
| Python | CPython | `requires-python = ">=3.11,<3.15"` | 3.10 于 2026-10-31 EOL，排除；3.11 起 `tomllib`、异常组、性能提升可用；上限锁 3.15 防未来破坏。CI 矩阵 3.11/3.12/3.13/3.14 |
| 包管理/构建 | uv + hatchling | uv 0.12.1，hatchling 1.31.0 | uv vs Poetry vs pip-tools vs PDM：uv 解析安装速度领先一个数量级，直接服务「5 分钟上手」硬指标；`uv.lock` 跨平台可复现；hatchling 是 PEP 621 原生后端，无私有配置段。详见 ADR-001 |
| CLI 框架 | Typer | 0.27.0 | Typer vs Click vs argparse vs Fire：Typer 基于 Click，类型注解即参数声明，自动生成帮助与补全；Click 需手写装饰器参数；argparse 无类型；Fire 反射式不可控。详见 ADR-003 |
| 数据层 | stdlib `sqlite3` + 薄 Repository | 标准库 | 裸 sqlite3 vs SQLAlchemy 2.0.51 vs DuckDB 1.5.5：ORM 对 6 张表是净负担且掩盖 SQL；DuckDB 分析强但改变范式、增加 40 MB 依赖且不是 PRD 场景。裸 sqlite3 零依赖、SQL 显式可读，符合「参考实现要给人读」。详见 ADR-002 |
| 数据校验 | pydantic + pydantic-settings | 2.13.4 / 2.14.2 | 边界处校验（外部 JSON 入口、配置、LLM 输出）；Rust 内核性能足够；pandera 0.32.1 需 pandas，出局 |
| 配置 | YAML + env 覆盖 | pyyaml 6.0.3 | 分层：默认值（代码）< `config/*.yaml` < 环境变量 < CLI 参数。密钥只走 env，绝不进 YAML |
| HTTP | httpx | 0.28.1 | httpx vs requests 2.34.2：httpx 有原生超时语义、连接池、可选 HTTP/2，且未来接 async 无需换库。requests 亦可，差异不大，取 httpx |
| 重试退避 | tenacity | 9.1.4 | 30 行自研 vs tenacity：退避 + 抖动 + 条件重试的正确实现容易写错（这是生成式代码高发失效点），用成熟库 |
| 模板引擎 | Jinja2 | 3.1.6 | 与 APEXDATA 现有 `dashboard_renderer.py` 一致，迁移成本最低；`autoescape=True` 强制开启 |
| 图表 | Apache ECharts（vendored） | 6.1.0，Apache-2.0 | 单文件离线可用；不引入 npm 运行时；`echarts.min.js` 提交入库并在 NOTICE 标注。对比 Chart.js：ECharts 金融图（K 线、双轴）开箱即用 |
| 图标 | lucide-static -> 自建 sprite | lucide-static 1.28.0，ISC | 见第九章与 ADR-007 |
| 日志 | structlog | 26.1.0 | 结构化事件天然对齐「自观测事件表」；`run_id` 通过 contextvars 绑定，避免每处手传 |
| 终端输出 | rich（经 Typer 传递） | 15.0.0 | 表格与颜色；严禁 emoji，状态用 `[PASS]`/`[FAIL]`/`[DEGRADED]` 文字前缀 |
| 测试 | pytest + pytest-cov + hypothesis | 9.1.1 / 7.1.0 / 6.165.0 | hypothesis 用于日历与去重逻辑的属性测试，这两处最容易出沉默逻辑错误 |
| Lint/Format | Ruff | 0.16.1 | 单一工具替代 flake8+isort+black，降低贡献门槛 |
| 类型检查 | mypy（strict） | 2.3.0 | 对 `core/` 与 `quality/` 开 strict；`types-PyYAML 6.0.12.20260724` |
| 架构约束检查 | import-linter 或自研 AST 检查 | 见 7.3 | 强制 2.1 的依赖方向铁律 |
| CI | GitHub Actions | ubuntu-latest | 无 secret 环境跑 `make demo`，产物 HTML 上传为 artifact |

### 4.2 运行时依赖预算（PRD 上限 10）

| # | 包 | 版本下限 | 用途 |
|---|----|---------|------|
| 1 | typer | >=0.27.0,<0.28 | CLI |
| 2 | pydantic | >=2.13.4,<3 | 模型与校验 |
| 3 | pydantic-settings | >=2.14.2,<3 | 配置 |
| 4 | pyyaml | >=6.0.3,<7 | 配置与日历 |
| 5 | jinja2 | >=3.1.6,<4 | 渲染 |
| 6 | httpx | >=0.28.1,<0.29 | 采集（fixture demo 不用，但属核心能力） |
| 7 | tenacity | >=9.1.4,<10 | 退避重试 |
| 8 | structlog | >=26.1.0,<27 | 结构化日志 |

合计 8 个，留 2 个余量。`rich`、`click` 为 Typer 传递依赖，不单列。可选 extras：`apexfin[pandas]`、`apexfin[dev]`。

版本策略：下限锁到已验证的具体补丁版，上限锁到下一个主版本（Jinja2/pyyaml 等成熟包）或次版本（Typer/httpx 等 0.x 包，0.x 的次版本可能含破坏变更）。`uv.lock` 提交入库，CI 用 `uv sync --frozen`。

---

## 五、数据契约与治理

完整 DDL 见 `docs/DATA_CONTRACT.md`，此处只述架构决策。

### 5.1 分层与表

| 层 | 表 | 语义 |
|----|----|------|
| Bronze | `bronze_records` | 原样 payload + `payload_hash`；`UNIQUE(source_name, symbol, event_time)`；同键不同 hash 走 `bronze_revisions` 修订链而非覆盖 |
| Bronze | `bronze_revisions` | 上游修订留痕（FRED 经常修订历史值），保证「历史可回溯」 |
| Silver | `silver_points` | 归一化 `value` / `value_secondary` / `quality_score` / `is_filled`；同样 `UNIQUE(source_name, symbol, event_time)` |
| Gold | `decisions`、`opinion_ledger` | 业务产物 |
| 运行 | `pipeline_runs`、`step_runs` | 自观测事件（PRD 十一·B） |
| 质量 | `quality_findings`、`series_health` | 检查结果与序列健康快照 |
| 元 | `schema_migrations` | 迁移版本 |

相对 APEXDATA 的简化：**取消双库架构**。APEXDATA 的 `apexdata.db` + `apexdata_daily.db` 是为 30 天滚动快照与业务表分离服务的，对参考实现属于额外心智负担。APEXFIN 单库 + 视图即可，`keep_daily` 语义改由 manifest 承载。

时区：全链路 UTC 存储，`event_time` 为 `TEXT` ISO-8601（`YYYY-MM-DDTHH:MM:SSZ`），另存 `event_date`（`TEXT`，交易日键）供日历比对。展示层按配置时区转换。

### 5.2 manifest 治理

沿用 APEXDATA 的四档 tier，这是本项目差异化的核心资产，术语不改：

| tier | 含义 | 陈旧时的闸门行为 |
|------|------|-----------------|
| `risk_essential` | 缺它会导致结论错误 | BLOCKING，非零退出码中断 |
| `support` | 支撑性上下文 | DEGRADED，标注但继续 |
| `display_only` | 仅展示 | DEGRADED，看板局部占位 |
| `research` | 研究性，不进每日 | 不参与每日闸门 |

manifest 条目字段：`name`、`tier`、`keep_daily`、`depends_on`、`timeout_s`、`critical`、`why`（强制必填的一句话，说明为什么值得每天跑——这是「管道瘦身依据」的载体，空字符串校验不通过）。

相对 APEXDATA 的改进：**用 `depends_on` 声明式依赖 + 拓扑排序，取代手工维护的有序 `POST_STEPS` 列表**。APEXDATA 的 `runner_post.py` 注释里详细记录过一次「依赖倒置 bug」（消费者排在生产者之前），根因就是顺序靠人肉维护。拓扑排序 + 环检测从结构上消灭这类 bug。

一致性校验（对应 PRD AC-6）双向断言：
1. 代码中 `@step` 注册的每个步骤，必须在 manifest 中声明；
2. manifest 中声明的每个步骤，必须能在注册表中找到；
3. `keep_daily=false` 的步骤不得被 `keep_daily=true` 的步骤依赖（否则每日链路会断）；
4. `depends_on` 图必须无环。
任一条失败 -> 退出码 6，列出全部差异项。

### 5.3 新鲜度定义（与 dbt 的关键差异）

```
lag_trading_days = calendar.trading_days_between(
    latest_event_date(source, symbol),   # 业务时间，不是写入时间
    clock.today(),                       # 可注入，便于测试与注入演示
)
verdict = BLOCKING if lag > expectation.max_lag_trading_days and tier == risk_essential
          else DEGRADED if lag > expectation.max_lag_trading_days
          else PASS
```

`expectations.yaml` 按 `(source, frequency)` 声明 `max_lag_trading_days`，从 APEXDATA 的 `SOURCE_EXPECTATIONS` 常量迁移为配置文件。

`TradingCalendar` 为协议，内置 `YamlTradingCalendar`（周末 + `config/calendars/nyse.yaml` 假日表）。诚实标注：内置日历只覆盖 NYSE/美国联邦假日，且假日表需要人工年更；需要其他交易所的使用者实现自己的 `TradingCalendar`。理由与替代方案见 ADR-006。

#### 5.3.1 新鲜度只有一种单位：交易日（OPEN-DECISIONS O-07）

**小时不是本项目的新鲜度单位，任何层都不是。** 契约中不存在 `lag_hours` / `sla_hours` / `sla_ratio` 字段，`quality_findings` 与 `series_health` 中不存储小时值，`freshness` 检查项的展示文本也一律用交易日表述（`"lag 2 交易日 / 阈值 1 交易日"`）。

理由是小时制 SLA 在这个领域会系统性说谎：周五收盘后到周一开盘约 62 小时，任何按小时计的日频源都会在每个周末稳定报警一次；叠加感恩节、圣诞这类连休，误报更密集。而运维看板一旦每周固定误报，人就会开始无视它——这比没有告警更糟。交易日历语义下，周五到周一的滞后是 1 个交易日，与周二到周三完全等价，这才是业务上真实发生的事。

#### 5.3.1.1 更正：健康区块内不出现「X 小时前」（撤回本节初稿的授权）

本节初稿写过一句「唯一允许出现『X 小时前』的地方是展示层由 `last_event_date` 对比 `Clock` 派生」。**这句话撤回**，它同时犯了两个错，是我的疏漏。

**错误一：类型上做不到。** `last_event_date` 是业务**日期**（`series_health.last_event_date TEXT`，日粒度）。日粒度的值无法派生出「2 小时前」，更无法支撑秒级的 `title="2026-08-02 14:03:11 +08:00"`。任何实现者照这句话去做，都只能被迫去别处取时间戳——而「别处」只有写入时间。

**错误二：那个「别处」正是我们刚刚排除的东西。** 写入时间（`last_checked_at` / bronze 落库时间）与业务时间是两个时钟，把它们并排放在同一个视觉分组里且不加标注，等于把 5.3 好不容易分开的两个概念又粘回去了，而且这次更隐蔽——它伪装成一个无害的友好提示。

**两者会朝着危险的方向背离**：相对时间衡量的是「我们上次碰这个源是什么时候」，不是「数据有多旧」。管道刚跑完，写入时间永远很新；而源可能自上周五起就没再发布。于是同一行里，「31 小时前」看着像一天前的数据，旁边的进度条却是「lag 2 交易日 · 超期 · 失败」。人眼先读到的是那个数字，结论是「还挺新」。**相对时间会系统性地把陈旧程度显示得比实际轻**，因为它测的是我们自己的勤奋程度，不是数据的年龄。

这正是本项目存在要反对的那类看板：每个数字单独看都没错，放在一起就骗人。

**生效规则**：健康区块（以及任何与新鲜度相邻的位置）**不渲染相对时间串**。该位置显示业务日期本身：

```
最后数据 07-31（周五）        lag 2 交易日 / 阈值 1 交易日
```

绝对业务日期与进度条同属一个时钟，不可能背离；周几用括号标出，因为「周五」是读者判断「跨了个周末」的关键信息，而这恰恰是交易日语义要传达的东西。

**写入时间不是没用，是放错了地方。** 「管道还活着吗」是一个真实且有用的问题，但它是**关于本次运行的一个事实，不是每个序列各一份**。因此它出现在运行头部，全局一处，措辞明确指向采集动作而非数据年龄：

```
上次采集完成 2026-08-02 14:03（+08:00）
```

来源为 `pipeline_runs.finished_at`，与 `series_health` 无关。两个问题分开问，分开答，各自用各自的时钟。

#### 5.3.2 SLA 进度条公式（渲染契约，模板不做计算）

进度条的全部数值由 `reporting/datapack.py` 预计算并放进 `HealthRow.freshness`，模板只做取值与渲染。公式与三个边界：

```
lag  = series_health.lag_trading_days       # 可为 NULL：从未成功采集
maxd = series_health.max_lag_trading_days   # 非空，检查时快照的阈值

# 边界 1：lag 为 NULL（state = unknown）-> 不渲染进度条
freshness = None if lag is None else FreshnessBar(
    # 边界 2：maxd 可能为 0（要求当天必须有数据），除零与零长度轨道都要避开
    bar_max   = max(maxd, 1),
    # 边界 3：超期时 lag > maxd，ARIA 要求 valuenow 落在 valuemin..valuemax 内
    bar_value = min(lag, max(maxd, 1)),
    overdue   = lag > maxd,
    label     = f"lag {lag} 交易日 / 阈值 {maxd} 交易日",
)
```

三条边界对应到 DOM：

| 情形 | `aria-valuenow` | `aria-valuemax` | 视觉 | 文本 |
|---|---|---|---|---|
| 正常 lag=0 maxd=1 | 0 | 1 | 空轨 | `lag 0 交易日 / 阈值 1 交易日` |
| 临界 lag=1 maxd=1 | 1 | 1 | 满轨，未超期配色 | `lag 1 交易日 / 阈值 1 交易日` |
| 超期 lag=3 maxd=1 | 1 | 1 | 满轨 + `overdue` 配色 + 状态图标降级 | `lag 3 交易日 / 阈值 1 交易日` |
| 当日要求 maxd=0，lag=1 | 1 | 1 | 满轨 + `overdue` | `lag 1 交易日 / 阈值 0 交易日` |
| 未知 lag=NULL | 不渲染进度条 | 不渲染 | `circle-dashed` + 空状态文案 | 由 `note` 提供具体原因 |

超期时 `aria-valuenow` 被夹到 `bar_max`（`3` 显示为 `1/1`）是 ARIA 规范要求，不是丢信息——真实滞后值始终在 `label` 文本里，而 `overdue` 标记保证屏幕阅读器与视觉用户都能感知「超了」而不只是「满了」。**进度条本身不承载超期幅度**：满轨即超期，超多少看文本。想用长度表达「超了 3 倍」是错的，那需要一个动态量程，而量程会让不同行之间无法横向比较。

`overdue` 与 `state` 是两件事，不可互相推导：`overdue` 只说滞后是否越线，`state` 还受 tier 与连续失败次数影响（见 5.2 tier 感知闸门）——`support` 档超期是 `degraded`，`risk_essential` 档超期才是 `blocked`。模板不得用 `overdue` 反推状态色，状态色只认 `state`。

---

## 六、抽象接口与插件机制

完整签名见 `docs/INTERFACES.md`。

### 6.1 接口清单

| 协议 / 基类 | 位置 | 关键方法 | 谁来实现 |
|------------|------|---------|---------|
| `BaseCollector` | `sources/base.py` | `fetch(window) -> Iterable[RawRecord]`、`capabilities()` | 内置 fixture/yahoo/fred；第三方数据源 |
| `Extractor` | `core/contracts.py` | `extract(BronzeRecord) -> list[SilverPoint]` | 每个源一个 |
| `QualityCheck` | `quality/base.py` | `run(QualityContext) -> list[QualityFinding]` | 内置 6 个；可扩展 |
| `PipelineStep` | `core/contracts.py` | `run(RunContext) -> StepResult`；元数据 `name/tier/depends_on` | 内置步骤；可扩展 |
| `BaseStrategy` | `decision/base.py` | `generate(MarketView) -> list[Signal]` | 玩具动量；使用者替换 |
| `SignalAggregator` | `decision/base.py` | `aggregate(list[Signal]) -> Decision` | 等权实现 |
| `LLMClient` | `analysis/client.py` | `complete(prompt, role) -> LLMResponse` | mock；使用者接真实 provider |
| `TradingCalendar` | `core/calendar.py` | `is_trading_day`、`trading_days_between`、`previous_trading_day` | YAML 实现；可替换 |
| `Clock` | `core/clock.py` | `now()`、`today()` | System / Frozen |
| `Renderer` | `reporting/renderer.py` | `render(DataPack) -> Path` | Jinja2 实现 |

设计要点：`BaseStrategy` 的唯一输入是 `MarketView`（只读投影），**策略拿不到数据库连接**。这既是安全边界，也保证策略可替换性（PRD AC-5）与可测试性。

### 6.2 插件机制：双轨

- **内置**：装饰器注册表 `@register_source("yahoo")` / `@register_step(...)`，import 时注册，简单直接。
- **第三方**：Python entry points，组名 `apexfin.sources`、`apexfin.checks`、`apexfin.strategies`。启动时用 `importlib.metadata.entry_points(group=...)`（Python 3.10+ 选择器 API）发现并加载，第三方包无需修改框架代码即可接入（PRD AC-4）。

安全与可诊断性：entry point 加载失败**不静默吞掉**，记录 warning 并在 `apexfin plugins list` 中显示 `[FAIL] <name>: <reason>`。`apexfin doctor` 会列出全部已发现插件与来源包名。详见 ADR-004。

---

## 七、质量保障

### 7.1 测试分层

| 层 | 范围 | 关键用例 |
|----|------|---------|
| 单元 | 各 check、extractor、calendar | 边界日期、跳空、去重键冲突 |
| 属性测试（hypothesis） | 日历、去重、增量窗口 | `trading_days_between` 的自反性与单调性；同一 payload 重复插入的幂等性 |
| 契约测试 | manifest / sources / silver_point 三个 JSON Schema | 配置文件必须通过 schema 校验 |
| 架构测试 | 依赖方向 | 见 7.3 |
| 端到端 | `make demo` 与 `make demo-stale` | 断言退出码、HTML 中出现降级文案、决策区为空 |

### 7.2 针对生成式代码高发失效模式的专项门禁

依据知识库 `01-standards/generated-code-failure-modes.md`：

| 失效模式 | 本项目的门禁 |
|---------|-------------|
| 幻觉依赖 | `uv.lock` + CI `uv sync --frozen`；所有版本号已实测存在 |
| 沉默逻辑错误 | 增量采集必须断言「本次运行后 `latest_event_date` 前进或明确记录未前进原因」（继承 APEXDATA 的 `latest_source_date` 防护）；空 DataFrame/空数组一律视为采集失败，不写 bronze |
| 异常吞噬 | `except Exception: pass` 由 Ruff 规则 `BLE`/`S110` 禁止；所有捕获必须重抛为 `ApexfinError` 子类或记录 finding |
| 边界未覆盖 | 空库、单条记录、跨年、闰日、非交易日运行进入必测清单 |
| 时间硬编码 | 禁止直接 `datetime.now()`；Ruff 自定义禁用规则 + code review，一律经 `Clock` |
| 新鲜度单位漂移 | `src/apexfin/**` 与 `config/**` 中禁止出现标识符 `lag_hours` / `sla_hours` / `sla_ratio`，命中即失败；`series_health` 与 `quality_findings` 的迁移 DDL 断言无小时类列。理由见 5.3.1 |

最后一条不是洁癖。小时制是这个领域最容易被「顺手加回来」的东西——某个源恰好是分钟级的，实现者会很自然地写一个 `lag_hours` 来表达它，于是同一张看板上同时存在两种新鲜度单位，而两者在周末的行为完全不同。真需要日内粒度时，正确做法是在交易日历上引入日内 session 概念，而不是在交易日语义旁边平行加一套小时语义。这条门禁扫的是 `src/` 与 `config/`，不扫 `docs/`（禁令声明文本必然包含被禁标识符，理由同 9.1 末的自指问题）。

### 7.3 依赖方向的机器校验

在 `tests/test_architecture.py` 中用 `ast` 解析 `src/apexfin/**/*.py` 的 import，对照允许矩阵断言：

```
core     -> {}                                   # 不得 import 任何 apexfin 子包
storage  -> {core}
sources|processing|quality|decision|analysis|accounting -> {core, storage}
pipeline -> {core, storage, L3 各包}
reporting-> {core, storage}
cli      -> 全部
L3 内部横向 import 一律禁止
```

同时断言：`src/apexfin/**/*.py` 无单文件超过 300 行（含空行与注释），超限即失败。

---

## 八、安全、合规与许可

### 8.1 一票否决项（对应 PRD AC-8）

APEXDATA 源码中实测存在两处**明文硬编码的真实 FRED API key**：`scripts/pipeline/fetch_fred.py` 第 22 行与 `scripts/pipeline/fetch_fred_regional.py` 第 23 行。处置要求：

1. APEXFIN 中 FRED key **只从环境变量 `APEXFIN_FRED_API_KEY` 读取**，缺失时 `fred` 源直接跳过并记录（demo 不依赖它）。
2. 该 key 已在私有仓库明文存在，**必须在 APEXDATA 侧吊销并重新签发**——这是独立于本项目的既有暴露，不能因为「新仓库没带过去」就认为已解决。
3. 开源前用 `gitleaks` 或等价工具全量扫描工作区与 git 历史；`.gitignore` 覆盖 `.env`、`*.db`、`data/`、`dist/`。APEXFIN 建议**全新 git init**，不从 APEXDATA 迁移历史，从根上避免历史泄露。

### 8.2 数据源合规（已裁决，生效约束）

> 状态：**RESOLVED**。裁决人 team-lead，2026-08-02，登记于 `docs/decisions/OPEN-DECISIONS.md` O-03，长期约束力条款已升格为 `docs/decisions/ADR-009-network-source-access-policy.md`。

Yahoo Finance 无公开数据 API 的商业使用授权，其服务条款限定个人非商业用途，且反对自动化批量抓取。APEXDATA 的 `fetch_yahoo.py` 中存在 **User-Agent 轮换 + 双 host 回退** 逻辑——这属于规避访问控制的特征，放进公开仓库会显著放大法律与平台风险，并且与本项目「诚实性」的价值主张自相矛盾。

生效的处置（架构方案 1 + 3 获采纳，方案 4 降级为文档化备选）：

1. **删除 UA 轮换与多 host 回退**，只保留单一公开端点、固定标识性 UA、保守速率（默认 ≥1.5 秒/请求）、遇 429 立即停止本源采集并记录 finding，不做绕过重试。
2. README 与 `sources/yahoo.py` 文件头写明：数据用途限个人研究与教育，使用者需自行遵守 Yahoo 服务条款，本项目不提供任何数据分发。
3. demo 默认路径**不访问 Yahoo**，走 committed fixture，因此 CI 与首次上手都不产生任何外部请求。
4. Stooq CSV 端点作为**文档化备选，MVP 不实现**。`BaseCollector` 抽象已使这个替换只影响一个文件，需要时再切。

落到代码上的可验证约束（S10 实现时逐条对照，CI 校验见 7.2）：

| # | 约束 | 校验方式 |
|---|------|----------|
| C1 | `sources/` 下不存在 UA 列表/池/轮换（无 `USER_AGENTS`、无随机选取 UA） | AST 门禁：`sources/` 内禁止对 `random` 的 import 与 `User-Agent` 字面量集合 |
| C2 | 每个网络源只允许一个 host 常量，禁止 host 数组与回退链 | 单测断言 `YahooCollector.HOST` 为 `str` 而非序列 |
| C3 | UA 为固定标识串 `apexfin/{version} (+https://github.com/<repo>)` | 单测断言 UA 含项目名与仓库地址，不含浏览器伪装串 |
| C4 | 收到 429/403 抛 `SourceBlocked`，`BaseCollector` 不重试、不换 host，直接结束本源并写 finding | 单测：mock 429，断言请求次数 == 1 且 `CollectResult.status == "blocked"` |
| C5 | 请求间隔下限 1.5 秒，配置可调大不可调小 | 单测：设 `min_interval=0.1` 时被夹到 1.5 |
| C6 | demo 默认路径零外部请求 | `make demo` 在 socket 被 monkeypatch 禁用的环境下仍需退 0 |

C4 与 `BaseCollector` 通用退避的关系：退避只对**网络层瞬时故障**（连接超时、5xx）生效，对**访问控制信号**（429/403）不生效。这条区分写进 `sources/base.py` 的类文档，避免后续实现者顺手把 429 并进重试集合。

FRED 有官方 API 与明确条款，需 key，合规无问题，作为可选源。

### 8.3 许可

项目取 MIT（PRD 锁定）。依赖许可全部兼容：Typer/pydantic/PyYAML/Jinja2/httpx/tenacity/structlog 为 MIT 或 BSD-3；ECharts 为 Apache-2.0；lucide-static 为 ISC。vendored 的 `echarts.min.js` 与 sprite 来源在 `NOTICE` 中标注。

一处提请注意（advisory，不阻塞）：MIT 不含专利授权条款，Apache-2.0 含。PRD 选 MIT 的理由是「与 Qlib 一致、fork 门槛低」，成立；此处仅作记录。

---

## 九、前端与图标方案（团队 P0 规则落地）

### 9.1 图标库锁定

**锁定 lucide-static 1.28.0（ISC 许可）**，全项目唯一图标来源。

落地方式：开发期用 `tools/build_sprite.py` 依据 `config/icons.yaml` 白名单，从 lucide-static 抽取所需图标，合并生成单一 `src/apexfin/reporting/static/icons/sprite.svg`（每个图标一个 `<symbol id="icon-xxx">`），**sprite 提交入库**。运行时零 npm、零网络、零构建步骤，纯静态 HTML 直接 `<svg><use href="#icon-alert-triangle"></use></svg>` 引用。

`config/icons.yaml` 的白名单内容以 `docs/DESIGN.md` 附录 A（Lucide 图标子集清单）为唯一来源，两处不得各自维护。设计侧已锁定的状态四态图标 `check-circle-2` / `alert-triangle` / `x-octagon` / `circle-dashed`，与 `series_health.state` 的四值枚举 `healthy` / `degraded` / `blocked` / `unknown` 一一对应（见 `docs/DATA_CONTRACT.md` 四）。映射关系在 `reporting/datapack.py` 中集中声明，模板不得自行判断状态到图标的对应。

**图标名可用性已实测（2026-08-02，OPEN-DECISIONS O-02 关闭依据）**：对 `lucide-static@1.28.0` 逐个拉取附录 A 全部 27 个图标名，**全部 HTTP 200，零缺失**，白名单可原样使用，无需改名。

实测中发现一件与直觉相反、必须写进文档的事：Lucide 的「旧名」并非全是新名的别名，有的是**几何不同的另一个图标**。

| 白名单名 | 现行新名 | 内容关系 | 结论 |
|---|---|---|---|
| `x-octagon` | `octagon-x` | 路径完全一致，仅 `class` 属性不同 | 真别名，用哪个都行 |
| `check-circle-2` | `circle-check-big` | **不同图形**：前者闭合圆 + 内含小对勾；后者开口弧 + 大对勾出框 | 保持 `check-circle-2`。状态列在 16px 下需要闭合外形与其余三态形状对齐，开口弧会显得「未完成」 |
| `alert-triangle` | `triangle-alert` | 路径一致，仅顶点顺序书写不同 | 真别名 |
| `table-2` | `table` | **不同图形**：前者缺角网格，后者矩形 + 三线网格 | advisory 交设计师：16px 下 `table` 可读性更好，但属视觉判断，不由架构侧改 |

因此「旧名 = 别名，可安全替换」这个假设不成立，`config/icons.yaml` 中的名字是**语义锁定值而非可自由归一化的字符串**，任何批量改名都必须逐个目视比对。

`tools/build_sprite.py` 的 fail-loud 约定（防止未来升级静默换图）：

1. 白名单中任一图标名在 lucide-static 包内不存在 -> 打印缺失清单，退出码 3（CONFIG），不生成任何产物。
2. sprite 头部写入生成用的 lucide-static 精确版本号；构建时若包版本与 `config/icons.yaml` 中 `lucide_version` 字段不符 -> 同样退 3。
3. 每个图标记录其 SVG 内容的 sha256 前 8 位到 `config/icons.lock`。升级 lucide 时哈希变化即在 diff 中显形，强制人工确认「是修了描边还是换了图形」。这一条正是上表 `check-circle-2` 情形的防线——没有它，一次版本升级就可能把状态图标悄悄换成另一个形状。

对比与理由：

| 候选 | 许可 | 判定 |
|------|------|------|
| lucide-static 1.28.0 | ISC | **选定**。提供纯 SVG 文件产物（非 React 组件），可离线抽取；线性风格与数据密集型看板匹配；1500+ 图标覆盖足够 |
| Feather 4.29.2 | MIT | 落选。lucide 本身是 Feather 的活跃 fork，Feather 更新已停滞 |
| Heroicons 2.2.0 | MIT | 落选。图标数量偏少，偏产品向，缺金融/数据类语义图标 |
| Tabler Icons 3.46.0 | MIT | 备选。数量最多，但体量与命名一致性略逊，且与 lucide 风格重叠 |

强制规则：
- **禁止 emoji 作为功能图标**——看板界面、README 功能列表、CLI 输出、日志、异常信息一律不用。CLI 状态用 `[PASS]` / `[FAIL]` / `[DEGRADED]` / `[SKIP]` 文字前缀。
- 禁止混用第二套图标集，禁止内联手写 SVG 路径绕过 sprite。
- CI 校验：`reporting/icons.py` 扫描全部模板中的 `#icon-*` 引用，任一 id 在 sprite 中不存在即失败；同时扫描模板与 Python 源码中的 emoji 码点，命中即失败。

#### P0 红线扫描器的设计约束（OPEN-DECISIONS O-06 落地）

Phase 1 门禁全量扫描暴露过一个必须一次性讲清的问题：扫描器会**被红线声明文本自身误伤**。22 个交付文件中 emoji 命中 0、弹跳缓动命中 0，但紫粉渐变命中 8 处、空洞文案命中 3 处，而这些命中**全部落在「禁止清单」的声明里**（`DESIGN.md` 自查清单、`design-tokens.json` 的 `denylist` 段、`PRD.md` 的 P0 约束表）——文档写「禁止 `#8B5CF6` 到 `#EC4899` 的渐变」，扫描器就在这句话里扫到了这两个色值。

处理方式是**把关系倒过来，而不是加排除名单**：

1. `design-tokens.json` 的 `denylist` 段是扫描器的**输入源**，不是扫描对象。CI 从 `denylist.hexValues` / `denylist.patterns` 读取禁令定义，再去扫描**产物与配置**——`src/apexfin/**`、`config/**`、`dist/**`。
2. `docs/**` 不在扫描目标内。声明禁令的文件天然不会被自己声明的禁令误伤，无需任何 `# noqa` 式的排除逻辑。
3. 需要校验文档时，只扫 emoji 码点这一类「文档里出现即错误、不可能作为声明文本出现」的规则，不扫色值与文案模式。

**为什么不用排除名单**：排除名单会腐化。一旦 CI 因红线清单自身而红灯且无法通过，团队的第一反应不是维护名单，而是放宽扫描规则——红线就此形同虚设。把 denylist 定为单一输入源，则「新增一条禁令」只需改一处数据、扫描器代码不动，且不存在自指。

这段写在这里而不是 CI 配置的注释里，是因为它是「为什么扫描器长这样」的根因。将来一定会有人看到扫描器不扫 `docs/` 而觉得是漏洞，然后把它改坏。

emoji 扫描的码点区间也有同类坑，一并锁定：**不得包含 `U+2190-U+21FF`（箭头块）**。初版扫描器把这段划进 emoji，导致文档里的 `->` 排版箭头被判为违规。生效区间为 `U+1F000-U+1FAFF`、`U+1F1E6-U+1F1FF`、`U+2600-U+26FF`、`U+2700-U+27BF`、`U+2B00-U+2BFF`、`U+FE0F`、`U+2049`、`U+203C`。文档与代码中表达「指向」一律用 ASCII `->`，不用 `U+2192` 全角箭头。

顺带记一个刚发生的实例，因为它比任何解释都直观：本段初稿在「不用全角箭头」这句话里写了一个全角箭头，被自查扫描当场抓出。这就是 O-06 所述自指问题的最小形态——**规则文本天然会包含它所禁止的东西**。解法不是给这行加豁免，而是改成用码点名称指代。同理，denylist 中的色值禁令也只能靠「不扫 `docs/`」来避免自指，不能靠豁免行号。

### 9.2 配色约束（架构侧硬约束，具体方案归设计师）

- **禁止紫色到粉色渐变**，任何渐变方向、任何透明度变体均禁止。该禁令的机器校验以 `docs/design-tokens.json` 的 `denylist.hexValues` 为唯一输入源，扫描目标只含 `src/apexfin/**`、`config/**`、`dist/**`，不含 `docs/**`，理由见 9.1 末「P0 红线扫描器的设计约束」。
- 基线遵循 PRD 的 Slate/Indigo 数据密集风。
- 状态表达**不得仅靠颜色**：健康 / 降级 / 阻断三态必须同时具备「文字标签 + 形状不同的图标 + 颜色」三重编码（WCAG 2.1 AA 与色盲可辨）。这条对模板是硬性的，`partials/health_badge.html` 需把三者绑定输出，不给调用方只传颜色的余地。

### 9.3 渲染契约

模板只能读 `DataPack`（`reporting/datapack.py` 组装的只读视图模型），**不允许在模板里访问 Repository 或做计算**。`autoescape=True` 全局开启。产物为单文件 `dist/dashboard.html`，CSS 内联、`echarts.min.js` 内联或同目录引用（默认内联以满足「双击可开」），目标 < 5 MB。

---

## 十、最小 Demo 链路

```
make demo
  = uv sync --frozen
 -> apexfin init --db ./data/apexfin.db
 -> apexfin run daily --manifest config/pipeline_manifest.yaml --fixture-pack fresh
      [collect]  fixture -> bronze_records
      [process]  bronze -> silver_points
      [quality]  6 checks -> findings -> gate: PASS
      [decide]   toy_momentum -> decisions
      [render]   -> dist/dashboard.html
 -> 打印: [PASS] pipeline completed in Xs, dashboard at dist/dashboard.html

make demo-stale
 -> apexfin run daily --fixture-pack stale
      [collect]  OK
      [process]  OK
      [quality]  check_freshness -> BLOCKING
                 stderr: [FAIL] freshness: source=fixture_equity symbol=SPY
                         latest_event_date=2026-07-20 lag=9 trading days
                         threshold=2 tier=risk_essential
      [decide]   SKIPPED (run state BLOCKED)
      [render]   degraded -> dist/dashboard.html
 -> 退出码 4
```

两条命令都不访问网络、不需要任何 key、结果确定性可复现（`Clock` 在 demo 模式下由 fixture pack 的元数据固定），因此 CI 可直接断言 HTML 内容。

---

## 十一、机器可读契约（openapi.yaml 偏离，已获准）

> 状态：**RESOLVED / 偏离获准**。裁决人 team-lead，2026-08-02，登记于 `docs/decisions/OPEN-DECISIONS.md` O-04。

角色规范默认要求产出 `openapi.yaml` 作为前后端契约。**本项目没有 HTTP API**——它是 CLI + 静态 HTML 产物，无服务端（PRD 十三明确 Out of Scope）。强行编造一个 OpenAPI 文件是形式主义且会误导实现方。

等价替代（已产出 / 待产出）：

| 契约 | 文件 | 作用 |
|------|------|------|
| 管道治理契约 | `contracts/manifest.schema.json` | manifest 结构的机器校验，CI 强制 |
| 数据源配置契约 | `contracts/sources.schema.json` | 符号/系列清单结构 |
| Silver 记录契约 | `contracts/silver_point.schema.json` | 跨层数据结构，第三方 extractor 对齐依据 |
| CLI 契约 | `docs/CLI_CONTRACT.md` | 命令、参数、退出码、输出格式（含 `--json` 机器可读模式） |
| 接口契约 | `docs/INTERFACES.md` | 全部 Protocol 签名 |

裁决要点：契约的作用是让双方对齐，载体形式服从项目形态；为满足模板编造一个不存在的 HTTP 契约会误导实现方去找不存在的服务端。若未来给看板加可选的本地只读 HTTP server（`apexfin serve`），届时再补 `openapi.yaml`——但这与「零服务」定位冲突，MVP 不做。

---

## 十二、技术风险与不可行警告

| # | 风险 | 等级 | 处置 |
|---|------|------|------|
| R1 | APEXDATA 明文 FRED key 已存在于私有仓库 | 高（安全） | 必须吊销重发；APEXFIN 全新 git init；开源前 gitleaks 扫描 |
| R2 | Yahoo TOS 与 UA 轮换/多 host 回退的规避特征 | 高（法律/声誉） | **已裁决关闭**（O-03 / ADR-009）：删除规避逻辑，单 host + 固定标识 UA + ≥1.5s 间隔 + 429 即停；demo 不走网络；README 免责；Stooq 记为文档化备选不实现。残余风险降至低，由 8.2 的 C1-C6 六条可测约束兜底 |
| R3 | 内置交易日历只覆盖 NYSE 且假日表需年更 | 中 | 文档诚实标注；提供 `TradingCalendar` 协议供替换；日历数据放 YAML 便于 PR 更新 |
| R4 | 「零 key 离线 demo」要求 fixture 数据入库 | 中 | fixture 用真实结构但小样本（每源 ≤ 200 条，总计 < 1 MB）；数据仅为公开市场行情片段，不含任何私有信息 |
| R5 | 60 秒全链路预算 | 中 | 已通过排除 pandas 与网络调用规避主要风险；CI 加耗时断言，超时红灯 |
| R6 | 从 APEXDATA 迁移质量检查时可能夹带个人化阈值 | 中 | 所有阈值外置到 `expectations.yaml`，代码内不留魔数；逐文件人工复核，见 `docs/ALPHA_BOUNDARY.md` |
| R7 | 多角色 AI 框架（F13）易被误解为「能自动投资」 | 中 | 只交付 prompt 契约 + 确定性 mock；角色卡与 README 显式声明非投资建议 |
| R8 | 观点对账（F11）需要未来行情才能判定，demo 内看不到闭环 | 低 | fixture 中预置一段历史区间，使 demo 能展示已结算的对账记录 |

**明确的不可行项**：在「零 API key + 离线 + 60 秒」约束下，**无法**用真实 Yahoo/FRED 网络采集作为 demo 默认路径。这不是实现难度问题，是约束冲突。解法即上文的 fixture pack 方案，网络采集降级为 `apexfin collect --source yahoo` 的可选进阶路径。此点需 PM 知悉：README 首屏截图展示的是 fixture 数据，需要在图注中诚实标注。

---

## 十三、实施顺序（对齐 PRD 依赖拓扑）

```
S0 骨架    pyproject + core/（contracts/models/errors/clock/calendar/config/logging/registry）
S1 存储    storage/（engine/migrator/0001_init.sql/repos）
S2 采集    sources/base + fixture（含 fresh/stale 两套样本）
S3 归一    processing/
S4 治理    quality/ 6 checks + gate + expectations.yaml     <- 差异化核心，投入最多
S5 编排    pipeline/（manifest + planner + runner + steps）
S6 决策    decision/（base + views + toy_momentum + aggregator）
S7 渲染    reporting/（datapack + templates + sprite + 正常态/降级态）
S8 CLI     cli/（装配 + 各子命令 + doctor）
S9 演示    Makefile demo / demo-stale + 端到端测试
S10 网络源 sources/yahoo + fred（可选路径，不阻塞 demo）
S11 CI     GitHub Actions + 架构测试 + 图标校验
S12 文档   README 双语 + 首屏对比截图
```

S4 与 S7 的降级态是本项目全部说服力所在，不得为赶进度削减。
