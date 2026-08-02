# APEXFIN 数据契约

| 项目 | 内容 |
|------|------|
| 文档 | DATA_CONTRACT.md |
| 版本 | v1.0 |
| 撰写 | 高见远（首席架构师） |
| 日期 | 2026-08-02 |
| 引擎 | SQLite 3.35+（`RETURNING` 与 `DROP COLUMN` 需要；Python 3.11 自带的 sqlite3 满足） |
| 单一真源 | `src/apexfin/storage/migrations/0001_init.sql` |

---

## 一、总体约定

| 约定 | 规则 |
|------|------|
| 命名 | 表名蛇形复数；列名蛇形单数 |
| 主键 | `id INTEGER PRIMARY KEY`（SQLite rowid 别名，写入最快） |
| 时间存储 | 一律 UTC。`*_time` 存 ISO-8601 字符串 `YYYY-MM-DDTHH:MM:SSZ`；`*_date` 存 `YYYY-MM-DD` |
| 为什么同时存 time 和 date | `event_date` 是交易日键，被新鲜度/连续性检查高频比对与索引；从 `event_time` 现算会阻止索引命中 |
| 浮点 | `REAL`。价格不做定点化——本项目不做撮合与结算，精度需求不成立 |
| 布尔 | `INTEGER` 0/1，附 `CHECK` 约束 |
| 外键 | 显式声明，连接时 `PRAGMA foreign_keys=ON` |
| 软删除 | 不使用。数据管道的正确语义是修订留痕，不是删除 |
| 迁移 | 顺序编号 SQL 文件，`schema_migrations` 记录已应用版本，只前进不回滚 |

连接期 PRAGMA（`storage/engine.py`）：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;      -- 读写不互相阻塞
PRAGMA synchronous = NORMAL;    -- WAL 下的合理折中
PRAGMA busy_timeout = 5000;     -- 锁等待 5s 后 fail-loud，不无限挂起
```

---

## 二、Bronze 层

```sql
CREATE TABLE bronze_records (
    id            INTEGER PRIMARY KEY,
    source_name   TEXT    NOT NULL,
    domain        TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,           -- business time, UTC ISO-8601
    event_date    TEXT    NOT NULL,           -- trading-day key, YYYY-MM-DD
    payload       TEXT    NOT NULL,           -- raw upstream body as JSON text
    payload_hash  TEXT    NOT NULL,           -- sha256 of canonical JSON
    revision      INTEGER NOT NULL DEFAULT 0,
    source_url    TEXT,
    run_id        TEXT    NOT NULL,
    ingested_at   TEXT    NOT NULL,           -- wall-clock write time
    UNIQUE (source_name, symbol, event_time)
);

CREATE INDEX idx_bronze_series_date
    ON bronze_records (source_name, symbol, event_date DESC);
CREATE INDEX idx_bronze_run
    ON bronze_records (run_id);
```

写入语义（`bronze_repo.upsert`）：

1. 计算 `payload_hash`（对 payload 做 key 排序的规范化 JSON 再 sha256）。
2. 按 `(source_name, symbol, event_time)` 查已有行：
   - 不存在 -> INSERT，`revision=0`，`stats.inserted += 1`
   - 存在且 hash 相同 -> 跳过，`stats.duplicates += 1`（幂等，对应 PRD「重复运行同一天」）
   - 存在且 hash 不同 -> 把旧行快照写入 `bronze_revisions`，UPDATE 主表，`revision += 1`，`stats.revisions += 1`
3. 返回 `UpsertStats`。调用方据此判断本次运行是否真的产生了进展。

```sql
CREATE TABLE bronze_revisions (
    id             INTEGER PRIMARY KEY,
    bronze_id      INTEGER NOT NULL REFERENCES bronze_records(id) ON DELETE CASCADE,
    revision       INTEGER NOT NULL,
    payload        TEXT    NOT NULL,
    payload_hash   TEXT    NOT NULL,
    superseded_at  TEXT    NOT NULL,
    run_id         TEXT    NOT NULL
);

