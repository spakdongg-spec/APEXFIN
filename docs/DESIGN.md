# APEXFIN 看板设计规范

> 版本 v1.0 · Phase 1 设计方向文档
> 适用范围：APEXFIN 静态 HTML 看板（Jinja2 + 原生 CSS + ECharts，无构建步骤，可离线打开）
> 设计寄存器：**Product（产品型）** —— 设计服务于数据，不是设计本身。
> 三轴刻度：`DESIGN_VARIANCE = 3` · `MOTION_INTENSITY = 2` · `VISUAL_DENSITY = 8`

---

## 0. 设计论点（先讲清楚为什么，再讲怎么做）

APEXFIN 的看板不是营销落地页，是**一份可以直接给交易台看的运行报告**。它要在三秒内回答三个问题：

1. 我的数据能不能信？（数据健康度 + 质量门）
2. 数据说了什么？（价格 + 宏观）
3. 系统跑没跑对？（管道执行 + 决策输出）

由此推导出本设计系统的核心论点：

> **色相（hue）是稀缺资源，全部预算划给「数据语义」；视觉层次（hierarchy）不花色相，用亮度、字重、字号来做。**

这条论点直接决定了后面所有选择：
- 品牌强调色 `--accent` **不承担"重要"的含义**，只承担"这里可以点"的含义（链接 / 焦点 / 选中）。每屏可见使用 ≤ 2 处。
- "重要"由 `--fg` 的亮度 + 字重 600 + 字号 22/28px 承担。
- 红 / 绿 / 青 / 琥珀四个色相全部是**语义保留字**，任何装饰用途禁止占用。

这是本项目最重要的反 AI 模板动作。AI 生成的看板通病是"每个卡片一个渐变色标题 + 一个彩色左边框"，色相被装饰吃光，真正的数据反而没有色彩预算。APEXFIN 反过来做。

### 三轴刻度的偏离说明

默认值是 6 / 5 / 4，本项目全部偏离，理由如下：

| 轴 | 默认 | 本项目 | 理由 |
|---|---|---|---|
| DESIGN_VARIANCE | 6 | **3** | 交易员的眼睛需要"每次打开，同一个数字在同一个位置"。非对称布局在金融终端里是认知噪音，不是设计感。严格 12 栏对称栅格。 |
| MOTION_INTENSITY | 2 | **2** | 静态 HTML，无实时流。动效只服务于状态反馈（hover / focus / 展开），零装饰动画。数据看板上的入场动画会让人怀疑数据在变。 |
| VISUAL_DENSITY | 4 | **8** | 驾驶舱模式。参照 TradingView / Grafana / Bloomberg 的信息密度。行高 28px、单元格内边距 12px、禁止通用卡片盒子堆叠，用 1px 分隔线 + 负空间分组。 |

---

## 1. Visual Theme & Atmosphere（视觉主题与氛围）

### 对标品牌与选定理由

| 对标 | 学它什么 | 明确不学什么 |
|---|---|---|
| **TradingView（深色主题）** | 深墨蓝黑底（非纯黑）的画布哲学；网格线弱到"需要时才存在"；坐标文字用柔灰而非纯白 | 它的绿涨红跌（我们必须红涨绿跌）；它的工具栏复杂度 |
| **Linear** | 深色下用**亮度递进**表达层级而非阴影；克制到接近无彩的界面骨架；焦点环与交互态的精确度 | 它的品牌紫（P0 红线） |
| **Grafana / Datadog** | 运维控制台的信息组织：状态优先、最少点击、跨面板标签一致；"一切正常"应该是安静的 | 它们默认的高饱和红绿告警堆叠 |
| **dbt docs / Great Expectations / Monte Carlo** | 数据质量报告的呈现范式：**维度矩阵**（完整性/一致性/及时性…）× 数据源，单元格是状态；新鲜度用"最后成功更新时间"表达；健康分 = 通过数 / 总数 | 它们偏文档化、密度不足的排版 |
| **Bloomberg Terminal** | 极高信息密度下的可读性；数字右对齐 + 等宽对齐；文字标签一律短促、无修饰 | 它的 90 年代配色与全大写轰炸 |

**一句话设计语言：**

> 深墨蓝黑画布上的仪器盘 —— 用亮度做层次、用等宽数字做骨架、把全部色相预算留给数据语义，安静时几乎无彩，出问题时一眼可见。

### 氛围关键词

`克制` · `仪器感` · `高密度可读` · `可信` · `零噱头`

### 明确的反氛围（出现即重写）

- 不要"科技感光效"：无发光边框、无毛玻璃、无霓虹描边
- 不要"营销首屏"：第一屏是数据，不是标题
- 不要"彩虹卡片墙"：面板不靠颜色区分身份，靠位置和标题
- 不要庆祝式绿色：95% 的检查通过时，屏幕不应该 95% 是绿的

---

## 2. Color Palette & Roles（色板与角色）

### 2.1 核心机制：双通道色彩隔离协议

这是本设计系统需要最优先理解的一条规则。

APEXFIN 的看板同时存在两套天然冲突的红绿语义：

- **行情语义（中国 A 股惯例）**：红 = 涨（好消息）、绿 = 跌（坏消息）
- **状态语义（工程惯例）**：绿 = 通过（好）、红 = 失败（坏）

**两者对绿色的解读完全相反。** 直接混用会造成真实的误读：一个绿色单元格到底是"价格跌了"还是"检查通过了"？

解决方案是三层隔离，三层同时生效，缺一不可：

**第一层 —— 色相隔离**

系统状态通道**放弃使用绿色**。"健康 / 通过"改用**青（cyan）**。青在运维语境里读作"在线 / 正常 / 已核验"，语义成立，且与行情的翠绿明确区分。系统失败改用**绛红（wine-crimson，偏冷）**，与行情的朱红（偏橙、更亮）拉开色相和明度距离。

**第二层 —— 载体隔离（强制，模板层执行）**

| 通道 | 唯一允许的载体 | 严格禁止 |
|---|---|---|
| 行情通道 M | 等宽数字的**前景色** + 方向符 `▲ ▼ —`；表格行的 12% 低透明度底纹 | 禁止作为图标色、徽章填充、按钮色、边框色 |
| 状态通道 S | 状态**图标**（16px SVG）、**徽章填充**、面板左侧 2px **状态轨**、健康分进度条 | 禁止作为裸数字的前景色 |

一个数字如果是彩色的，它一定是行情；一个色块 / 图标如果是彩色的，它一定是状态。这条规则由模板层保证，前端不得越界。

**第三层 —— 永不依赖颜色（WCAG 1.4.1）**

- 每个状态 = **形状不同的图标** + **文字标签**，颜色只是第三重编码。
  `check-circle-2`（圆+对勾）/ `alert-triangle`（三角）/ `x-octagon`（八边形）/ `circle-dashed`（虚线圆）—— 四个轮廓形状彼此不同，色觉障碍用户靠形状即可分辨。
- 每个涨跌数字 = **正负号 + 方向符 ▲▼—** + 颜色。
- 提供 `[data-palette="cvd"]` 色觉安全模式：行情切换为**红涨 / 蓝跌**（部分中国终端的既有色盲方案），状态切换为蓝 / 橙二元编码。

**隔离度实测**（HSL 空间，已用脚本核算）：

| 对照 | 色相差 | 饱和度差 | 明度差 | 评价 |
|---|---|---|---|---|
| `--mkt-down` 翠绿 (160.0°, S78) vs `--st-ok` 青 (189.3°, S58) | **29.3°** | 20pp | 1.5pp | 充分分离。最危险的"绿色歧义"已消除 |
| `--mkt-up` 朱红 (3.9°, S91) vs `--st-fail` 绛红 (350.1°, S72) | **13.8°** | 19pp | 4.3pp | 分离度偏紧，依赖载体隔离 |

**残余风险与坦白**：朱红（涨）与绛红（失败）色相仅差 13.8°，小尺寸下无法仅凭色相区分。这是权衡后的取舍——"失败"改用品红会踩 P0 粉色红线，改用橙色会撞琥珀警告色。饱和度差 19pp 提供了"寄存器差"（行情色鲜艳、状态色沉着），加上第二层载体隔离与第三层形状+文字编码，实际使用中不会误读。**但这是本设计系统唯一的薄弱点，评审时必须专项验证**：在同一屏内同时出现红色涨幅数字和失败徽章时，做一次眯眼测试（squint test）。

相比之下，`--mkt-down` 与 `--st-ok` 的 29.3° 色相差是本方案的核心收益——把"绿色到底是跌还是通过"这个真正致命的歧义彻底消除了。

### 2.2 完整 Token 定义（深色主题，默认）

