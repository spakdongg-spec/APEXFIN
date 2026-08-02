# ADR-003: CLI 框架选用 Typer

## Status

Accepted (2026-08-02) — 高见远

## Background

CLI 是 APEXFIN 唯一的对外接口（无 HTTP API，PRD 十三）。它同时承担三个职责：人类交互入口、CI 断言目标（`make demo-stale` 必须返回退出码 4）、以及依赖注入的装配点（Composition Root）。

候选：Typer 0.27.0、Click 8.4.2、argparse（标准库）、Fire、cleo。

## Decision

采用 **Typer 0.27.0**。

| 候选 | 参数声明方式 | 子命令 | 类型安全 | 判定 |
|------|------------|-------|---------|------|
| Typer 0.27.0 | 函数类型注解即声明 | 原生 | 与 mypy strict 兼容良好 | **选定** |
| Click 8.4.2 | 装饰器堆叠 | 原生 | 参数类型需重复声明 | 落选：Typer 是它的上层封装，能力不丢 |
| argparse | 手写 parser | 需手工 subparsers | 无 | 落选：样板代码多，与 mypy 配合差 |
| Fire | 反射自动暴露 | 隐式 | 无 | 落选：接口边界不可控，不适合作为契约 |
| cleo | 类式定义 | 原生 | 一般 | 落选：生态与文档量远小于 Click 系 |

Typer 建立在 Click 之上，需要 Click 原语时可直接下探，不存在能力天花板。类型注解即参数声明这一点，对「单文件 ≤ 300 行」的约束帮助明显：一个子命令文件通常 40-80 行即可完成。

配套约束：
- `cli/app.py` 是唯一装配点，负责构造 `CliContext`（Clock、Calendar、Settings、ConnectionFactory、注册表）并注入。任何深层模块不得自行导入具体实现。
- 每个子命令独立文件（`cmd_collect.py` 等），只做参数解析与调用，业务逻辑一律下沉。
- 输出层 `cli/output.py` 统一格式：`[PASS]` / `[FAIL]` / `[DEGRADED]` / `[SKIP]` / `[BLOCKED]` 文字前缀，**禁止 emoji**（团队 P0 规则）。
- `--json` 模式下 stdout 只输出一个 JSON 对象，日志全部走 stderr，否则 CI 无法解析。
- 退出码契约见 `docs/CLI_CONTRACT.md` 二。退出码是本项目对外最硬的契约，改动等同破坏性变更。

## Consequences

正面：
- 帮助文本、shell 补全自动生成，降低 P2/P3 用户的上手摩擦。
- 类型注解让 mypy 能覆盖 CLI 层，减少参数类型相关的运行时错误。
- `rich` 经 Typer 传递引入，表格输出免费获得，不额外计入依赖预算的顶层数量。

负面：
- Typer 处于 0.x，次版本可能含破坏变更。缓解：版本约束锁 `>=0.27.0,<0.28`，`uv.lock` 固定精确版本，CI 覆盖全部子命令的 smoke test。
- 类型注解驱动的参数声明在复杂场景（互斥参数组）表达力弱于手写 Click。缓解：本项目参数结构简单，若遇到可下探 Click 原语。

## Related ADRs

ADR-001（uv/hatchling 提供 `apexfin` 入口点）