CREATE INDEX idx_bronze_rev_parent ON bronze_revisions (bronze_id, revision DESC);
```

`bronze_revisions` 的存在理由：FRED 会修订历史宏观数据，Yahoo 会调整分红拆股后的复权价。覆盖写会让「昨天的结论基于什么数据」永久不可考——这与项目的诚实性主张直接冲突。

---

## 三、Silver 层

```sql
CREATE TABLE silver_points (
    id              INTEGER PRIMARY KEY,
    bronze_id       INTEGER REFERENCES bronze_records(id) ON DELETE SET NULL,
    source_name     TEXT    NOT NULL,
    domain          TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    event_time      TEXT    NOT NULL,
    event_date      TEXT    NOT NULL,
    value           REAL    NOT NULL,
    value_secondary REAL,
    unit            TEXT,
    quality_score   REAL    NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
    is_filled       INTEGER NOT NULL DEFAULT 0 CHECK (is_filled IN (0, 1)),
    payload_json    TEXT,
    run_id          TEXT    NOT NULL,
    built_at        TEXT    NOT NULL,
    UNIQUE (source_name, symbol, event_time)
);

CREATE INDEX idx_silver_series_date
    ON silver_points (source_name, symbol, event_date DESC);
CREATE INDEX idx_silver_domain_date
    ON silver_points (domain, event_date DESC);
```

`quality_score` 计算（`processing/quality_score.py`）：

```
score = source_reliability * staleness_factor * completeness_factor