```css
:root,
:root[data-theme="dark"] {

  /* ============================================================
     A1-identity · 表面层（亮度递进代替阴影，参照 Linear / TradingView）
     ============================================================ */
  --bg:            #0B0E14;  /* 页面底：深墨蓝黑。刻意深于 TradingView #131722，让面板浮起 */
  --surface:       #111721;  /* 面板 / 卡片底 */
  --surface-2:     #161D29;  /* 表头、嵌套区、行 hover */
  --surface-3:     #1C2532;  /* 选中行、激活态 */

  /* ============================================================
     A1-identity · 前景层
     ============================================================ */
  --fg:            #E8EEF7;  /* 主文本、关键数值            对 --surface 15.4:1 */
  --fg-2:          #AFBBCB;  /* 次级文本、表格正文          对 --surface  9.2:1 */
  --muted:         #8290A4;  /* 标签、表头、单位            对 --surface  5.5:1 */
  --meta:          #616E82;  /* 三级：时间戳、脚注、禁用态  对 --surface  3.5:1
                                仅限 >=16px 或非关键信息，不得单独承载关键内容 */

  /* ============================================================
     A1-identity · 边框层
     ============================================================ */
  --border:        #202938;  /* 面板外框 */
  --border-soft:   #19212E;  /* 表格行分隔线（几乎隐形，只提供节奏） */
  --border-strong: #2C3849;  /* 表头下沿、分区线、图表坐标轴 */

  /* ============================================================
     A1-identity · 交互强调色（只表示"可交互"，不表示"重要"）
     每屏可见使用 <= 2 处
     ============================================================ */
  --accent:        #4589E6;  /* 链接、焦点环、选中下划线    对 --surface 5.4:1 */
  --accent-fill:   #2F6BC4;  /* 实心按钮背景 */
  --accent-on:     #FFFFFF;  /* accent-fill 上的前景        5.2:1 */
  --accent-hover:  #5A98EA;
  --accent-active: #3B79D4;
  --accent-wash:   rgba(69, 137, 230, 0.12);

  /* ============================================================
     通道 M · 行情方向（中国 A 股惯例：红涨绿跌）
     高彩度 · 仅用于等宽数字前景色 + 方向符 + 12% 行底纹
     ============================================================ */
  --mkt-up:        #F6564B;  /* 朱红 · 涨                   对 --surface 5.5:1 */
  --mkt-down:      #17BE86;  /* 翠绿 · 跌                   对 --surface 7.4:1 */
  --mkt-flat:      #8290A4;  /* 灰 · 平 / 停牌 / 无变化 */
  --mkt-up-wash:   rgba(246, 86,  75, 0.12);
  --mkt-down-wash: rgba( 23, 190, 134, 0.12);
  --mkt-flat-wash: rgba(130, 144, 164, 0.10);

  /* ============================================================
     通道 S · 系统状态（刻意避开绿色；低彩度，与行情色形成"寄存器差"）
     仅用于状态图标 / 徽章 / 状态轨 / 进度条
     ============================================================ */
  --st-ok:         #2E9BAF;  /* 青  · 健康 / 通过 / 新鲜     对 --surface 5.5:1 */
  --st-warn:       #C99A3B;  /* 琥珀 · 警告 / 陈旧 / 降级    对 --surface 7.0:1 */
  --st-fail:       #E14A63;  /* 绛红 · 失败 / 中断 / 越界    对 --surface 4.6:1 */
  --st-idle:       #5E6B7E;  /* 石墨 · 未知 / 未运行 / 跳过 */

  --st-ok-fill:    #1B6B7A;  /* 徽章填充，配 #FFFFFF 文字   6.2:1 */
  --st-warn-fill:  #8A6417;  /*                             5.4:1 */
  --st-fail-fill:  #B32E4C;  /*                             6.2:1 */
  --st-idle-fill:  #38414F;

  --st-ok-wash:    rgba( 46, 155, 175, 0.12);
  --st-warn-wash:  rgba(201, 154,  59, 0.12);
  --st-fail-wash:  rgba(225,  74,  99, 0.12);
  --st-idle-wash:  rgba( 94, 107, 126, 0.10);

  /* ============================================================
     图表 · 中性序列色（宏观 / 非方向性数据专用）
     低彩度（S 25-45%），刻意"退到背景"，把视觉优先级让给行情色
     ============================================================ */
  --chart-1: #6E9BD8;  /* 雾蓝 */
  --chart-2: #5FA8A0;  /* 灰青 */
  --chart-3: #C0A268;  /* 沙金 */
  --chart-4: #9AA3B5;  /* 石板 */
  --chart-5: #B98A78;  /* 陶土 */
  --chart-6: #7E8FB8;  /* 靛灰 */

  --chart-axis:      #2C3849;  /* 坐标轴线 */
  --chart-split:     #1B2330;  /* 网格线：弱到"需要时才存在"（TradingView 教训） */
  --chart-label:     #8290A4;  /* 坐标文字 */
  --chart-crosshair: #AFBBCB;  /* 十字光标 */
  --chart-tooltip-bg: #161D29;

  /* ============================================================
     A1-structure · 字体栈
     ============================================================ */
  --font-data: "JetBrains Mono", ui-monospace, "SF Mono", "Cascadia Mono",
               Menlo, Consolas, monospace;
  --font-ui:   -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text",
               "Segoe UI", "PingFang SC", "HarmonyOS Sans SC",
               "Microsoft YaHei", "Noto Sans SC", sans-serif;

  /* ============================================================
     A1-structure · 字号（密度 8 · 紧凑刻度）
     ============================================================ */
  --text-2xs: 11px;  /* 单位 / 角标。禁止单独承载关键信息 */
  --text-xs:  12px;  /* 标签、表头、meta */
  --text-sm:  13px;  /* 表格数据行（默认数据字号） */
  --text-md:  14px;  /* 正文 / 说明（本项目 body 基准） */
  --text-lg:  16px;  /* 面板标题、长段落说明文字 */
  --text-xl:  18px;  /* 区块标题 */
  --text-2xl: 22px;  /* KPI 数值 */
  --text-3xl: 28px;  /* 主 KPI / 健康总分 */

  --leading-data:  1.35;  /* 数据行 */
  --leading-body:  1.6;   /* 中文段落（CJK 需要更松） */
  --leading-tight: 1.15;  /* 大号 KPI */

  --tracking-caps:    0.08em;  /* ALL CAPS 标签，强制 */
  --tracking-data:    0.01em;  /* 13px 等宽数据 */
  --tracking-display: -0.02em; /* >= 22px */

  --weight-read:     400;
  --weight-emph:     500;
  --weight-announce: 600;

  /* ============================================================
     A2 · 间距（4px 网格）
     ============================================================ */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* 密度专用 */
  --row-h:         28px;  /* 数据表行高 */
  --row-h-compact: 24px;  /* 极密模式（矩阵单元格） */
  --cell-px:       12px;  /* 单元格左右内边距 */
  --panel-pad:     16px;  /* 面板内边距 */
  --panel-head-h:  36px;  /* 面板标题栏高度 */
  --topbar-h:      44px;  /* 顶部状态栏 */

  /* ============================================================
     A2 · 圆角（仪器感 = 低圆角。上限 8px，禁止 >= 12px）
     ============================================================ */
  --radius-xs:   3px;  /* 状态徽章、tier 标签 */
  --radius-sm:   4px;  /* 输入框、小按钮 */
  --radius-md:   6px;  /* 按钮、下拉 */
  --radius-lg:   8px;  /* 面板（本项目最大圆角） */
  --radius-pill: 999px;/* 仅状态圆点 */

  /* ============================================================
     A2 · 层级（深色下用亮度递进，不用阴影。阴影仅限浮层）
     ============================================================ */
  --elev-flat:    none;
  --elev-ring:    inset 0 0 0 1px var(--border);
  --elev-overlay: 0 8px 24px rgba(0, 0, 0, 0.55);  /* 仅 tooltip / popover / modal */

  /* ============================================================
     A2 · 焦点与动效（MOTION_INTENSITY = 2）
     ============================================================ */
  --focus-ring:  0 0 0 2px var(--bg), 0 0 0 4px var(--accent);
  --motion-fast: 120ms;   /* hover 变色、按下 */
  --motion-base: 180ms;   /* details 展开、tooltip 淡入 */
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);

  /* ============================================================
     A1-structure · 布局
     ============================================================ */
  --container-max:     1440px;  /* 看板需要宽度，不是 1200 */
  --gutter-desktop:    24px;
  --gutter-tablet:     16px;
  --gutter-phone:      12px;
  --section-y-desktop: 32px;    /* 密度 8：远小于常规 SaaS 的 80px */
  --section-y-tablet:  24px;
  --section-y-phone:   16px;
  --grid-gap:          12px;
}
```

### 2.3 浅色主题覆盖

遵循研究结论「一个语义角色，两套色阶」——**同一个 hex 在深浅底上的知觉重量完全不同**，必须分别调校，不能复用。

