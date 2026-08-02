# ADR-004: 插件机制采用「装饰器注册表 + entry points」双轨

## Status

Accepted (2026-08-02) — 高见远

## Background

PRD AC-4 要求：第三方开发者只读 `BaseCollector` 抽象基类的 docstring，新增一个自定义数据源类并在配置中注册，**无需修改任何框架代码**即可接入管道，并自动获得分层落库与质量检查能力。

这是「可被 fork 的参考实现」定位的技术支点——P1 用户的典型行为就是「扔掉你的采集器，接自己的付费源」（PRD 二·关键洞察）。如果接入需要改框架代码，这个定位就落空了。

候选机制：
1. 纯装饰器注册表（import 时注册）
2. 纯 entry points（`importlib.metadata`）
3. 配置文件里写 `module:Class` 路径 + 动态 import
4. 目录扫描自动 import
5. 以上组合

## Decision

采用**双轨**：

- **内置组件**用装饰器注册表：`@register_source("yahoo")`、`@register_check("freshness")`、`@register_strategy("toy_momentum")`、`@step(...)`。在包 import 时完成注册，无魔法，可被静态阅读。
- **第三方扩展**用 Python entry points，组名 `apexfin.sources`、`apexfin.checks`、`apexfin.strategies`。启动时用 `importlib.metadata.entry_points(group=...)` 发现并加载（Python 3.10+ 的选择器 API，本项目最低 3.11，可直接使用）。

第三方包只需在自己的 `pyproject.toml` 里声明：

```toml
[project.entry-points."apexfin.sources"]
my_broker = "my_pkg.collectors:MyBrokerCollector"
```

然后在 `config/sources.yaml` 中把 `collector` 字段指向 `my_broker` 即可。框架侧零改动。

落选说明：
- 纯装饰器：无法覆盖「不修改框架代码」的第三方场景，除非用户 fork 后往框架里塞 import。
- 纯 entry points：内置组件也走 entry points 会让代码阅读变得间接（读者要跳到 `pyproject.toml` 才知道有哪些内置源），对参考实现是负价值。
- 配置里写 `module:Class` 路径：能工作，但等于让配置文件执行任意 import，是一个不必要的代码执行面，且失去 entry points 自带的「包级声明」语义。
- 目录扫描自动 import：最隐式，最难调试，明确排除。

关键约束（都指向可诊断性）：
- **加载失败绝不静默吞掉**。`discover_plugins()` 返回 `PluginReport`，失败项进 `failures`，`apexfin plugins list` 渲染为 `[FAIL] my_broker  my-pkg 0.3.1: ImportError: no module named 'ibapi'`。
- **名称冲突不静默覆盖**。内置优先，第三方同名注册被拒绝并记录为 `[SKIP] name: shadowed by builtin`。
- `apexfin doctor` 列出全部已发现插件及其来源包名与版本。
- 插件加载在 CLI 装配阶段完成，失败不影响与该插件无关的命令执行。

## Consequences

正面：
- 满足 AC-4：第三方接入零框架改动。
- 内置组件的注册在源码中直接可见，符合参考实现「要给人读」的目标。
- 失败可见、冲突可见，避免「装了插件但没生效且不知道为什么」这类最消耗信任的问题。

负面：
- 两套机制需要在文档里讲清楚边界，否则贡献者会困惑该用哪套。缓解：`docs/INTERFACES.md` 十一节明确「内置用装饰器，外部用 entry points」，无第三种选择。
- entry points 发现有启动开销（需扫描已安装分发包元数据）。实测量级为毫秒，对 60 秒预算无影响；若未来成为问题，可加 `--no-plugins` 快速路径。
- 恶意第三方包可通过 entry point 在启动时执行代码。这是 Python 打包生态的固有属性，非本项目引入；README 中提示只安装可信插件。

## Related ADRs

ADR-003（CLI 装配阶段触发插件发现）、ADR-005（插件机制是「策略可替换」得以成立的前提）