source_reliability : 每源常量，配置在 sources.yaml（官方 API 1.0，非官方端点 0.9，衍生计算 0.85）
staleness_factor   : max(0, 1 - lag_trading_days / max_lag_trading_days * 0.5)
completeness_factor: 1.0 若字段齐全；0.8 若 value_secondary 缺失且该源本应提供
```

`is_filled=1` 的行必须由显式的填充步骤产生，且在看板上带可见标记。**任何静默前向填充都是被禁止的**——这正是 PRD 痛点 1 的典型成因。

---

## 四、质量层

```sql
CREATE TABLE quality_findings (
    id           INTEGER PRIMARY KEY,
    run_id       TEXT NOT NULL,
    check_id     TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','BLOCKING')),
    tier         TEXT NOT NULL CHECK (tier IN
                   ('risk_essential','support','display_only','research')),
    source_name  TEXT NOT NULL,
    symbol       TEXT,
    message      TEXT NOT NULL,
    observed     TEXT,
    expected     TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX idx_findings_run      ON quality_findings (run_id, severity);
CREATE INDEX idx_findings_source   ON quality_findings (source_name, created_at DESC);

CREATE TABLE series_health (
    source_name           TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    last_event_date       TEXT,
    lag_trading_days      INTEGER,
    max_lag_trading_days  INTEGER NOT NULL CHECK (max_lag_trading_days >= 0),
    state                 TEXT NOT NULL CHECK (state IN ('healthy','degraded','blocked','unknown')),
    last_checked_at       TEXT NOT NULL,
    consecutive_fails     INTEGER NOT NULL DEFAULT 0,
    note                  TEXT,
    PRIMARY KEY (source_name, symbol)
);
```

`series_health` 是看板顶部健康度区块的直接数据源，也是「哪个源该被换掉」的历史依据（PRD 十一·B 的 `freshness_gate_triggered` 事件由 `quality_findings` 承载，健康快照由本表承载）。

#### 为什么 `max_lag_trading_days` 要落表，而不是渲染时读 `expectations.yaml`

这个字段是本轮新增的（依据 OPEN-DECISIONS O-07），值来自 `expectations.yaml` 中该 `(source, frequency)` 的阈值，但**在质量检查执行的那一刻快照写入**，不是渲染时现查。两个理由：

**一、判定结果与判定依据分离，等于判定不可复现。** 表里存着 `lag_trading_days = 2, state = 'degraded'`，而有人后来把 `expectations.yaml` 的阈值从 1 改成 3。此后任何人读这行历史记录都会得出「lag 2 没超过阈值 3，为什么是 degraded」的困惑，而这行记录本身无法自证。一个以数据诚实性为主张的项目，自己的健康快照表不能是这种「结论在库里、依据在别处且会漂移」的结构。阈值随判定一起落盘，这行记录才是自洽的、可离线复核的。

**二、渲染层不应认识治理层的配置格式。** 若 `reporting/datapack.py` 在组装时去解析 `expectations.yaml`，则 `reporting/` 就耦合了 `quality/` 的配置结构——阈值配置改个键名，看板跟着坏。这违反 L3 各领域包互不认识的铁律（见 ARCHITECTURE 2.1）。落表之后，DataPack 只走存储端口读 `series_health`（L5 -> L2，合法路径），不碰任何 YAML。

成本是一个 INTEGER 列。收益是历史可解释 + 少一条跨层耦合，这笔账不用算。

`NOT NULL` 的取舍：即使 `state = 'unknown'`（从未成功采集、`lag_trading_days` 为 NULL），阈值本身仍然是已知的——它来自配置而非观测。所以阈值列非空，滞后列可空。这个不对称是有意的，它准确表达了「我们知道要求是什么，但还不知道现状」。

#### 阈值从哪来：`expectations.yaml` 的 `defaults` 段必填（O-09）

「阈值永远已知」成立的前提是「阈值来自配置」。为堵死「配置里没有、代码默认值补上」的隐形路径，`config/expectations.yaml` 的加载契约如下：

1. **顶层 `defaults:` 段必填**，且必须显式给出全部 4 个数值键：`max_lag_trading_days` / `completeness_window_days` / `max_missing_trading_days` / `max_gap_trading_days`。缺段或缺键时 `load_expectations()` 抛 `ConfigError` 并**指名缺哪个键**（fail-loud，退 3）。
2. **dataclass 默认值职责降级**：`SourceExpectation` 的默认值仅作「测试直接构造对象时的类型兜底」，加载路径永不依赖它。不要因为「字段有默认值」就认为可以不在 YAML 里写。
3. **落表写最终生效值**：`series_health.max_lag_trading_days` 存 `for_series()` 解析后的生效值（源级/序列级覆盖后的结果），不是 YAML 字面值。生效优先级：序列级 `symbols` 覆盖 > 源级覆盖 > `defaults`。
4. **DDL `NOT NULL CHECK (>= 0)` 不变**——判定依据必须在库里可自证，这正是本表存阈值快照的原因。

反向约束同样成立：源级覆盖可放宽或收紧阈值（如 `fixture_equity` 用 1、`fixture_macro` 用 5），但**不可新增配置里没有的键**——`_merge` 对未知键（含小时制键）直接抛 `ConfigError`（ARCHITECTURE 5.3.1 的机制保障）。

---

## 五、运行与自观测

```sql
CREATE TABLE pipeline_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    state         TEXT NOT NULL CHECK (state IN
                    ('RUNNING','PASS','DEGRADED','BLOCKED','FAILED')),
    manifest_hash TEXT NOT NULL,          -- 治理配置的指纹，便于复盘
    fixture_pack  TEXT,                   -- 'fresh' / 'stale' / NULL(real sources)
    as_of_date    TEXT NOT NULL,          -- clock.today() at run start
    exit_code     INTEGER,
    summary       TEXT
);

CREATE TABLE step_runs (
    id          INTEGER PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    step_name   TEXT NOT NULL,
    tier        TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('OK','FAILED','SKIPPED')),
    started_at  TEXT NOT NULL,
    duration_s  REAL NOT NULL,
    message     TEXT,
    metrics     TEXT                       -- JSON: {"inserted": 42, "duplicates": 3}
);

