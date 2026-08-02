# ADR-001: 用 uv + hatchling 做包管理与构建

## Status

Accepted (2026-08-02) — 高见远

## Background

APEXFIN 有一条硬指标：从 `git clone` 到看到看板 < 5 分钟，含依赖安装（PRD 十·NFR、AC-1）。同时 PRD 要求依赖版本锁定、CI 在纯净环境可复现。APEXDATA 用的是裸 `requirements.txt`，无 lockfile，无法保证跨机器一致。

候选：uv、Poetry、PDM、pip-tools + venv、裸 pip + requirements.txt。

## Decision

采用 **uv 0.12.1** 作为环境与依赖管理器，**hatchling 1.31.0** 作为 PEP 517 构建后端，`pyproject.toml` 用 PEP 621 标准元数据，`uv.lock` 提交入库，CI 用 `uv sync --frozen`。

`requires-python = ">=3.11,<3.15"`。3.10 于 2026-10-31 EOL，排除；上限锁定防止未来主版本破坏。CI 矩阵覆盖 3.11 / 3.12 / 3.13 / 3.14。

| 候选 | 解析安装速度 | lockfile | 元数据标准 | 判定 |
|------|-------------|---------|-----------|------|
| uv 0.12.1 | 最快（Rust 实现，缓存命中时秒级） | `uv.lock`，跨平台 | PEP 621 原生 | **选定** |
| Poetry | 慢，解析器是历史痛点 | `poetry.lock` | 早期私有段，现支持 PEP 621 | 落选：速度直接冲击 5 分钟指标 |
| PDM | 中等 | `pdm.lock` | PEP 621 原生 | 落选：生态与文档量不及 uv |
| pip-tools | 中等 | `requirements.txt` 编译产物 | 需另配构建后端 | 落选：多工具拼装，贡献者心智成本高 |
| 裸 pip | 中等 | 无 | 无 | 落选：不满足可复现性要求 |

构建后端选 hatchling 而非 setuptools：无 `setup.py`、无私有配置段、`src/` 布局开箱支持，配置文件更短——对一个「要给人读」的参考实现，配置的可读性本身就是交付物的一部分。

## Consequences

正面：
- 冷缓存下 `uv sync` 通常在 10 秒量级完成，为 5 分钟指标留出充足余量。
- `uv.lock` 含哈希，CI 与本地强一致，同时挡住供应链替换风险。
- `uv run` 免去 venv 激活步骤，README 的上手路径少一步。
- PEP 621 元数据可被任何符合标准的工具读取，未来换工具不需要重写 `pyproject.toml`。

负面：
- uv 仍是快速演进的工具，0.x 版本号意味着可能有破坏性变更。缓解：在 CI 与文档中锁定 uv 版本，并保证 `pip install -e .` 作为兜底路径始终可用（hatchling 保证了这一点）。
- 部分用户不熟悉 uv。缓解：README 同时给出 `uv sync` 与 `pip install -e .` 两条路径，后者标注为「较慢但通用」。

## Related ADRs

ADR-008（运行时不引入 pandas，与依赖预算共同服务 5 分钟指标）