```css
:root[data-theme="light"] {
  --bg:            #F4F6F9;
  --surface:       #FFFFFF;
  --surface-2:     #EDF1F6;
  --surface-3:     #E3E9F1;

  --fg:            #10151D;
  --fg-2:          #33404F;
  --muted:         #5A697C;
  --meta:          #808D9E;

  --border:        #D8DFE8;
  --border-soft:   #E8EDF3;
  --border-strong: #C3CDDA;

  --accent:        #2A62C4;  /* 5.8:1 */
  --accent-fill:   #2A62C4;
  --accent-on:     #FFFFFF;
  --accent-hover:  #22539F;
  --accent-active: #1C4585;
  --accent-wash:   rgba(42, 98, 196, 0.10);

  --mkt-up:        #D93025;  /* 4.8:1，比深色版更深 */
  --mkt-down:      #0C7B54;  /* 5.3:1 */
  --mkt-flat:      #6B7787;
  --mkt-up-wash:   rgba(217, 48, 37, 0.09);
  --mkt-down-wash: rgba(12, 123, 84, 0.09);
  --mkt-flat-wash: rgba(107, 119, 135, 0.08);

  --st-ok:         #12758A;  /* 5.3:1 */
  --st-warn:       #96690F;  /* 4.9:1 */
  --st-fail:       #C0334F;  /* 5.5:1 */
  --st-idle:       #6B7787;
  --st-ok-fill:    #12758A;
  --st-warn-fill:  #96690F;
  --st-fail-fill:  #C0334F;
  --st-idle-fill:  #6B7787;
  --st-ok-wash:    rgba(18, 117, 138, 0.10);
  --st-warn-wash:  rgba(150, 105,  15, 0.10);
  --st-fail-wash:  rgba(192,  51,  79, 0.10);
  --st-idle-wash:  rgba(107, 119, 135, 0.08);

  --chart-1: #3D72B8;
  --chart-2: #2F7F77;
  --chart-3: #96762F;
  --chart-4: #66707F;
  --chart-5: #8E5C48;
  --chart-6: #4F6291;

  --chart-axis:       #C3CDDA;
  --chart-split:      #EBEFF5;
  --chart-label:      #5A697C;
  --chart-crosshair:  #33404F;
  --chart-tooltip-bg: #FFFFFF;

  --elev-ring:    inset 0 0 0 1px var(--border);
  --elev-overlay: 0 8px 24px rgba(16, 21, 29, 0.12);
}
```

**主题默认策略**：深色为默认（`<html data-theme="dark">`），浅色为显式切换。这与研究结论一致——长会话工具（每天开 8 小时）应深色默认，浅色是覆盖，而不是反过来。同时提供 `@media (prefers-color-scheme: light)` 在**用户未做过选择时**采用浅色，兼顾 GitHub Pages 上偶然点进来的浏览者。切换状态写入 `localStorage`。

### 2.4 状态语义总表

| 语义 | Token | 深色 hex | 图标（Lucide） | 中文标签 | 英文标签 | 触发条件示例 |
|---|---|---|---|---|---|---|
| 健康 / 通过 | `--st-ok` | `#2E9BAF` | `check-circle-2` | 正常 | OK | 检查通过；数据在 SLA 内 |
| 警告 / 降级 | `--st-warn` | `#C99A3B` | `alert-triangle` | 陈旧 / 降级 | STALE / DEGRADED | 超过 SLA 但未超硬阈值；部分字段缺失 |
| 失败 / 中断 | `--st-fail` | `#E14A63` | `x-octagon` | 失败 | FAIL | 检查未通过；采集异常；质量门拦截 |
| 未知 / 未运行 | `--st-idle` | `#5E6B7E` | `circle-dashed` | 未运行 | N/A | 步骤跳过；无数据；本次未调度 |

| 行情语义 | Token | 深色 hex | 方向符 | 规则 |
|---|---|---|---|---|
| 涨 | `--mkt-up` | `#F6564B` | `▲` | **红涨**（中国 A 股 / 港股惯例）。数值必带 `+` 号 |
| 跌 | `--mkt-down` | `#17BE86` | `▼` | **绿跌**。数值必带 `−` 号（U+2212 减号，非连字符） |
| 平 | `--mkt-flat` | `#8290A4` | `—` | 变化为 0、停牌、无前值 |

> 方向符 `▲ ▼ —` 属 Unicode 几何形状区（U+25B2 / U+25BC / U+2014），**不是 emoji**，无彩色 emoji 表现形式，可安全使用。如遇个别环境渲染为彩色，追加变体选择符 `U+FE0E`。
> 减号使用 `−` (U+2212) 而非 `-`，因为它在等宽字体中与加号 `+` 等宽，保证列对齐。

### 2.5 数据枚举 → Token 映射（对齐架构师数据契约）

下面的枚举字符串直接来自 `DATA_CONTRACT.md` / `INTERFACES.md`（高见远，v1.0）。**模板层的 `data-*` 属性值必须使用这些真实枚举（全小写），禁止自造 `ok/warn/fail` 这类抽象词**——抽象词只作为本节内部 4 态视觉聚合（ok / warn / fail / idle）存在。前端用一个 `STATUS_TOKEN_MAP` 把枚举映射到 `--st-*` token。这样设计系统对外的契约与数据层完全一致，前端无需二次翻译。

**状态通道 S（系统 / 质量 / 管道）**

| 数据字段 | 枚举值 | 视觉聚合 | Token | 图标（Lucide） | 中文 |
|---|---|---|---|---|---|
| `series_health.state` | `healthy` | ok | `--st-ok` | `check-circle-2` | 健康 |
| | `degraded` | warn | `--st-warn` | `alert-triangle` | 降级 |
| | `blocked` | fail | `--st-fail` | `x-octagon` | 阻断 |
| | `unknown` | idle | `--st-idle` | `circle-dashed` | 未知 |
| `pipeline_runs.state` | `PASS` | ok | `--st-ok` | `check-circle-2` | 通过 |
| | `DEGRADED` | warn | `--st-warn` | `alert-triangle` | 降级 |
| | `BLOCKED` | fail | `--st-fail` | `x-octagon` | 阻断 |
| | `FAILED` | fail | `--st-fail` | `x-octagon` | 失败 |
| | `RUNNING` | idle+脉冲 | `--st-idle` | `loader` | 运行中 |
| `GateVerdict` (`quality/gate.py`) | `PASS` | ok | `--st-ok` | `check-circle-2` | 通过 |
| | `DEGRADED` | warn | `--st-warn` | `alert-triangle` | 降级 |
| | `BLOCKED` | fail | `--st-fail` | `x-octagon` | 阻断 |
| `StepStatus` (`step_runs`) | `OK` | ok | `--st-ok` | `check-circle-2` | 通过 |
| | `FAILED` | fail | `--st-fail` | `x-octagon` | 失败 |
| | `SKIPPED` | idle | `--st-idle` | `circle-dashed` | 跳过 |
| `Severity` (`quality_findings`) | `INFO` | idle（低权重，不计入失败） | `--st-idle` | `info` | 提示 |
| | `WARNING` | warn | `--st-warn` | `alert-triangle` | 警告 |
| | `BLOCKING` | fail（`risk_essential` 触发 `BLOCKED` 门） | `--st-fail` | `x-octagon` | 阻断 |

**行情通道 M（决策 / 对账）— 沿用 §2.4 红涨绿跌**

| 数据字段 | 枚举值 | Token | 方向符 | 中文 |
|---|---|---|---|---|
| `Decision.stance` / `Signal.direction` | `long` | `--mkt-up`（红） | `▲` | 看多 |
| | `short` | `--mkt-down`（绿） | `▼` | 看空 |
| | `flat` | `--mkt-flat` | `—` | 中性 |
| | `no_call` | `--mkt-flat`（灰） | `—` | 不表态（闸门拦截时如实记录，不省略） |
| `opinion_ledger.outcome` | `hit` | `--mkt-up`（红） | `▲` | 命中 |
| | `miss` | `--mkt-down`（绿） | `▼` | 未中 |
| | `void` | `--mkt-flat`（灰） | `—` | 作废 |
| | `pending` | `--st-idle` | `◌` | 待到期 |

**质量门 6 检查项**（`QualityCheck.check_id`，每个一个文件）：`freshness` · `completeness` · `duplicates` · `consistency` · `continuity` · `range` —— 直接作为质量门矩阵的行（或列）标识。

**`HealthRow` 三重编码约束（INTERFACES.md §9）**：`label_text` + `icon_id` + `state` 三者必填，"模板不得只用颜色区分"。这与本方案的双通道隔离协议 + `[data-palette="cvd"]` 色觉安全模式完全对齐——前端渲染 `HealthRow` 时必须同时输出文字标签与图标，颜色只是第三重编码。

**前端映射建议**（放进 `tokens.css` 或 `app.css`）：

