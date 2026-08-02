# APEXFIN CLI 契约

| 项目 | 内容 |
|------|------|
| 文档 | CLI_CONTRACT.md |
| 版本 | v1.2 |
| 撰写 | 高见远（首席架构师） |
| 日期 | 2026-08-02 |
| 说明 | 本项目无 HTTP API（PRD 十三 Out of Scope）。CLI 即对外接口，本文是它的契约，地位等同于 OpenAPI 之于 Web 服务。偏离说明见 `docs/ARCHITECTURE.md` 十一 |

### 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-02 | 初版 |
| v1.1 | 2026-08-02 | O-12：指定 `--fixture-pack` 时时钟冻结到该包 `_meta.json` 的 `as_of`，优先级为显式 `--as-of` > pack `meta.as_of` > 系统时钟，保证 `make demo-stale` 的退 4 断言可复现 |
| v1.2 | 2026-08-02 | 退出码口径修正：`make demo-stale` 底层命令退 4 但 make 层退 2（make 对失败目标的语义）；CI 机械断言改走 SPEC §9.1 裸命令（真 4 + BLOCKED 双断言），make 目标降为人类演示入口（O-12 裁决推论） |
---

## 一、全局约定

```
apexfin [GLOBAL OPTIONS] COMMAND [ARGS]
```

| 全局选项 | 默认 | 说明 |
|---------|------|------|
| `--db PATH` | `./data/apexfin.db` | SQLite 路径，也可用 `APEXFIN_DB` 环境变量 |
| `--config PATH` | `./config` | 配置目录 |
| `--log-level LEVEL` | `info` | `debug` / `info` / `warning` / `error` |
| `--json` | off | 输出机器可读 JSON（用于 CI 断言与脚本消费） |
| `--as-of DATE` | 系统日期 | 注入 `FrozenClock`，用于测试与复现 |
| `--dry-run` | off | 只规划不写库，打印将要执行的步骤与顺序 |
| `--version` | — | 打印版本后退出 |

配置优先级（低到高）：代码默认值 < `config/*.yaml` < 环境变量（前缀 `APEXFIN_`）< CLI 参数。

时钟冻结优先级（O-12）：显式 `--as-of` > 指定 `--fixture-pack` 时该包 `_meta.json` 的 `as_of` > 系统时钟。带 `--fixture-pack` 的裸跑因此与墙钟无关，`make demo-stale` 的退 4 断言可复现。

**密钥只能来自环境变量**，YAML 中出现疑似密钥的键（`*_key`、`*_token`、`*_secret`）时启动即报错退出码 3。

---

## 二、退出码契约

CI 与脚本依赖这张表，改动即破坏契约。

| 码 | 名称 | 含义 |
|----|------|------|
| 0 | OK | 成功。gate 为 PASS 或 DEGRADED |
| 1 | RUNTIME_ERROR | 未预期的内部错误（bug） |
| 2 | USAGE_ERROR | 参数错误（Typer/Click 标准） |
| 3 | CONFIG_ERROR | 配置缺失、密钥位置错误、迁移 checksum 不符 |
| 4 | QUALITY_BLOCKED | 质量闸门判定 BLOCKED，下游被阻断（`make demo-stale` 的预期码） |
| 5 | SOURCE_UNAVAILABLE | 全部数据源采集失败（单源失败不触发此码） |
| 6 | MANIFEST_INVALID | manifest 校验失败：双向不一致 / 有环 / schema 不符 / `why` 为空 |

DEGRADED 不占用独立退出码，退 0——因为它是「有产出但有缺失」，脚本层面属成功；状态通过 `--json` 输出的 `gate.verdict` 字段与看板降级态传达。

---

## 三、输出格式

### 3.1 人类可读

状态一律文字前缀，**禁止 emoji**：

```
[PASS]      通过
[FAIL]      失败
[DEGRADED]  降级
[SKIP]      跳过
[BLOCKED]   被闸门阻断
```

失败输出必须回答三问：什么坏了、观测值是多少、期望值是多少。

```
[FAIL] freshness: source=fixture_equity symbol=SPY
       observed: latest_event_date=2026-07-20, lag=9 trading days
       expected: lag <= 2 trading days (tier=risk_essential)
       action:   run `apexfin collect --source fixture_equity` or check upstream
```

### 3.2 机器可读（`--json`）

统一信封，便于 CI 断言：

```json
{
  "ok": true,
  "command": "run",
  "run_id": "20260802T031500Z-7f3a",
  "exit_code": 0,
  "gate": {
    "verdict": "PASS",
    "blocking": [],
    "degraded_sources": []
  },
  "steps": [
    {"name": "collect", "status": "OK", "duration_s": 1.82,
     "metrics": {"inserted": 412, "duplicates": 0, "revisions": 0}}
  ],
  "artifacts": {"dashboard": "dist/dashboard.html"},
  "warnings": []
}
```

