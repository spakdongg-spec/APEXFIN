# 悬而未决登记册（OPEN-DECISIONS）

> 只追加、就地关闭。每个 Phase 开始时全量复现到工作上下文最前面，逐条判断能否关闭。
> 已关闭且具备长期约束力的条目，升格为 `docs/decisions/ADR-XXX.md`。

汇总：**0 未决 / 13 已决**

---

## 未决（OPEN）

（当前无未决项。新条目在此表追加。）

---

## 已决（RESOLVED）

| # | Date | Source | Open Item | Resolution | Resolved By | Slug | Status |
|---|------|--------|-----------|------------|-------------|------|--------|
| O-03 | 2026-08-02 | ARCHITECTURE 8.2 / R2 | Yahoo 服务条款与 APEXDATA 中 UA 轮换 + 双 host 回退的规避特征如何处置 | **采纳架构师方案 1 + 3**：删除 UA 轮换与多 host 回退；只保留单一公开端点、固定标识性 UA、默认 ≥1.5s 请求间隔、遇 429 立即停止本源并写 finding，不做绕过重试；demo 默认路径不访问 Yahoo。Stooq 作为文档化备选记入 ADR，MVP 不实现。**裁决理由**：本项目全部说服力建立在「数据诚实性」上，仓库里带一段专门用来绕过访问控制的代码，是自己拆自己的台；且 demo 走 fixture 已使 Yahoo 成为可选路径，风险敞口本就很小，没有为它承担法律与声誉风险的理由 | 大湾区靓仔（team-lead） | design-decision-to-evaluate | RESOLVED |
| O-04 | 2026-08-02 | ARCHITECTURE 十一 | 角色规范默认要求的 `openapi.yaml` 缺失 | **接受偏离**。本项目无 HTTP 服务端（PRD 十三 Out of Scope），CLI 即唯一对外接口。等价契约已产出且更贴合形态：`docs/CLI_CONTRACT.md`（命令/参数/退出码/`--json` 信封）+ `contracts/` 下 3 个 JSON Schema + `docs/INTERFACES.md`。**裁决理由**：为满足模板而编造一个不存在的 HTTP 契约是形式主义，且会误导实现方去找不存在的服务端。契约的作用是让双方对齐，载体形式服从项目形态 | 大湾区靓仔（team-lead） | design-decision-to-evaluate | RESOLVED |
| O-05 | 2026-08-02 | Phase 1 门禁扫描 | `docs/ALPHA_BOUNDARY.md` 在记录密钥泄露点时，把真实 FRED API key 的 32 位明文抄进了表格 | **已就地脱敏**（改为 `<32位十六进制明文，已脱敏>` 并加注说明）。审计文档抄录明文密钥 = 把泄露从私有仓库搬到公开仓库，是同一个错误换地方犯。定位靠文件 + 行号足够。**遗留动作项交用户**：该 key 仍明文存在于 APEXDATA 私有仓库，须在 FRED 控制台吊销重发，此事独立于 APEXFIN 是否带走它 | 大湾区靓仔（team-lead） | existing-design-boundary | RESOLVED |
| O-02 | 2026-08-02 | Phase 1 门禁 | Lucide 图标名在新版本中可能已重命名（`x-octagon` -> `octagon-x`、`check-circle-2` -> `circle-check-big`），锁定的 lucide-static 版本是否仍提供旧名别名未实测 | **已实测关闭，无需改名**。2026-08-02 逐个拉取 `unpkg.com/lucide-static@1.28.0/icons/<name>.svg`，DESIGN 附录 A 全部 27 个名字 **27/27 HTTP 200，零缺失**，白名单原样可用。**但实测出一个原假设之外的事实**：旧名并非都是新名的别名——`x-octagon`/`octagon-x` 与 `alert-triangle`/`triangle-alert` 路径完全一致（真别名），而 `check-circle-2`/`circle-check-big` 与 `table-2`/`table` 是**几何不同的两个图标**。故「旧名可安全归一化为新名」不成立，`config/icons.yaml` 中的名字定为语义锁定值，禁止批量改名。`check-circle-2` 保留（16px 下闭合外形需与其余三态轮廓量级对齐，开口弧读作「未完成」，与 healthy 语义相反）；`table-2` 是否换 `table` 作为 advisory 交设计师。`tools/build_sprite.py` 追加 fail-loud 三条：名字缺失退 3、包版本与 `lucide_version` 不符退 3、每图标 sha256 写入 `config/icons.lock` 使升级换图在 diff 中显形。已落 ARCHITECTURE 9.1 + ADR-007 Addendum | 高见远（架构师，实测） | design-decision-to-evaluate | RESOLVED |
| O-06 | 2026-08-02 | Phase 1 门禁全量扫描 | P0 红线扫描器会被红线声明文本自身误伤：22 个交付文件中 emoji 命中 0、弹跳缓动命中 0，但紫粉渐变命中 8 处、空洞文案命中 3 处，**全部落在禁止清单的声明里**（`DESIGN.md:1033` 自查清单、`design-tokens.json:313-320` 的 `denylist` 段、`PRD.md:446` P0 约束表） | **把关系倒过来，而不是加排除名单**。`design-tokens.json` 的 `denylist` 段是扫描器的**输入**，不是扫描对象：CI 从 `denylist.hexValues` / `denylist.patterns` 读取禁令，再去扫 `src/apexfin/**` 与 `config/**`；声明禁令的文件天然不在扫描目标内，无需任何排除逻辑。**裁决理由**：排除名单本身会腐化——一旦 CI 因红线清单自身而红灯且无法通过，团队第一反应是放宽扫描规则，红线就此形同虚设。已要求架构师写进 ARCHITECTURE 9.1，因为这是「为什么扫描器长这样」的根因，将来会有人想不通而去改坏它 | 大湾区靓仔（team-lead） | design-decision-to-evaluate | RESOLVED |
| O-07 | 2026-08-02 | Phase 1 门禁交叉核对 | 设计师 DESIGN §4.6 用小时制 SLA（`lag_hours/sla_hours/sla_ratio`、相对时间「2 小时前」），与架构师 ARCHITECTURE §5.3 / DATA_CONTRACT `series_health`（仅 `lag_trading_days` 交易日历语义）冲突 | **采纳交易日历语义为唯一真值**：SLA 进度条 = `lag_trading_days / max_lag_trading_days`（`max_lag_trading_days` 来自 `expectations.yaml`，由 DataPack 透传）；「X 小时前」降级为展示层 ONLY 派生字符串（由 `last_event_date` 对比 Clock 计算，不存储、不进 SLA 数学）；拒绝 `lag_hours/sla_hours/sla_ratio` 作为契约字段（小时级 SLA 在周末/假期下脆弱，违背「业务时间 + 交易日历」哲学）。设计师据此改 §4.6，架构师在 §5.3 + series_health 写明进度条公式 | 大湾区靓仔（team-lead） | design-decision-to-evaluate | RESOLVED |
| O-01 | 2026-08-02 | Phase 1 门禁 | `make demo` 默认走离线 fixture，而非用户 q-1 原话指定的「Yahoo + FRED 免费公开源」 | **采纳架构师方案（用户 2026-08-02 确认）**：默认 fixture 离线可复现、零网络零密钥、CI 稳定；真实源作为 `apexfin collect --source yahoo` 一条命令的进阶路径，README 首屏说明。满足「最小可跑 Demo」决策与开源分发场景 | 大湾区靓仔（team-lead） | waiting-on-external-condition | RESOLVED |
| O-10 | 2026-08-02 | Phase 3 施工期 · team-lead 门禁扫描 | `static/tokens.css` 392 行超「单文件 ≤300 行」P0 红线；同时文件内混入 3 处非 token 内容（`.sr-only` :352、`.ts/td.num/th.num` :369、`@media` 内 `.btn/.qgate__cell` :387） | **拆成两件事分别处置，不整体豁免**。① 职责混入必须修：3 处组件规则挪入 `static/dashboard.css`（239 行 + ~25 行 = ~264 行，不超线）；`@font-face` 两块留在 tokens.css，因其为 `--font-data`/`--font-mono` 的载入前提，拆开会让 token 引用别处声明的字体族。② 挪后仍约 367 行，**批 300 行豁免，但豁免带三条机械条件**：除两块 `@font-face` 外不得出现任何类/元素/属性选择器（只允许 `:root` 及 `[data-theme=*]`/`[data-palette=*]` 作为 token 作用域）；`@media` 内只允许改 token 值不得含组件规则；文件顶部注释写明豁免判定依据与「引入任何选择器则豁免自动失效」。**裁决理由**：300 行红线要防的是单文件多职责与控制流膨胀，而 197 个自定义属性 + 4 个主题作用域的声明表复杂度是线性、可逐行 diff、零控制流的；硬拆会引入加载顺序敏感 + 改一个语义色需跨文件对照，后者直接违背该文件自称的 single source of truth。豁免条件写进文件本身而非登记册，手法同 O-06——约束要写在会被违反的地方 | 大湾区靓仔（team-lead） | design-decision-to-evaluate | RESOLVED |
| O-09 | 2026-08-02 | Phase 3 施工期 · team-lead 代码核查 | `expectations.yaml` 缺阈值时 `max_lag_trading_days` 写什么——`SourceExpectation` 的 dataclass 默认值 `= 2`（`expectations.py:35`）配合 `raw.get("defaults") or {}`（:71），构成一条「配置里没有、代码里补上」的隐形路径，而 DDL 是 `NOT NULL` | **defaults 段必填，缺失即 fail-loud，不得回落到代码默认值**。四条：① `config/expectations.yaml` 顶层 `defaults:` 段必填且必须显式给出 4 个数值键全部（`max_lag_trading_days`/`completeness_window_days`/`max_missing_trading_days`/`max_gap_trading_days`）；② `load_expectations()` 在 `defaults` 缺失或缺键时抛 `ConfigError` 并指名缺哪个键；③ dataclass 默认值保留但职责降级为「测试直接构造对象时的类型兜底」，加载路径永不依赖；④ DDL `NOT NULL CHECK (>= 0)` 不变，落表写 `for_series()` 解析后的**最终生效值**而非 YAML 字面值。**裁决理由**：DATA_CONTRACT `series_health` 那段论证「阈值列非空、滞后列可空」的前提是「阈值永远已知，因为它来自配置而非观测」。若配置里可以没有它、由代码默认值补上，这个前提就是假的——判定依据变成用户在 YAML 里找不到的数字，与该节自己痛斥的「结论在库里、依据在别处」同病，只是依据不是漂移而是压根不存在。架构师未回、后端正在写 config 层，等不起，故由 team-lead 拍板并要求架构师封版解除后补文档 | 大湾区靓仔（team-lead），架构师复核待回 | existing-design-boundary | RESOLVED |
| O-11 | 2026-08-02 | Phase 3 施工期 · team-lead 代码核查 | `pipeline/runner.py:57` 的 `savepoint(ctx.conn_factory(), step.name)` 与 repository 持有的连接不是同一个，SAVEPOINT 保护的是空事务，失败步骤的写入不会被回滚 | **推论成立，按 team-lead 倾向修，架构师收紧一处**。① `RunContext` 删 `conn_factory: ConnectionFactory`，改为 `conn: sqlite3.Connection`（`context.py` 需加 `import sqlite3`）；② 五个 repository 一律用这个 `conn` 构造；③ `runner.py:57` 改 `with savepoint(ctx.conn, step.name):`；④ `ConnectionFactory` Protocol **保留不删**，职责收紧为「只在 composition root 调用一次」——CLI 装配时建连接、迁移、构造 repo、构造 `RunContext`，此后全流程共用。**裁决理由**：`runner.py` 文档字符串第 3-5 行承诺「each inside its own SAVEPOINT so a failing step rolls back its own writes」，而 `storage/engine.py:23-30` 的 `connect()` 每次调用新开连接、`storage/*_repo.py` 构造时绑定固定连接（`self._conn = conn`），两者不是同一个连接对象，SQLite 的 SAVEPOINT 是连接级事务原语，跨连接不生效——即该承诺当前为假，且是静默为假（回滚成功返回、写入原样留在库里），属本项目最不能接受的 fail-silent 类别。附带风险：双连接并发写同一文件可能撞 `SQLITE_BUSY`。**波及面经架构师核实为极小**：`INTERFACES.md` §6（:271）`RunContext` 字段 `conn_factory` → `conn`；`runner.py` 一行；`pipeline/steps.py`（299 行）**不动**，因为全部 step 只经 `ctx` 拿 repo、从不碰 `conn_factory`；`ARCHITECTURE.md` 不动 | 大湾区靓仔（team-lead）发起 · 高见远（架构师）裁决 | design-decision-to-evaluate | RESOLVED |
| O-08 | 2026-08-02 | Phase 3 施工期 · 架构师自查 | O-07 保留的「X 小时前」展示层派生串，在健康行内与交易日进度条并排，实际无法安全实现 | **撤回该保留项，把两个时钟物理分开**。健康行改显示业务日期 `last_event_label`（含周几，如 `07-31（周五）`，由 `datapack.py` 预格式化）；写入时间从每序列撤出，移入全局页脚 `DataPack.run_footer`（来源 `pipeline_runs.finished_at`），措辞指向采集动作而非数据年龄；`HealthRow` 类型层面禁止任何写入时间字段（`last_checked_at` 留表不进视图模型）。**裁决理由**：`last_event_date` 是日粒度，派生不出小时——实现者唯一能拿到小时的来源就是写入时间，而写入时间测「管道多久前碰过源」≠「数据多旧」。周日跑管道、FRED 停在周三，页面会显示「2 分钟前」而真实滞后 2 个交易日，**系统性低估陈旧度**。这是 O-07 拒绝小时制的同一个错误换了个形态，我上一轮把它当无害展示串放过了，是漏判。新增 AC-10 / AC-11 三条机械验证使其不可回潮 | 高见远（架构师）发起 · 大湾区靓仔（team-lead）裁决为小改并实时传导前后端 | design-decision-to-evaluate | RESOLVED |
| O-12 | 2026-08-02 | Phase 4 · DevOps 部署预研 | demo-stale 契约假绿：`run daily --fixture-pack stale` 裸跑（无 `--as-of`）exit 0 而非契约的 4。根因：`build_fixtures.py:145` stale equity 复用 `_FRESH_AS_OF`（与 fresh 相同**是设计**——滞后来自 Clock 注入而非数据差异，fixture.py 模块注释「Staleness is produced by switching packs and freezing the clock, never by editing the database」），但 `load_pack_meta` 解析的 `meta.as_of` **无任何代码消费**（context.py 只在 `--as-of` 时冻结 clock）。隐藏双 bug：`make demo`（fresh）在真实日期≠2026-07-31 时同样退 4——整条 demo 路径对系统日期有隐性依赖，违反 clock.py「byte-identical on any machine on any day」承诺 | **采纳方案 B，位置修正为组合根**。① 冻结时钟优先级 = 显式 `--as-of` > pack meta.as_of（指定 `--fixture-pack` 时）> SystemClock；实现放 `cli/context.build_context` 加 `fixture_pack` 参数（约 6 行），**不放 fixture collector**（sources 必须纯净，source 里改 clock 是副作用，gate 在 collect 后才消费 clock）；② `build_fixtures.py:145` **不改**（传 `_STALE_AS_OF` 会让 equity 变 current、demo-stale 退 0 毁契约；数据不变才能证明 0/4 差异来自 Clock 注入）；③ 补回归测试：裸跑 `run daily --fixture-pack stale` 必须退 4（CLI_CONTRACT:204 承诺的差异化回归现在假绿）；④ CLI_CONTRACT 补一行 + 变更记录 v1.0→v1.1；⑤ 命令面收敛：以 CLI 实际为准，**不加 demo/demo-stale 别名命令**（Makefile 即 demo 抽象层），SPEC §2/§5/§9/§9.1 命令名改 `make demo`/`make demo-stale` 或裸命令，`report`→`render` 漂移一并修；⑥ 发布文件（Makefile/LICENSE/NOTICE/.gitignore/uv.lock）归 DevOps | 大湾区靓仔（team-lead）发起 · 高见远（架构师）裁决 · DevOps 预研举证 | design-decision-to-evaluate | RESOLVED |