```css
/* 状态通道：真实枚举 → 4 态视觉聚合 */
[data-s="healthy"],[data-s="pass"],[data-s="ok"],
[data-s="running"]:not([data-pulse]) { color: var(--st-ok); }
[data-s="degraded"],[data-s="warning"] { color: var(--st-warn); }
[data-s="blocked"],[data-s="failed"] { color: var(--st-fail); }
[data-s="unknown"],[data-s="skipped"],[data-s="info"] { color: var(--st-idle); }
[data-s="running"] { animation: st-pulse 1.6s ease-in-out infinite; }
@keyframes st-pulse { 0%,100%{opacity:1} 50%{opacity:.45} }

/* 行情通道：真实枚举 → 涨跌色（红涨绿跌） */
[data-m="long"],[data-m="hit"]   { color: var(--mkt-up); }
[data-m="short"],[data-m="miss"] { color: var(--mkt-down); }
[data-m="flat"],[data-m="no_call"],[data-m="void"] { color: var(--mkt-flat); }
[data-m="pending"] { color: var(--st-idle); }
```

---

## 3. Typography Rules（排版规则）

### 3.1 两个字体角色，没有第三个

| 角色 | 变量 | 用途 | 方案 |
|---|---|---|---|
| 数据字体 | `--font-data` | **所有数字**、ticker 代码、时间戳、哈希、代码片段、方向符 | **JetBrains Mono**（SIL OFL 1.1），自托管 woff2 子集 |
| 界面字体 | `--font-ui` | 中英混排的标题、标签、说明、按钮文案 | 系统栈（见下） |

### 3.2 为什么这样选（工程约束下的诚实取舍）

**数据字体自托管 JetBrains Mono 的理由：**
- **点心零**：`0` 中间有点，与字母 `O` 不会混。金融数据里 `0.08` 和 `O.O8` 的区别是致命的。
- **等宽表格数字**：价格列上下对齐，扫读时数量级一眼可辨。
- 只需两个字重（400 / 500），仅子集化 Latin + 数字 + 常用标点，**每个 woff2 约 20-28KB，总计约 50KB**。这是整个仓库唯一的字体二进制，可接受。
- SIL OFL 1.1 允许自由再分发，开源项目无许可风险。

**界面字体走系统栈、不打包 CJK 的理由：**
- 思源黑体 / Noto Sans SC 全量 8MB+，即使子集化也要 1-2MB。对一个"clone 下来就能跑"的开源仓库，这个体积不可接受，且首屏会闪烁。
- Bloomberg / TradingView / Grafana 的界面框架文字全部使用系统 UI 字体——这是数据终端的正确选择，不是偷懒。
- 系统栈已明确枚举每个平台的具体字面（含 CJK），并锁定了字重、字距、`font-variant-numeric`，是**被设计过的排版系统**，不是 `font-family: sans-serif` 直出。

```css
--font-ui: -apple-system, BlinkMacSystemFont,
           "Segoe UI Variable Text", "Segoe UI",
           "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei", "Noto Sans SC",
           sans-serif;
```

对应关系：macOS/iOS → SF Pro + 苹方；Windows 11 → Segoe UI Variable + 微软雅黑；Windows 10 → Segoe UI + 微软雅黑；Linux → Noto Sans SC。

```css
@font-face {
  font-family: "JetBrains Mono";
  src: url("../fonts/JetBrainsMono-Regular-subset.woff2") format("woff2");
  font-weight: 400; font-style: normal; font-display: swap;
}
@font-face {
  font-family: "JetBrains Mono";
  src: url("../fonts/JetBrainsMono-Medium-subset.woff2") format("woff2");
  font-weight: 500; font-style: normal; font-display: swap;
}
```

### 3.3 数字排版铁律（违反即为 bug）

```css
/* 全局：任何承载数字的元素 */
.num, td.num, .kpi-value, .ticker, .ts {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;   /* 强制等宽数字，禁止比例数字 */
  font-feature-settings: "tnum" 1, "zero" 1;
  text-align: right;                     /* 数字一律右对齐 */
  letter-spacing: var(--tracking-data);
  white-space: nowrap;
}
th.num { text-align: right; }            /* 表头跟随数据列对齐 */
```

1. **数字右对齐，文本左对齐。** 右对齐让小数点成列，量级差异（1,203 vs 12,030）一眼可见。
2. **`tabular-nums` 全局强制。** 比例数字会让刷新时的数字宽度跳动。
3. **千分位分隔用窄空格或逗号，全项目统一为逗号。** 小数位数由字段类型固定，不做自适应（价格 2 位、百分比 2 位、评分 1 位）。
4. **单位、货币符号用 `--text-2xs` + `--meta`**，与数值本体拉开层级，不参与对齐。
5. **新鲜度位置只显示业务日期，不显示相对时间**。健康区块（及任何与新鲜度相邻的位置）显示 `last_event_label`（DataPack 预格式化的业务日期 + 周几，如 `07-31（周五）`），与进度条同属交易日时钟，不可能背离。相对时间（「X 小时前」）由写入时间派生，测的是「管道多久前碰过这个源」而非「数据多旧」，会系统性低估陈旧度，**禁止出现在健康区块**。管道存活（写入时间）是本次运行的单一事实，不在每序列重复，移到页脚 `run_footer` 全局一处（见 INTERFACES `RunFooter`）。

### 3.4 字距与字重

| 场景 | 字号 | 字重 | 字距 | 行高 |
|---|---|---|---|---|
| 主 KPI / 健康总分 | 28px | 600 | −0.02em | 1.15 |
| KPI 数值 | 22px | 500 | −0.02em | 1.2 |
| 区块标题 | 18px | 600 | −0.01em | 1.3 |
| 面板标题 | 16px | 600 | 0 | 1.3 |
| 中文段落 | 14px | 400 | 0 | 1.6 |
| 表格数据行 | 13px | 400 | 0.01em | 1.35 |
| 表格数据（强调列） | 13px | 500 | 0.01em | 1.35 |
| 标签 / 表头（ALL CAPS） | 12px | 500 | **0.08em** | 1.3 |
| 单位 / 角标 | 11px | 400 | 0.02em | 1.2 |

**ALL CAPS 必须加 0.08em 字距**，否则大写字母挤在一起不可读。这条是工艺分水岭。

**正文基准偏离说明**：常规规范要求正文 16px，本项目 body 基准为 14px、数据行 13px。理由是 VISUAL_DENSITY = 8，对齐 TradingView / Grafana / Linear 表格的实际密度。约束：
- 硬地板 11px，且 11px **仅限单位与角标**，不得单独承载关键信息。
- 页面上任何**长段落说明文字**（方法论解释、免责声明）必须提升到 `--text-lg` 16px、行高 1.6。
- 移动端断点下，数据行从 13px 提升到 14px（见第 8 节）。

---

## 4. Component Stylings（组件样式）

### 4.1 面板（Panel）—— 不是卡片

面板是本看板唯一的内容容器。**它不是"卡片"**：无阴影、无彩色左边框、圆角上限 8px。

```css
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--elev-flat);          /* 明确：无阴影 */
  overflow: hidden;
}
.panel__head {
  height: var(--panel-head-h);
  display: flex; align-items: center; gap: var(--space-2);
  padding: 0 var(--panel-pad);
  border-bottom: 1px solid var(--border-strong);
  font: var(--weight-announce) var(--text-lg)/1.3 var(--font-ui);
  color: var(--fg);
}
.panel__head .ico { width: 20px; height: 20px; color: var(--muted); }
.panel__head-meta {                       /* 右侧对齐的更新时间等 */
  margin-left: auto;
  font: var(--weight-read) var(--text-xs)/1.3 var(--font-data);
  color: var(--meta);
}
.panel__body { padding: var(--panel-pad); }
.panel__body--flush { padding: 0; }       /* 表格类面板：表格自己带 padding */
```

**面板状态轨（唯一允许的"左边框强调"例外）**：仅当面板整体聚合状态为 `degraded` / `blocked` 时，允许在面板**顶部**加 2px 状态色横轨（不是左边框）。`healthy` 无轨，`unknown` 无轨。聚合态由面板内最严重子项决定（`blocked` > `degraded` > `unknown` > `healthy`）。

```css
.panel[data-state="degraded"] { box-shadow: inset 0 2px 0 0 var(--st-warn); }
.panel[data-state="blocked"]  { box-shadow: inset 0 2px 0 0 var(--st-fail); }
```

反模式说明：常规设计规范禁止"圆角卡片 + 彩色左边框"，因为那是被滥用的 AI 装饰。这里改为**顶部轨 + 仅异常态出现**，它承载真实语义（这个面板有问题），且 95% 时间不出现，因此不构成装饰噪音。

### 4.2 状态指示器（Status Indicator）

三重编码：图标形状 + 颜色 + 文字。**任一单独出现都不合格。**