CREATE INDEX idx_step_runs_run ON step_runs (run_id);
CREATE INDEX idx_step_runs_perf ON step_runs (step_name, duration_s DESC);
```

`idx_step_runs_perf` 的用途很具体：回答「哪一步最慢、值不值得每天跑」，为 manifest tier 降级提供数据依据，而不是靠感觉删步骤。

---

## 六、Gold 层：决策与对账

```sql
CREATE TABLE decisions (
    id            INTEGER PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    as_of_date    TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    stance        TEXT NOT NULL CHECK (stance IN ('long','short','flat','no_call')),
    confidence    REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    strategy      TEXT NOT NULL,
    rationale     TEXT NOT NULL,
    inputs_json   TEXT NOT NULL,           -- the exact numbers behind the call
    degraded      INTEGER NOT NULL DEFAULT 0 CHECK (degraded IN (0,1)),
    created_at    TEXT NOT NULL,
    UNIQUE (run_id, symbol, strategy)
);

CREATE TABLE opinion_ledger (
    id              INTEGER PRIMARY KEY,
    decision_id     INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    stated_on       TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,
    due_on          TEXT NOT NULL,
    stance          TEXT NOT NULL,
    reference_value REAL NOT NULL,          -- price at statement time
    settled_on      TEXT,
    settled_value   REAL,
    outcome         TEXT CHECK (outcome IN ('hit','miss','void','pending')),
    settled_note    TEXT
);

CREATE INDEX idx_ledger_due ON opinion_ledger (due_on) WHERE outcome = 'pending';
```

`stance='no_call'` 是一等公民：数据被闸门拦下时，决策层写入 `no_call` 并记明原因，**而不是不写记录**。不写记录等于允许事后假装当天没表过态——这与 PRD 的观点对账主张冲突。

`opinion_ledger.outcome='void'` 用于「到期日行情缺失」这类无法判定的情形，不允许把不可判定的记录静默丢弃。

---

## 七、迁移表

```sql
CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL,
    checksum    TEXT NOT NULL          -- sha256 of the migration file
);
```

`migrator.py` 启动时校验：已应用迁移的 checksum 与磁盘文件不一致 -> 立即报错退出（退出码 3），不尝试自愈。改历史迁移是团队协作中最隐蔽的破坏行为之一，必须 fail-loud。

---

## 八、与 APEXDATA 的差异对照

| APEXDATA | APEXFIN | 变更理由 |
|----------|---------|---------|
| `raw_events` + `bronze_records` 两张原始表 | 合并为 `bronze_records` | `raw_events` 与 `bronze_records` 的字段高度重叠，双写增加一致性检查负担；参考实现要降低阅读成本 |
| `apexdata.db` + `apexdata_daily.db` 双库 | 单库 | 30 天滚动快照的运维价值不适用于参考实现；跨库一致性是纯粹的额外复杂度 |
| `silver_extracted` | `silver_points` | 命名去掉过程词，改为描述内容 |
| `ingestion_runs` | `pipeline_runs` + `step_runs` | 拆分粒度，支持「按步骤统计耗时」这一 tier 治理的数据依据 |
| `data_quality_checks` | `quality_findings` | 语义从「检查记录」改为「发现的问题」，空结果不写行，表更小更可读 |
| `macro_hypotheses` + `falsification_log` | `opinion_ledger`（合并简化） | 抽 alpha 后不保留宏观假设的领域细节，只保留通用的「观点—到期—判定」骨架 |
| 30+ 张业务表 | 不迁移 | 属于用户私有业务与 alpha，见 `docs/ALPHA_BOUNDARY.md` |

---

## 九、契约校验

`contracts/silver_point.schema.json` 定义 SilverPoint 的 JSON Schema，用于：
1. 第三方 extractor 的输出自检（`apexfin doctor --validate-extractors`）；
2. fixture 样本文件的 CI 校验；
3. 未来若增加导出功能，作为导出格式的稳定契约。

`contracts/manifest.schema.json` 与 `contracts/sources.schema.json` 在 CI 中对 `config/*.yaml` 强制校验，校验失败退出码 6。