`--json` 模式下 stdout 只有这一个 JSON 对象，所有日志走 stderr。这条规则不可破，否则 CI 无法解析。

---

## 四、命令清单

### `apexfin init`

```
apexfin init [--db PATH] [--force]
```
创建数据库与目录结构，执行全部迁移，写入 `schema_migrations`。已存在且 schema 最新时为幂等空操作；`--force` 才允许重建。

### `apexfin collect`

```
apexfin collect [--source NAME]... [--symbol SYM]... [--full]
                [--since DATE] [--fixture-pack {fresh,stale}]
```
- 不传 `--source` 则采集 `sources.yaml` 中启用的全部源。
- 单源失败不中断其它源（PRD 九·边界条件），失败写入 warnings 并在末尾汇总。
- 全部源失败 -> 退出码 5。
- 输出 `UpsertStats`：inserted / duplicates / revisions。**inserted 与 duplicates 同时为 0 视为异常**，产生 WARNING finding（防静默失效）。

### `apexfin process`

```
apexfin process [--full] [--source NAME]...
```
bronze -> silver。默认增量（只处理未构建的 bronze 行）；`--full` 全量重建。

### `apexfin quality`

```
apexfin quality [--check ID]... [--strict]
```
运行质量检查并写入 findings 与 series_health，打印裁决。`--strict` 把 DEGRADED 也视为失败（退 4），供偏执场景使用。

### `apexfin decide`

```
apexfin decide [--strategy NAME] [--horizon-days N]
```
默认 `toy_momentum`。gate 为 BLOCKED 时拒绝执行并退 4；DEGRADED 时只对健康 series 产出，其余写 `no_call`。

### `apexfin render`

```
apexfin render [--out PATH] [--degraded]
```
默认输出 `dist/dashboard.html`。`--degraded` 强制降级态渲染；不传时按当前 run 的 gate 状态自动决定。

### `apexfin run`

```
apexfin run daily [--manifest PATH] [--fixture-pack {fresh,stale}]
                  [--only STEP]... [--skip STEP]... [--continue-on-error]
```
按 manifest 编排执行完整链路。`--only` / `--skip` 用于单步重跑（保留依赖检查：`--only decide` 时若上游未就绪会报错而非静默跑空）。

### `apexfin manifest`

```
apexfin manifest validate [--manifest PATH]
apexfin manifest show [--tier TIER]
```
`validate` 执行四条断言（见 ARCHITECTURE 5.2），失败退 6 并列出全部差异项。`show` 按 tier 过滤展示，是「管道瘦身」的日常工具。

### `apexfin plugins`

```
apexfin plugins list
```
列出内置与第三方注册项，来源包名，加载失败原因：

```
sources:
  [PASS] fixture_equity   builtin
  [PASS] yahoo            builtin
  [PASS] fred             builtin
  [FAIL] my_broker        my-pkg 0.3.1: ImportError: no module named 'ibapi'
  [SKIP] yahoo            other-pkg 1.0: shadowed by builtin
```

### `apexfin doctor`

```
apexfin doctor [--validate-extractors]
```
环境自检：Python 版本、依赖版本、DB 可写与 schema 版本、迁移 checksum、配置文件 schema 校验、日历覆盖年份、插件发现结果、密钥存在性（**只报告存在与否，绝不打印值**）、sprite 图标引用完整性。

---

## 五、Makefile 目标（demo 的稳定入口）

| 目标 | 等价命令 | 预期退出码 |
|------|---------|-----------|
| `make demo` | `uv sync --frozen && apexfin init && apexfin run daily --fixture-pack fresh` | 0 |
| `make demo-stale` | `uv sync --frozen && apexfin run daily --fixture-pack stale` | 底层 4（make 层 2） |
| `make test` | `pytest -q` | 0 |
| `make lint` | `ruff check . && ruff format --check .` | 0 |
| `make typecheck` | `mypy src/apexfin` | 0 |
| `make sprite` | `python tools/build_sprite.py` | 0 |

**退出码口径（2026-08-02 实测修正）**：`make demo-stale` 的**底层命令** `apexfin run daily --fixture-pack stale` 退 4（freshness 闸门 BLOCKED）；但 **make 对失败目标自身返回 2**（make 语义：目标命令非零即 Error 并退 2，实测输出 `make: *** [demo-stale] Error 4`）。因此 **CI 机械断言必须走 SPEC §9.1 的裸命令** `apexfin run daily --fixture-pack stale; echo $?`（真 4 + `SELECT state ... = BLOCKED` 双断言），make 目标仅作人类演示入口，不参与机械断言（O-12 裁决）。若 `make demo-stale` 返回 0 或底层命令退 0，说明闸门被改坏——这是差异化回归测试的守卫点，无论走 make 还是裸命令都不可变。