```css
.status {
  display: inline-flex; align-items: center; gap: var(--space-1);
  font: var(--weight-emph) var(--text-xs)/1.3 var(--font-ui);
  white-space: nowrap;
}
.status .ico { width: 16px; height: 16px; flex: none; }
/* 详见 §2.5：data-s 值为真实枚举（全小写），4 态聚合由选择器覆盖 */
.status[data-s="healthy"],.status[data-s="pass"],.status[data-s="ok"] { color: var(--st-ok); }
.status[data-s="degraded"],.status[data-s="warning"] { color: var(--st-warn); }
.status[data-s="blocked"],.status[data-s="failed"] { color: var(--st-fail); }
.status[data-s="unknown"],.status[data-s="skipped"],.status[data-s="info"],.status[data-s="running"] { color: var(--st-idle); }

/* 徽章形态：用于列表 / 表格单元格 */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  height: 20px; padding: 0 6px;
  border-radius: var(--radius-xs);
  font: var(--weight-emph) var(--text-2xs)/1 var(--font-ui);
  letter-spacing: var(--tracking-caps); text-transform: uppercase;
}
.badge[data-s="healthy"],.badge[data-s="pass"],.badge[data-s="ok"] { background: var(--st-ok-fill);   color: #FFFFFF; }
.badge[data-s="degraded"],.badge[data-s="warning"] { background: var(--st-warn-fill); color: #FFFFFF; }
.badge[data-s="blocked"],.badge[data-s="failed"] { background: var(--st-fail-fill); color: #FFFFFF; }
.badge[data-s="unknown"],.badge[data-s="skipped"],.badge[data-s="info"],.badge[data-s="running"] { background: var(--st-idle-fill); color: var(--fg-2); }
```

在**高密度矩阵**中，允许省略文字标签，改用 16px 图标 + `title` 属性 + `aria-label`，但表格必须有图例（legend）说明四种图标含义。

### 4.3 涨跌数字（Delta）

```css
.delta {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
  font-weight: var(--weight-emph);
  text-align: right;
}
.delta[data-d="up"]   { color: var(--mkt-up); }
.delta[data-d="down"] { color: var(--mkt-down); }
.delta[data-d="flat"] { color: var(--mkt-flat); }
.delta::before { margin-right: 4px; font-weight: 400; }
.delta[data-d="up"]::before   { content: "▲"; }
.delta[data-d="down"]::before { content: "▼"; }
.delta[data-d="flat"]::before { content: "—"; }

/* 表格行低透明度底纹（可选，用于突出当日异动） */
tr[data-d="up"]   td { background: var(--mkt-up-wash); }
tr[data-d="down"] td { background: var(--mkt-down-wash); }
```

`--mkt-*` 只允许出现在 `.delta` 及其行底纹上。任何 `.badge`、`.ico`、`button` 上出现行情色即为越界。

### 4.4 数据表（Table）—— 看板的主力组件

```css
.tbl { width: 100%; border-collapse: collapse; }
.tbl th {
  height: var(--row-h);
  padding: 0 var(--cell-px);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border-strong);
  font: var(--weight-emph) var(--text-xs)/1.3 var(--font-ui);
  letter-spacing: var(--tracking-caps); text-transform: uppercase;
  color: var(--muted); text-align: left;
  position: sticky; top: var(--topbar-h); z-index: 2;
}
.tbl td {
  height: var(--row-h);
  padding: 0 var(--cell-px);
  border-bottom: 1px solid var(--border-soft);
  font: var(--weight-read) var(--text-sm)/var(--leading-data) var(--font-ui);
  color: var(--fg-2);
}
.tbl td:first-child { color: var(--fg); font-weight: var(--weight-emph); }
.tbl tbody tr:hover td { background: var(--surface-2); }
.tbl tbody tr:last-child td { border-bottom: 0; }
```

表格规则：
- 无斑马纹（zebra stripe）。1px `--border-soft` 分隔线已提供足够节奏，斑马纹会与 `--mkt-*-wash` 底纹冲突。
- 表头 sticky，粘在顶部状态栏下方。
- 首列为标识列（数据源名 / ticker），使用 `--fg` + 字重 500，其余列 `--fg-2`。
- 每个 `<table>` 必须有 `<caption class="sr-only">` 描述内容，`<th scope="col|row">` 完整标注。

### 4.5 质量门矩阵（Quality Gate Matrix）—— 看板的签名视觉

这是 APEXFIN 与任何通用看板模板最不一样的一块，也是数据治理卖点的视觉化身。**6 类检查 × N 个数据源的矩阵**，单元格是 16px 状态图标。

```
                 新鲜度  完整性  重复性  一致性  连续性  合理性
                 FRESH   COMPL   DUP     CONSIST CONTIN  RANGE
  yahoo/equity     [+]     [+]     [+]     [+]     [!]     [+]
  yahoo/index      [+]     [+]     [+]     [+]     [+]     [+]
  fred/rates       [+]     [!]     [+]     [+]     [+]     [+]
  fred/cpi         [~]     [+]     [+]     [+]     [+]     [+]
```

规格：
- 单元格 `--row-h-compact` 24px 高、40px 宽，图标 16px 居中。
- 表头双语：中文 12px `--muted` 为主，英文缩写 11px `--meta` 为辅，垂直两行。
- 每个单元格 `title` = `"{数据源} · {检查项}：{状态}（{实际值} / 阈值 {阈值}）"`，`aria-label` 同文。
- 单元格可聚焦（`tabindex="0"`），键盘可遍历，聚焦时显示同样的 tooltip。
- 矩阵下方必须有**四态图例**。
- 行末追加一列"通过率"：`5/6` 等宽数字 + 一条 3px 高的进度条（`--st-ok` / `--st-warn` / `--st-fail` 按阈值着色）。

### 4.6 新鲜度指示（Freshness）

```
  yahoo/equity   ● 正常    最后数据 07-31（周五）   [----------]  阈值 1 交易日 · 余 1
  fred/rates     ▲ 陈旧    最后数据 07-30（周四）   [##########]  阈值 1 交易日 · 余 0   ← 临界，未超期
  fred/cpi       ▲ 失败    最后数据 07-29（周三）   [##########]  阈值 1 交易日 · 超 1
  fixture/vol    ▲ 降级    最后数据 07-29（周三）   [##########]  阈值 1 交易日 · 超 1 · support   ← 状态琥珀 + 进度条红（overdue≠state）
  fred/new       ◌ 未知    —                       （无进度条）从未采集（建库后首跑）
```

- 状态点 + 文字标签 + 业务日期（`last_event_label`，含周几，等宽）+ 4px 高余量条 + 新鲜度说明。
- **嵌套模型（依架构师 INTERFACES 9.1）**：`HealthRow.freshness: FreshnessBar | None`，`FreshnessBar = { bar_value, bar_max, overdue, label }`。`freshness` 为 `None`（即 `state = unknown`，从未采集）时**整条进度条不渲染**，改渲染 `circle-dashed` + 空状态文案（原因取 `note`）。
- 进度条只认 `FreshnessBar` 的**预计算字段**，模板不自己算滞后（避免 ARIA 非法值）：
  - `aria-valuenow = freshness.bar_value`（DataPack 已 clamp，保证 `≤ bar_max`）
  - `aria-valuemax = freshness.bar_max`（保证 `≥ 1`，即 `max(max_lag_trading_days, 1)`）
  - 宽度 = `bar_value / bar_max`（clamp 后，超期也只到 100%）
  - 真实滞后值不丢，在 `freshness.label`（如「lag 3 交易日 / 阈值 1 交易日」）与 `note` 里。
- **进度条不表达超期幅度**：满轨即超期，超多少看文本。若改用动态量程表达「超 3 倍」，不同行之间就无法横向比较——而健康轨的最大价值正是一眼扫出哪行更糟，故不采用。
- **三边界（ARCHITECTURE 5.3.2）**：
  1. **lag > max（超期）**：`bar_value` 已 clamp 到 `bar_max`，`overdue=true` 驱动满轨配色；文本如实写「超 M 交易日」。例 lag=3,max=1 → `aria-valuenow=1 aria-valuemax=1 overdue`，label「lag 3 / 阈值 1」。
  2. **max = 0**（要求当天必有的源）：`bar_max = max(0,1) = 1`；lag=0 空轨，lag≥1 满轨 + overdue，文本「阈值 0 交易日」。
  3. **lag = NULL（state = unknown）**：`freshness = None`，**不渲染进度条**，渲染 `circle-dashed` + 空状态文案（原因取 `note`）。
