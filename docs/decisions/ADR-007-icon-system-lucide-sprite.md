# ADR-007: 图标方案锁定 lucide-static，构建期生成单一 SVG sprite

## Status

Accepted (2026-08-02) — 高见远

## Background

团队 P0 绝对规则：**禁止 emoji 作为功能图标，必须锁定一套 SVG 图标库，全项目统一不混用**。PRD 十·NFR 进一步要求 CLI 输出与 README 也不得用 emoji，日志状态用 `[PASS]` / `[FAIL]` / `[DEGRADED]` 文字前缀。

同时项目形态给出强约束：产物是**单文件静态 HTML，无服务器、无构建步骤、双击可开、离线可用**（PRD 六·AC-1、AC-3）。这排除了任何需要运行时 JS 图标库或 CDN 请求的方案。

图标的实际用途集中在一处但极其关键：数据健康度区块的三态（healthy / degraded / blocked）必须用**形状不同**的图标区分，不能只靠颜色（PRD 十·可访问性，WCAG 2.1 AA + 色盲可辨）。

## Decision

**锁定 lucide-static 1.28.0（ISC 许可）**，作为全项目唯一图标来源。

落地方式：开发期由 `tools/build_sprite.py` 依据 `config/icons.yaml` 白名单，从 lucide-static 抽取所需图标，合并生成单一 `src/apexfin/reporting/static/icons/sprite.svg`（每个图标一个 `<symbol id="icon-xxx">`），**sprite 提交入库**。运行时零 npm、零网络、零构建，模板中统一写：

```html
<svg class="icon" aria-hidden="true"><use href="#icon-alert-triangle"></use></svg>
```

| 候选 | 版本 | 许可 | 判定 |
|------|------|------|------|
| lucide-static | 1.28.0 | ISC | **选定**：提供纯 SVG 文件产物（非 React 组件），可离线抽取；线性风格匹配数据密集型看板；1500+ 图标覆盖充分；社区活跃 |
| Feather | 4.29.2 | MIT | 落选：lucide 本身是 Feather 的活跃 fork，Feather 更新已停滞 |
| Heroicons | 2.2.0 | MIT | 落选：数量偏少且偏产品向，缺数据/告警类语义图标 |
| Tabler Icons | 3.46.0 | MIT | 备选：数量最多，但体量更大、命名一致性略逊，风格与 lucide 高度重叠，无切换理由 |
| 手写内联 SVG | — | — | 落选：无统一来源即无法保证「不混用」，且视觉一致性靠人肉维护 |

版本与许可均于 2026-08-02 通过 npm registry 实测确认。

强制规则（CI 门禁）：
1. **禁止 emoji**。CI 扫描全部模板、Python 源码、README、CLI 输出字符串的 emoji 码点区段，命中即红灯。
2. **禁止第二套图标集**，禁止绕过 sprite 手写内联路径。
3. `reporting/icons.py` 扫描模板中全部 `#icon-*` 引用，任一 id 在 sprite 中不存在即失败——防止「图标不显示但页面照常渲染」这类静默缺陷。
4. 健康度组件 `partials/health_badge.html` 必须同时输出**文字标签 + 图标形状 + 颜色**三重编码，接口上不给调用方「只传颜色」的余地。
5. 配色侧同步约束：**禁止紫色到粉色渐变**（任何方向、任何透明度变体）。基线遵循 PRD 的 Slate/Indigo 数据密集风，具体方案归设计师。

## Consequences

正面：
- 单文件 sprite 与「双击打开的离线 HTML」形态完全契合，零运行时依赖。
- ISC 许可与项目 MIT 兼容，在 `NOTICE` 中标注来源即可。
- 白名单机制让 sprite 保持极小（预计 < 15 KB），不冲击 5 MB 产物上限。
- CI 校验把「图标缺失」从视觉问题变成构建失败，符合本项目 fail-loud 的一贯取向。

负面：
- 新增图标需要跑一次 `make sprite` 并提交产物，多一步操作。缓解：写进 CONTRIBUTING 级别的开发说明与 Makefile 目标，`make sprite` 一条命令完成。
- sprite 是生成产物却入库，存在与白名单不同步的风险。缓解：CI 重新生成并与入库文件比对，不一致即失败。
- lucide-static 的图标命名可能随主版本变化。缓解：版本锁定在 `1.28.0`，升级走独立 PR 并跑全量图标引用校验。

## Addendum (2026-08-02)：白名单可用性实测与「旧名不等于别名」

OPEN-DECISIONS O-02 担心白名单里的旧名（`x-octagon`、`check-circle-2` 等）在 1.28.0 中已被重命名而失效。实测结论：**担忧不成立，但发现了一个更需要防的问题**。

实测方法：逐个拉取 `https://unpkg.com/lucide-static@1.28.0/icons/<name>.svg`，对 `docs/DESIGN.md` 附录 A 全部 27 个名字取 HTTP 状态与内容 sha256。

结果一：27/27 全部 200，零缺失，白名单原样可用，DESIGN 附录 A 与 `config/icons.yaml` 均无需改名。

结果二（非预期）：旧名与新名并非都是同一图形的两个入口。

- `x-octagon` 与 `octagon-x`：路径完全一致，仅 `class` 属性不同 -> 真别名。
- `alert-triangle` 与 `triangle-alert`：路径一致 -> 真别名。
- `check-circle-2` 与 `circle-check-big`：**不同图形**。前者是闭合圆内含小对勾，后者是开口弧加大对勾出框。
- `table-2` 与 `table`：**不同图形**。前者缺角网格，后者矩形加三线网格。

`check-circle-2` 予以保留：状态列在 16px 下需要闭合外形与 `alert-triangle` / `x-octagon` / `circle-dashed` 的轮廓量级对齐，开口弧在小尺寸下读起来像「未完成」，与 healthy 语义相反。`table-2` 是否换成 `table` 属视觉判断，作为 advisory 交设计师，架构侧不擅自改。

由此追加一条硬约束：`config/icons.yaml` 中的图标名是**语义锁定值，不是可自由归一化的字符串**。任何「顺手把旧名统一成新名」的批量改动都必须逐个目视比对，否则会静默换掉状态语义。

`tools/build_sprite.py` 相应的 fail-loud 三条：
1. 白名单任一名字在包内不存在 -> 打印缺失清单，退出码 3（CONFIG），不产出任何文件。
2. 实际包版本与 `config/icons.yaml` 的 `lucide_version` 不符 -> 同样退 3。
3. 每个图标的 SVG 内容 sha256 前 8 位写入 `config/icons.lock`。升级 lucide 时哈希变动在 diff 中显形，强制人工确认是「描边微调」还是「换了图形」。第 3 条正是针对上面 `check-circle-2` 那类情形——没有它，一次例行升级就可能把状态图标悄悄换成另一个形状，而页面照常渲染、测试照常通过。

## Related ADRs

无直接依赖。与 `docs/ARCHITECTURE.md` 第九章为同一决策的两处表述，以本 ADR 为准。