---

## 关闭项的架构侧落地状态

裁决只有落进将被实现者读到的文档才算生效。逐条对照：

| # | 落地位置 | 落地形式 | 状态 |
|---|----------|----------|------|
| O-02 | `ARCHITECTURE.md` 9.1、`ADR-007` Addendum | 27 图标实测表 + 「旧名不等于别名」硬约束 + `build_sprite.py` fail-loud 三条 + `config/icons.lock` 哈希锁 | DONE |
| O-03 | `ARCHITECTURE.md` 8.2（标题改为「已裁决，生效约束」）、`ADR-009`（新建）、`ALPHA_BOUNDARY.md` D3、风险表 R2 | 生效处置 4 条 + **C1-C6 六条可测断言**（AST 门禁 / 单测），并明确「退避只对瞬时网络故障生效，429/403 不属于该集合」 | DONE |
| O-04 | `ARCHITECTURE.md` 十一（标题改为「偏离获准」） | 标注裁决人与登记编号，替换原「需 team-lead 确认」措辞 | DONE |
| O-05 | `ALPHA_BOUNDARY.md`（team-lead 就地脱敏） | 架构侧复核：全仓 `\b[0-9a-f]{32}\b` 正则扫描 `.md/.json/.yaml/.py/.html/.css/.txt`，**命中 0**，脱敏确认彻底 | VERIFIED |
| O-06 | `ARCHITECTURE.md` 9.1 末「P0 红线扫描器的设计约束」、9.2 交叉引用 | denylist 定为扫描器输入源而非扫描对象 + 「为什么不用排除名单」根因 + emoji 码点区间锁定（排除 `U+2190-U+21FF` 箭头块） | DONE |
| O-07 | `ARCHITECTURE.md` 5.3.1 + 5.3.2 + 7.2 门禁行、`DATA_CONTRACT.md` 四 `series_health`、`INTERFACES.md` 9.1 | 新增 5.3.1「新鲜度只有一种单位」（含小时制在周末系统性误报的论证）+ 5.3.2 进度条公式与三条边界（NULL / maxd=0 / 超期 clamp）+ 补齐 `HealthRow`/`FreshnessBar` 完整契约 + `series_health` 增列 `max_lag_trading_days`（检查时快照）+ CI 门禁禁止 `lag_hours`/`sla_hours`/`sla_ratio` | DONE |
| O-08 | `ARCHITECTURE.md` 5.3.1.1、`INTERFACES.md` 9.1（约束 6/7 + `RunFooter` 模型）、`DESIGN.md` §4.6 与设计原则 #5、`preview.html`（`.rail__ago`→`.rail__date` + `.run-footer`）、`SPEC.md` §9 AC-10/AC-11 | 健康行去相对时间改 `last_event_label`（含周几）+ `DataPack.run_footer` 全局一处 + `HealthRow` 类型层禁写入时间字段 + 三条机械验证（类型无 `last_checked_at` / 健康区块「小时前」计数 0 / `lag_hours` 等标识符计数 0） | DONE（实现待验，Phase 4 按 AC-10/11 收） |
| O-09 | 代码侧：`quality/expectations.py`（`load_expectations` fail-loud 分支）+ `config/expectations.yaml`（`defaults` 段显式四键 + 每个阈值的来历注释）。文档侧：`DATA_CONTRACT.md` 四 `series_health` 的 `NOT NULL` 取舍段落之后 | 已实时传导后端实现；文档补写待 Phase 3 封版解除后由架构师执行 | 代码 DONE（后端 B-4 已验）· 文档 DONE（2026-08-02 架构师：DATA_CONTRACT 四补「defaults 段必填」小节） |
| O-10 | 代码侧：`static/tokens.css` 顶部豁免判定注释 + `@font-face` 例外注释、`static/dashboard.css` 接收 3 处组件规则。文档侧：`SPEC.md` §10 边界与约束补「300 行红线的适用范围」 | 已实时传导前端；SPEC 补写待封版解除 | 代码 DONE（team-lead 实测 2026-08-02：tokens.css 366 行零组件选择器、豁免注释在位、dashboard.css 289 行接收三处规则、`.foot a:hover` 死规则已删）· 文档 DONE（2026-08-02 架构师：SPEC §10 补豁免三条机械条件） |
| O-11 | 代码侧：`pipeline/context.py` `conn_factory` → `conn: sqlite3.Connection`（加 `import sqlite3`）；`runner.py:57` 改 `savepoint(ctx.conn, step.name)`；CLI 组合根一次性建连接。文档侧：`INTERFACES.md` §6(:271) `RunContext` 字段改 `conn` | 裁决 2026-08-02 达成（架构师收紧一处：`ConnectionFactory` 保留，仅组合根调用一次）；已写入 fixlist B-8 解锁下发；文档补写待 Phase 3 封版解除后由架构师执行 | 代码 DONE（后端 B-8 已验）· 文档 DONE（2026-08-02 架构师：INTERFACES §6 字段改 `conn` + Runner 保证补 O-11 共享连接约束） |
| O-12 | 代码侧：`cli/context.py` `build_context` 加 `fixture_pack` 参数，冻结时钟优先级 = 显式 `--as-of` > pack meta.as_of > SystemClock（约 6 行）；回归测试锁「裸跑 stale 必退 4」；CLI_CONTRACT 补行 + v1.0→v1.1。文档侧：SPEC §2/§5/§7/§9/§9.1 命令面收敛 + §10 O-10 豁免、README `report`→`render` | 2026-08-02 裁决达成；SPEC/README/INTERFACES/DATA_CONTRACT 文档收敛由架构师 DONE（team-lead 抽查 6 项全过）；后端代码修复执行中 | 代码 IN PROGRESS（后端）· 文档 DONE（架构师） |