- **`overdue` 不等价于状态色（语义陷阱）**：状态色 / 状态图标 / 状态文字**只认 `state`**；进度条超期配色**认 `overdue`**。两者可不同步——`support` 档超期是 `degraded`（状态琥珀），但 `overdue` 让进度条满轨显示超期色（失败红）。同一行「状态琥珀 + 进度条红」是对的，不是 bug。模板用 `data-overdue="true"` 单独控制进度条色，与 `data-s`（state）分离。
- **健康区块内不渲染相对时间（撤回初版授权，ARCHITECTURE 5.3.1.1）**：相对时间由写入时间派生，测的是「管道多久前碰过这个源」而非「数据多旧」，会系统性低估陈旧度（管道越勤越好看、越掩盖问题），与进度条的交易日时钟并排且未标注即把 O-07 拆开的两个概念又粘回去了。故该位置改为显示业务日期本身 `last_event_label`（`last_event_date` 是日粒度，本就派不出「X 小时前」）。相对时间**禁止**出现在健康区块及任何新鲜度相邻位置。管道存活（写入时间）是本次运行的单一事实，移到页脚 `run_footer` 全局一处（来源 `pipeline_runs.finished_at`）。
- 余量条 `role="progressbar"`，`aria-label` 写交易日表述（含真实滞后，如「fred/cpi 已超阈值 1 个交易日（lag 2 / 阈值 1）」）。
- 标签文案（`freshness.label` 由 DataPack 预格式化，模板不拼）：未超阈值 `阈值 {max} 交易日 · 余 {max-lag}`；已超阈值 `阈值 {max} 交易日 · 超 {lag-max}`。
- **CI 锁（架构师加）**：`src/apexfin/**` 与 `config/**` 出现标识符 `lag_hours` / `sla_hours` / `sla_ratio` 即构建失败。本设计文档与模板**不引用**这些标识符，新鲜度只用交易日数。
- **HealthRow 字段（INTERFACES 9.1，已补齐）**：`source_name` `symbol` `state`(4态) `label_text` `icon_id` `tone`(ok/warn/danger/muted) `lag_trading_days`(int|None) `max_lag_trading_days`(int) `freshness`(FreshnessBar|None) `last_event_date`(date|None) `last_event_label`(str|None，如 `07-31（周五）`) `note`(str|None)。`label_text`/`icon_id`/`tone`/`last_event_label` 由 `datapack.py` 按 `state`/`last_event_date` 集中映射，模板不自行判断、不拼字符串。**HealthRow 中不含任何写入时间字段**——`last_checked_at` 留在 `series_health` 表但不进视图模型；管道存活是本次运行的单一事实，由 `DataPack.run_footer` 承载，全局渲染一处。本设计以 `state` 为 `data-s` 单一来源；`tone` 是其 1:1 展示别名（ok=healthy、warn=degraded、danger=blocked、muted=unknown）。
- **freshness 检查项文本**：质量门矩阵里 `freshness` 单元格的 `cell_value` / `cell_tooltip` 统一用 `freshness.label` 格式「lag 2 交易日 / 阈值 1 交易日」，由 DataPack 预格式化，模板不拼字符串（§4.3 矩阵同此约束）。

### 4.7 按钮

```css
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 28px; padding: 0 10px;
  border-radius: var(--radius-md);
  font: var(--weight-emph) var(--text-xs)/1 var(--font-ui);
  border: 1px solid transparent; cursor: pointer;
  transition: background var(--motion-fast) var(--ease-standard),
              border-color var(--motion-fast) var(--ease-standard);
}
.btn .ico { width: 20px; height: 20px; }

.btn--primary   { background: var(--accent-fill); color: var(--accent-on); }
.btn--primary:hover  { background: var(--accent-hover); }
.btn--primary:active { background: var(--accent-active); }

.btn--secondary { background: transparent; border-color: var(--border-strong); color: var(--fg-2); }
.btn--secondary:hover { background: var(--surface-2); border-color: var(--accent); color: var(--fg); }

.btn--ghost { background: transparent; color: var(--muted); }
.btn--ghost:hover { background: var(--surface-2); color: var(--fg); }

.btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.btn[disabled] { opacity: .45; cursor: not-allowed; }
```

注意：按钮高度 28px 是桌面密集模式。**移动端断点下所有可点击元素强制 ≥44×44px**（见第 8 节）。

### 4.8 渐进披露（Disclosure）

静态页面无框架，用原生 `<details>` 实现"检查详情"、"原始数据表"、"方法论说明"的展开。

```css
details > summary {
  cursor: pointer; list-style: none;
  display: flex; align-items: center; gap: 6px;
  height: var(--row-h); padding: 0 var(--cell-px);
  font: var(--weight-emph) var(--text-xs)/1 var(--font-ui);
  color: var(--muted);
  border-radius: var(--radius-sm);
}
details > summary::-webkit-details-marker { display: none; }
details > summary:hover { background: var(--surface-2); color: var(--fg); }
details > summary:focus-visible { outline: none; box-shadow: var(--focus-ring); }
details > summary .ico { transition: transform var(--motion-base) var(--ease-standard); }
details[open] > summary .ico { transform: rotate(90deg); }   /* chevron-right */
```

---

## 5. Layout Principles（布局原则）

### 5.1 栅格

| 断点 | 栅格 | 沟槽 | 容器 |
|---|---|---|---|
| ≥1280px | 12 栏 | 24px | `min(100% - 48px, 1440px)` |
| 1024–1279px | 12 栏 | 16px | `100% - 32px` |
| 768–1023px | 6 栏 | 16px | `100% - 32px` |
| <768px | 1 栏 | 12px | `100% - 24px` |

`DESIGN_VARIANCE = 3` → **严格对称栅格，不做非对称留白、不做 masonry、不做负 margin 重叠。** 面板宽度只允许 12 / 8 / 6 / 4 / 3 栏这几个值。

### 5.2 首屏结构（无 Hero 区，第一屏即数据）

```
┌─ 顶部状态栏 (sticky, 44px) ────────────────────────────────────┐
│ APEXFIN  |  数据截止 2026-08-02 14:03 +08  |  ● 全局健康 22/24  │
│                        run f3a91c2 · [主题切换] │
├─ 数据健康度总览 (12 栏, 横向 rail, 非卡片) ───────────────────┤
│ ● yahoo/equity 07-31（周五）  ● yahoo/index 07-31（周五）  ▲ fred/cpi 07-29（周三）  ...     │
├──────────────────────────────┬────────────────────────────────┤
│ 价格走势 (8 栏)              │ 宏观指标 (4 栏)                │
│  ECharts K线 / 折线          │  密集数字列表                  │
│  + <details> 数据表降级      │  利率 / 通胀 / 失业率          │
├──────────────────────────────┼────────────────────────────────┤
│ 质量门矩阵 (6 栏)            │ 管道执行 (6 栏)                │
│  6 类检查 × N 数据源         │  步骤 × tier × 状态 × 耗时     │
├──────────────────────────────┴────────────────────────────────┤
│ 决策输出 (12 栏)  —— 信号表 + 顶部免责声明条                  │
├────────────────────────────────────────────────────────────────┤
│ 页脚：上次采集完成 2026-08-02 14:03（+08:00）· 耗时 1m12s · run f3a91c2 · 数据源出处 · 许可 · 免责声明     │
└────────────────────────────────────────────────────────────────┘
```

在 1440px / 900px 视口下，"顶部状态栏 + 健康度总览 + 价格图上半 + 宏观指标"落在首屏。**打开页面看到的第一个像素就是真实数据和真实状态。**

### 5.3 节区节奏

面板间 gap 12px，区块间 32px（桌面）/ 24px（平板）/ 16px（手机）。这个节奏比常规 SaaS（80px）密得多，是 VISUAL_DENSITY = 8 的直接体现。

### 5.4 信息密度策略（金融看板专项）

1. **禁止通用卡片盒子堆叠。** 每一层嵌套容器都要付出边框和内边距的代价。同类内容用 1px `--border-soft` 分隔，不要各自包一层卡片。
2. **分组靠负空间和分隔线，不靠背景色块。** 背景色是层级信号（`--surface` → `--surface-2` → `--surface-3`），不是分组信号。
3. **一屏内的信息分块 ≤ 6 组**（人的工作记忆上限约 4，看板可放宽到 6 但每组必须有明确标题）。当前布局正好 6 个面板。
4. **渐进披露**：每个面板只展示摘要级信息，明细进 `<details>`。质量门矩阵展示状态，具体的期望值 / 实际值进 tooltip 和展开区。
5. **列的取舍**：数据表默认列 ≤ 7 列。次要列（昨收、开盘、最高、最低）折叠进 `<details>` 的"完整数据表"。
6. **"一切正常"必须安静。** 通过态用低彩度青 + 小图标，不用大面积填充。屏幕上的颜色总量应该与"问题数量"成正比。这是 Grafana / Linear 的核心经验，也是我们避免"彩虹看板"的机制。

---

## 6. Depth & Elevation（层级与深度）

深色主题下**用亮度递进表达层级，不用阴影**。阴影在深色底上几乎不可见，强行加只会产生脏边。

| 层 | Token | 深色值 | 用途 |
|---|---|---|---|
| L0 页面底 | `--bg` | `#0B0E14` | body |
| L1 面板 | `--surface` | `#111721` | `.panel` |
| L2 内嵌 | `--surface-2` | `#161D29` | 表头、行 hover、`<details>` 展开区 |
| L3 激活 | `--surface-3` | `#1C2532` | 选中行、当前 tab |
| 浮层 | `--elev-overlay` | `0 8px 24px rgba(0,0,0,.55)` | **仅** tooltip / popover / modal |

规则：
- 面板一律 `box-shadow: none`。
- **严禁**同一元素上同时出现 `1px solid` 边框和 `blur ≥ 16px` 的阴影（幽灵卡片反模式）。
- 浅色主题下才允许 `--elev-overlay` 使用真实投影；深色下浮层主要靠 `--surface-2` + 1px `--border-strong` 建立边界。

---

## 7. Do's and Don'ts

### 允许（Do）

- 用 `--fg` 亮度 + 字重 600 + 字号来做视觉重点。
- 所有数字用 `--font-data` + `tabular-nums` + 右对齐。
- 状态一律三重编码：图标形状 + 颜色 + 文字标签。
- 用 1px 分隔线和负空间做分组。
- 面板顶部 2px 状态轨（仅异常态出现）。
- `<details>` 做渐进披露，零 JS 依赖。
- 每个图表旁提供等价的 `<table>` 降级。
- 健康区块只显示业务日期（`last_event_label`，含周几），不显示相对时间；写入时间只在页脚 `run_footer` 出现一次。
- 中性序列色（`--chart-1..6`）画宏观数据，配图例 + 端点直标。

### 禁止（Don't）

**P0 级（出现即退回重做）**

- 禁止任何 emoji 作为功能图标。图标只来自锁定的 Lucide 雪碧图，尺寸只有 16 / 20 / 24px 三档。
- 禁止紫色→粉色渐变主视觉，禁止 Indigo→Pink 任意渐变，禁止"渐变 + 发光边框 + 毛玻璃"三件套。
- 禁止空洞占位文案："Welcome to APEXFIN" / "Lorem ipsum" / "Get started" / "开启你的量化之旅"。所有文案必须描述具体数据或具体动作。
- 禁止硬编码颜色值。除 `#fff` `#000` 外，一切颜色走 CSS 变量。
- 禁止营销式 Hero 区。第一屏是数据。

**通道越界（本项目专属红线）**

- 禁止用 `--mkt-up` / `--mkt-down` 给图标、徽章、按钮、边框上色。
- 禁止用 `--st-ok` / `--st-fail` 给裸数字上色。
- 禁止用绿色表示"通过"（会与"下跌"撞语义）。通过用青。
- 禁止仅靠颜色传达状态或涨跌。

**工艺级**

- 禁止 `border-radius ≥ 12px`（本项目上限 8px）。
- 禁止面板阴影；禁止 1px 边框 + 大模糊阴影同时出现。
- 禁止斑马纹表格。
- 禁止 `--meta` 承载关键信息（对比度仅 3.5:1）。
- 禁止 ALL CAPS 不加字距。
- 禁止比例数字（必须 `tabular-nums`）。
- 禁止连字符 `-` 当负号（用 U+2212 `−`）。
- 禁止装饰性动画、入场动画、滚动视差。动效只服务状态反馈。
- 禁止虚构数据。示例数据必须有机（`47.2%` 而非 `50%`），且页脚必须写明"示例数据来自 Yahoo Finance / FRED 公开接口，采集于 {真实时间}"。
- 禁止把玩具级策略包装成投资建议。决策输出面板顶部必须有 `--st-warn` 免责条。

---

## 8. Responsive Behavior（响应式）

| 断点 | 布局 | 密度调整 |
|---|---|---|
| ≥1280px | 12 栏，8/4 + 6/6 + 12 三行 | 数据行 13px，行高 28px |
| 1024–1279px | 12 栏，8/4 + 6/6 + 12（沟槽缩到 16px） | 同上 |
| 768–1023px | 6 栏 → 面板两两并排，图表全宽 | 数据行 13px，行高 28px |
| <768px | 单栏堆叠 | **数据行升到 14px，行高升到 36px** |

移动端专项规则：

1. **触摸目标 ≥44×44px**。桌面 28px 高的按钮、`<summary>`、状态单元格在 `<768px` 全部提升到 44px 高，相邻间距 ≥8px。
2. **顶部状态栏折行**：`APEXFIN + 全局健康` 一行，`数据截止 + run id` 第二行，总高 68px。
3. **宽表格横向滚动**：`.tbl-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }`，首列 `position: sticky; left: 0` 冻结标识列，并在滚动容器右侧加渐隐遮罩提示可滚。**禁止整页横向滚动。**
4. **质量门矩阵**在 `<768px` 转置：从"6 检查 × N 源"改为**按数据源分块的纵向列表**，每个数据源一个 `<details>`，摘要行显示 `5/6 通过` + 状态点，展开显示 6 项明细。矩阵在窄屏不可读，必须换形态而不是缩小。
5. **ECharts 响应式**：监听 `resize` 调 `chart.resize()`；`<768px` 时隐藏图例改为端点直标，降低 `axisLabel` 密度（`interval: 'auto'`），K 线默认展示区间收窄到最近 60 根。
6. **禁止禁用缩放**：`<meta name="viewport" content="width=device-width, initial-scale=1">`，不加 `maximum-scale` / `user-scalable=no`。

---

## 9. Agent Prompt Guide（给前端实现的执行指南）

### 9.1 无障碍（必做项）

```css
/* 焦点环：全局，不许移除 */
:where(a, button, summary, [tabindex], input, select):focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
  border-radius: var(--radius-sm);
}

/* 动效降级 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}

/* 高对比度偏好 */
@media (prefers-contrast: more) {
  :root { --border: #3A4759; --border-soft: #2A3444; --muted: #9BA9BD; }
}

/* 屏幕阅读器专用文本 */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
```

检查清单：
- 所有 `<svg class="ico">` 装饰性的加 `aria-hidden="true"`；承载语义的（如矩阵单元格状态）用 `role="img"` + `aria-label`。
- 所有 `<table>` 有 `<caption class="sr-only">` 和 `<th scope>`。
- 所有进度条用 `role="progressbar"` + `aria-valuenow/min/max/text`。
- 所有 `title` tooltip 同时提供 `aria-label`（`title` 对键盘用户不可达）。
- 页面有 `<a class="skip-link" href="#main">跳到主要内容</a>`。
- `<html lang="zh-CN">`。
- 对比度全部已在第 2 节标注，正文级最低 4.6:1，`--meta` 3.5:1 已限定用途。

### 9.2 ECharts 主题配置方向

创建 `assets/js/apexfin-echarts-theme.js`，从 CSS 变量读取，保证主题切换时图表跟随：

```js
const css = (v) => getComputedStyle(document.documentElement)
                     .getPropertyValue(v).trim();

function apexfinTheme() {
  return {
    color: [css('--chart-1'), css('--chart-2'), css('--chart-3'),
            css('--chart-4'), css('--chart-5'), css('--chart-6')],
    backgroundColor: 'transparent',          // 让面板背景透出，不要图表自带底色
    textStyle: { fontFamily: css('--font-ui'), fontSize: 12 },
    animation: false,                        // MOTION_INTENSITY = 2：图表不做入场动画
    grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },

    categoryAxis: {
      axisLine:  { lineStyle: { color: css('--chart-axis') } },
      axisTick:  { show: false },
      axisLabel: { color: css('--chart-label'), fontFamily: css('--font-data'), fontSize: 11 },
      splitLine: { show: false }
    },
    valueAxis: {
      axisLine:  { show: false },
      axisTick:  { show: false },
      axisLabel: { color: css('--chart-label'), fontFamily: css('--font-data'), fontSize: 11 },
      splitLine: { lineStyle: { color: css('--chart-split'), width: 1 } }   // 网格线弱到"需要时才存在"
    },

    // 中国 A 股惯例：阳线(涨)=红，阴线(跌)=绿
    candlestick: {
      itemStyle: {
        color:        css('--mkt-up'),     // 阳线实体
        color0:       css('--mkt-down'),   // 阴线实体
        borderColor:  css('--mkt-up'),
        borderColor0: css('--mkt-down'),
        borderWidth: 1
      }
    },

    line: { symbol: 'none', lineStyle: { width: 1.5 }, smooth: false },
    bar:  { itemStyle: { borderRadius: [2, 2, 0, 0] } },

    tooltip: {
      backgroundColor: css('--chart-tooltip-bg'),
      borderColor: css('--border-strong'),
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: css('--fg'), fontFamily: css('--font-data'), fontSize: 12 },
      axisPointer: {
        type: 'cross',
        lineStyle:  { color: css('--chart-crosshair'), width: 1, type: 'dashed' },
        crossStyle: { color: css('--chart-crosshair'), width: 1, type: 'dashed' },
        label: { backgroundColor: css('--surface-3'), color: css('--fg'),
                 fontFamily: css('--font-data'), borderColor: css('--border-strong') }
      }
    },
    legend: {
      textStyle: { color: css('--muted'), fontSize: 11 },
      icon: 'roundRect', itemWidth: 10, itemHeight: 2
    }
  };
}

// 主题切换时重建
document.addEventListener('apexfin:theme-change', () => {
  echarts.registerTheme('apexfin', apexfinTheme());
  window.__apexfinCharts?.forEach(c => { const o = c.getOption(); c.dispose(); /* 重新 init */ });
});
```