O-03 的落地不止于改措辞。原文只有一句「删除规避逻辑」，实现者完全可能删掉 UA 池却把 429 顺手并进重试集合——规避行为换个写法就回来了。C1-C6 把这句主张拆成六条 CI 可判的断言，其中 C4「mock 429 断言请求次数 == 1」是真正的防线。

O-07 的落地追加了一项裁决未提及但必需的内容：`series_health` 增列 `max_lag_trading_days`。裁决说「阈值来自 `expectations.yaml`，由 DataPack 透传」，若按字面实现为渲染时现读配置，会引入两个问题——其一，阈值日后被改动，历史健康行的 `state` 即无法自证（表里 lag=2/degraded，配置说 max=3，记录本身解释不了自己）；其二，`reporting/` 将耦合 `quality/` 的配置格式，违反 L3 互不认识的铁律。改为质量检查执行时快照落表，两个问题同时消失，成本是一个 INTEGER 列。这属于「按裁决意图实现」而非「按裁决字面实现」，已在 DATA_CONTRACT 四写明理由备查。

---

## 交给用户的行动项（不属于本项目交付范围，但必须做）

| # | 动作 | 紧急度 | 说明 |
|---|------|--------|------|
| U-01 | 在 FRED 控制台吊销并重新签发 API key | 高 | 明文 key 存在于 `APEXDATA/scripts/pipeline/fetch_fred.py:22` 与 `fetch_fred_regional.py:23`。APEXFIN 不带走它不等于它已安全 |
| U-02 | APEXFIN 全新 `git init`，不迁移 APEXDATA 的 git 历史 | 高 | 历史提交中可能残留密钥与私有数据，从根上避免 |
| U-03 | 开源前跑 `gitleaks detect` 全量扫描工作区与 git 历史，报告留档 | 高 | 自动化只能拦模式化泄露，配合 ALPHA_BOUNDARY 六的人工复核清单 |