图表规则：
- **成交量柱**用 `--mkt-up` / `--mkt-down` 但 opacity 降到 0.4（研究结论：成交量是次要信息，不应与价格竞争视觉）。
- **宏观折线**只用 `--chart-1..6` 中性序列，**绝不用行情红绿**——避免暗示"CPI 上升 = 好消息"。
- 每条宏观折线必须有图例 + 端点直标（`endLabel: { show: true }`），不依赖颜色识别。
- `--chart-split` 网格线极弱，宁可少也不要多。
- 图表内不出现渐变填充（`areaStyle` 若必须用，透明度上限 0.10 且同色系单色）。

### 9.3 离线与降级（设计要求，实现归架构）

三层降级，任一层失效上一层仍可用：

1. **本地优先加载**：`assets/vendor/echarts.min.js` 随仓库分发。若使用 CDN，必须 `onerror` 回退本地。
2. **图表引擎缺失降级**：每个图表容器旁由 Jinja2 同步渲染一个 `<details class="chart-fallback"><summary>数据表</summary><table>…</table></details>`。检测到 `typeof echarts === 'undefined'` 时：强制 `details[open]`，并在图表位插入一条 `--st-warn` 提示条「图表引擎未加载，已降级为数据表」。
3. **无 JS 降级**：`<noscript>` 内给出同样提示，且所有 `<details>` 默认 `open`。页面在完全无 JS 环境下仍然是一份完整可读的报告。这对 GitHub Pages 抓取、README 截图、邮件转发都有直接价值。

**字体降级**：`font-display: swap`，JetBrains Mono 未加载时回落系统等宽栈，`tabular-nums` 仍然生效，对齐不破。

**图标降级**：内联 SVG 雪碧图，零网络请求，无降级需求。

### 9.4 文案规范（反 AI 模板的最后一道关）

- 标签用**名词短语**，不用句子：`数据健康度` 不是 `查看你的数据健康度`。
- 空状态写**具体下一步**：`暂无 fred/cpi 数据 —— 该序列本月尚未发布，下次预计 2026-08-12` 而不是 `暂无数据`。
- 错误写**发生了什么 + 怎么办**：`yahoo/equity 采集超时（30s）· 已使用 T-1 缓存 · 重跑：make collect SOURCE=yahoo` 而不是 `加载失败`。
- 数字**永远带出处和口径**：`健康分 5/6` 旁边有 `(通过检查数 / 总检查数)` 的 `title`。
- 免责声明写实话：`决策输出为玩具级参考实现，仅用于演示管道链路，不构成任何投资建议。`
- 页脚写清楚：数据来源（Yahoo Finance、FRED）、采集时间、代码 commit、许可证。

### 9.5 交付前自检清单

**P0（任一不通过即退回）**
- [ ] 用正则 `[\x{1F300}-\x{1F9FF}\x{2600}-\x{26FF}\x{2700}-\x{27BF}]` 扫描全部 `templates/` `assets/` `docs/`，零命中
- [ ] 全局搜索 `#7C3AED` `#A855F7` `#9333EA` `#EC4899` `#6366F1`，零命中
- [ ] 全局搜索 `linear-gradient`，仅允许出现在滚动遮罩，且必须是同色系单色渐隐
- [ ] 全局搜索 `Welcome` `Lorem` `Get started`，零命中
- [ ] 除 `tokens.css` 外，任何 `.css` / `.html` 中零硬编码 hex（`#fff` `#000` 除外）
- [ ] 首屏无 Hero 区，第一个内容块是数据

**通道隔离**
- [ ] 搜索 `--mkt-`，确认只出现在 `.delta` / `tr[data-d]` / ECharts candlestick 与成交量
- [ ] 搜索 `--st-`，确认只出现在 `.status` / `.badge` / `.panel[data-state]` / progressbar
- [ ] 每个状态都有图标 + 文字标签，不存在只有颜色的状态

**排版与密度**
- [ ] 所有数字元素带 `font-variant-numeric: tabular-nums` 且右对齐
- [ ] 所有 ALL CAPS 有 `letter-spacing: 0.08em`
- [ ] 负号是 `−` (U+2212) 不是 `-`
- [ ] 无 11px 以下字号；11px 仅出现在单位 / 角标
- [ ] 长段落说明文字为 16px / 行高 1.6

**无障碍**
- [ ] 键盘可遍历全部交互元素，`focus-visible` 可见
- [ ] `prefers-reduced-motion` 生效
- [ ] 所有表格有 caption 与 th scope
- [ ] 所有 title tooltip 有配套 aria-label
- [ ] 正文对比度 ≥4.5:1（`--meta` 已限定用途）

**响应式与降级**
- [ ] 375px 宽下无横向滚动（表格容器内滚动除外）
- [ ] `<768px` 下点击目标 ≥44×44px
- [ ] `<768px` 下质量门矩阵已转为纵向 details 列表
- [ ] 断网打开 `index.html`，页面完整可读（图表降级为表格）
- [ ] 禁用 JS 打开，页面完整可读

**组件状态**
- [ ] 数据表有 Loading（骨架）/ Empty（引导文案）/ Error（原因+命令）/ Populated / Edge（超长名称截断+title）五态
- [ ] 图表有 Loading / Empty / Error（降级表格）/ Populated 四态

---

## 附录 A：Lucide 图标子集清单（与架构师锁定）

图标库：**Lucide**（ISC 许可），内联 SVG 雪碧图分发，零网络请求。尺寸只允许 16 / 20 / 24px。

| 用途 | 图标名 |
|---|---|
| 状态四态 | `check-circle-2` `alert-triangle` `x-octagon` `circle-dashed` |
| 数据与管道 | `database` `layers` `activity` `filter` `shield-check` `git-commit-horizontal` |
| 时间 / 进程 | `clock` `refresh-cw` `loader` |
| 图表 | `candlestick-chart` `line-chart` `table-2` |
| 方向（备用） | `trending-up` `trending-down` `minus` |
| 交互 | `chevron-down` `chevron-right` `external-link` `info` `download` |
| 主题 | `sun` `moon` |
| 兜底 | `circle-slash` |

```css
.ico   { width: 16px; height: 16px; stroke-width: 2; flex: none; }
.ico--md { width: 20px; height: 20px; }
.ico--lg { width: 24px; height: 24px; }
```

所有图标使用 `stroke="currentColor"`，颜色由父元素的 `color` 决定，天然跟随 Design Token 与主题切换。

## 附录 B：本文档的知识库与调研来源

**专家包知识库**（内容已内嵌于设计角色指令，磁盘上未物化为独立文件，此处标注实际引用的章节）：
- `references/design-systems/token-standard.md` —— 四层 Token 架构（A1-identity / A1-structure / A2 / B-slot / C-extension）、DESIGN.md 九节模板、色彩精规（中性 70-90% / 强调 5-10% / 语义 0-5%）、排版精规（ALL CAPS ≥0.06em、三级字重）、动效精规（150ms 收敛值）、布局词汇表（12/8/4 栏、节区节奏）
- `references/industries/enterprise.md` + `references/industries/saas-b2b.md` —— 本项目属"数据工具 / 企业级监控"，参照企业管理与 B2B 工具的密度规范与状态表达。未参照 `ecommerce.md` / `content-platform.md` / `ai-native.md`。
- 角色指令内嵌的《AI 模板反模式七大罪》《绝对禁令 12 条》《10 级优先级规则》《认知负荷评估》

**联网调研来源**：
1. TradingView 深色主题实测色值 —— `#131722` 背景、`#2A2E39` 网格、`#B2B5BE` 坐标文字、"永不用纯黑"结论（eathealthy365.com、visualfoodie.com）
2. 数据密集看板八条经验 —— "深色为默认、浅色为覆盖"、"一个语义角色两套色阶"（pixel-show.com/blog/designing-data-dense-dashboards）
3. 中国金融 UI 规范 —— "红色代表上涨、绿色代表下跌，此行业惯例必须严格遵守"；数字右对齐；等宽字体展示价格（momoui.cn、momoux.com，服务招商证券 / 中信证券 / 国信证券）
4. 量化终端表格密度实测 —— 行高 18-22px、列间距 4-6px、涨跌 `#FF4444` / `#00AA44` / 平盘 `#888888`（shinnytech.com）
5. 数据质量看板范式 —— 六维度质量矩阵、健康分 = 通过监控数 / 总数、新鲜度用"最后成功更新时间"、评分趋势（docs.getmontecarlo.com/docs/data-quality）
6. 数据质量运维控制台设计 —— "状态一览应像运维控制台：状态清晰、点击最少、标签跨面板一致"、失败详情需含"期望值 vs 实际值"（koder.ai/blog/build-web-app-data-quality-checks-alerts）
7. 金融深色配色工程结论 —— 交易界面需 ≥5 个小尺寸下仍可区分的状态色；深色下图表色需单独定义 6-8 色互斥序列（colorarchive.org/guides/fintech-dark-mode-colors）
