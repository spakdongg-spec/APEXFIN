# 「抽框架不抽 alpha」切割清单

| 项目 | 内容 |
|------|------|
| 文档 | ALPHA_BOUNDARY.md |
| 版本 | v1.0 |
| 撰写 | 高见远（首席架构师） |
| 日期 | 2026-08-02 |
| 源系统 | APEXDATA（`scripts/` 26 个 py + `scripts/pipeline/` 187 个 py，共 213 个，实测于 2026-08-02） |
| 目标 | APEXFIN 约 60 个 py 文件 |
| 对应验收 | PRD AC-8（隐私净化，一票否决项） |

---

## 一、切割判定规则

每个文件依次过三问，任一问命中即落入对应类别，不再往下走：

**Q1 泄露问：** 它是否包含或引用密钥、券商连接、持仓、个人账户、付费源凭据？
- 是 -> **DELETE**（一票否决，无例外）

**Q2 alpha 问：** 它是否编码了「怎么赚钱」的判断——具体阈值、权重、因子公式、择时规则、经过实盘调优的参数？
- 是，且该判断可被通用抽象替代 -> **SKELETONIZE**（保留接口，玩具实现）
- 是，且它本身就是 alpha 主体（无通用骨架可留） -> **DELETE**

**Q3 骨架问：** 它是否表达了「数据工程该怎么组织」的通用工程判断，且脱离本人的标的与策略后仍然成立？
- 是 -> **KEEP**（迁移 + 重构）
- 否 -> **DELETE**（多为一次性脚本、临时修复、个人产物）

规则的本质：**保留「纪律」，丢弃「判断」。** 质量门怎么设计是纪律，阈值定多少是判断（外置到 YAML）；管道怎么排序是纪律，排哪些步骤是判断（外置到 manifest）。

---

## 二、DELETE：不进仓库

### D1 密钥与凭据（一票否决）

| 位置 | 内容 | 处置 |
|------|------|------|
| `scripts/pipeline/fetch_fred.py:22` | `FRED_API_KEY = "<32位十六进制明文，已脱敏>"` | 不迁移；APEXFIN 只读 env `APEXFIN_FRED_API_KEY` |
| `scripts/pipeline/fetch_fred_regional.py:23` | 同一个 key 的第二处硬编码 | 同上 |

> 本表刻意不记录密钥实际值。审计文档本身若抄录明文密钥，等于把泄露从私有仓库搬到公开仓库——这是同一个错误换了个地方犯。定位靠文件与行号即可。

实测确认：全库正则扫描 `(API_KEY\|api_key\|token\|secret\|password)\s*=\s*["'][A-Za-z0-9_-]{16,}["']` 命中且仅命中以上 2 处。

**独立于本项目的行动项：该 key 明文存在于用户私有仓库中，必须在 FRED 控制台吊销并重新签发。** 「新仓库没带过去」不等于「已解决」。

### D2 券商 / 私有连接（Futu / IB / vn.py）

`scripts/_futu_test.py`、`scripts/futu_positions_direct.py`、`scripts/pull_futu_positions.py`、
`scripts/pipeline/fetch_futu_positions.py`、`fetch_etf_futu.py`、`fetch_gld_futu.py`、`fetch_hk_futu.py`、`vnpy_bridge.py`

代码内引用也要一并剥离，不能只删文件：
- `scripts/pipeline/common.py` 中的 `FUTU_HOST` / `FUTU_PORT` 配置项
- `scripts/pipeline/fetch_yahoo.py` 中的 `FUTU_COVERED` 集合（该集合表达「这些标的以 Futu 为主源」，属于私有基础设施拓扑信息）
- `requirements.txt` 中的 `futu-api>=10.0.0`

### D3 反爬 / 规避特征（合规红线）

`scripts/pipeline/fetch_yahoo.py` 中的 **User-Agent 轮换池** 与 **双 host 回退** 逻辑。

理由：这属于规避访问控制的特征。放进以「数据诚实性」为卖点的公开仓库，既放大法律风险，也构成价值观自相矛盾。APEXFIN 的 Yahoo 采集器改为单一公开端点 + 固定标识性 UA + 默认 1.5 秒请求间隔 + 遇 429 立即停止本源。

> **已裁决（2026-08-02，team-lead）**：本条从「建议」升格为**生效约束**，且适用于所有网络源而不止 Yahoo。依据 `docs/decisions/ADR-009-network-source-access-policy.md`，架构侧表述见 `docs/ARCHITECTURE.md` 8.2，含 C1-C6 六条可测断言（AST 门禁禁止 `sources/` 内出现 UA 池、单测断言 429 不重试等）。Stooq 记为文档化备选，MVP 不实现。

### D4 MVP 不内置的数据源（25 个 fetch_*，走插件接口而非内置）

`fetch_akshare_china.py`、`fetch_cftc_cot.py`、`refresh_tff_cot.py`、`fetch_cme_fedwatch.py`、`fetch_eia.py`、`fetch_cboe.py`、`fetch_cboe_backfill.py`、`fetch_cboe_daily.py`、`fetch_aaii.py`、`fetch_bdi.py`、`fetch_ism_pmi.py`、`fetch_worldbank.py`、`fetch_us_treasury.py`、`fetch_ted_spread.py`、`fetch_spx_rv.py`、`fetch_vix_curve.py`、`fetch_vix_term.py`、`fetch_options_daily.py`、`fetch_event_calendar.py`、`fetch_textual_factors.py`、`fetch_theme_factors.py`、`fetch_fred_regional.py`、`options_collector.py`、`options_historical.py`、`options_storage.py`

依据 PRD 六「进 Backlog」：内置两源（Yahoo + FRED）足以证明 `BaseCollector` 接口成立，其余由使用者按需实现。其中 akshare 另有依赖体量问题（`akshare>=1.12` 拉入大量传递依赖），与依赖预算冲突。

### D5 真实 alpha 主体（无通用骨架可留）

按主题归组，共约 90 个文件：

| 主题 | 代表文件 |
|------|---------|
| 因子工程 | `compute_alpha158.py`、`factor_ic_screening.py`、`factor_crowding_detector.py`、`pca_signal_orthogonalizer.py`、`temporal_feature_engineer.py`、`analyze_factor_exposure.py`、`analyze_rolling_windows.py`、`bad_times_tolerance.py` |
| COT 体系 | `cot_bayesian_updater.py`、`cot_brier_fusion.py`、`cot_evolution_driver.py`、`cot_fast_correction.py`、`cot_position_integrator.py`、`cot_reverse_flow.py`、`cot_stop_loss.py`、`cot_two_phase_backtest.py`、`generate_cot_section.py`、`compute_alsi_cot_integration.py` |
| 期权策略 | `options_signals.py`、`options_metrics.py`、`options_reliability.py`、`compute_options_microstructure.py`、`compute_options_risk.py`、`map_mcmillan_strategies.py`、`generate_options_dashboard.py` |
| 价格行为 | `compute_wyckoff_phase.py`、`compute_pa_deep_analysis.py`、`compute_price_action_diag.py`、`analyze_price_action.py`、`generate_pa_deep_analysis.py`、`multi_timeframe.py`、`compute_reference_points.py` |
| 宏观建模 | `macro_compression.py`、`macro_environment_consistency.py`、`macro_options_linkage.py`、`macro_scenario_weighting.py`、`macro_shock_simulator.py`、`build_macro_book.py`、`reconcile_macro_book_subjective.py`、`update_bayesian_scenario.py` |
| 叙事体系 | `narrative_continuity_tracker.py`、`narrative_detector_daily/weekly/monthly.py`、`narrative_llm_bridge.py`、`narrative_registry.py`、`narrative_schema.py`、`narrative_utils.py`、`author_narratives_agent.py` |
| 跨市场 | `cross_asset_matrix.py`、`cross_confirm_arbiter.py`、`cross_market_signals.py`、`compute_cross_analysis.py`、`market_liquidity.py`、`flow_heatmap.py`、`market_reaction_validator.py`、`detect_behavioral_signals.py` |
| 组合与择时 | `run_v7_ang.py`、`update_v7_ang_daily.py`、`makemoney_pipeline.py`、`regime_arbiter.py`、`thesis_engine.py`、`strategy_synthesis.py`、`multi_horizon_assertion_generator.py`、`assertion_performance_tracker.py`、`analyze_event_patterns.py`、`update_event_patterns.py`、`perspective_adjuster.py` |
| 个人风控闸门 | `ai_checkpoint.py`、`ai_consumer_gate.py`、`ai_rr_gate.py`、`discipline_guard.py`、`risk_matrix_generator.py`、`core_allocator.py` |

判定说明：这一组的共同特征是「删掉参数就什么都不剩」。例如 `compute_alpha158.py` 的价值全在 158 个因子的具体定义上，抽象成 `BaseFactor` 之后剩下的骨架毫无信息量——那不是骨架，那是空壳。给空壳留位置是伪装成架构的噪音。

### D6 一次性脚本 / 个人产物 / 临时修复（约 25 个）

`_tmp_cleanup_probe.py`、`_tmp_extract_ctx.py`、`_tmp_f1_mock.py`、`_agent_news_backfill_20260731.py`、`_build_curated_0728.py`、`_gen_outlook_2026_07_11.py`、`build_ai_result_2026_07_30.py`、`write_debate_prose_2026_07_11.py`、`manual_analysis_insert.py`、`fix_double_encoding.py`、`fix_hk_options_snapshot.py`、`fix_today_data.py`、`copy_yesterday_data.py`、`export_to_alphamaster.py`、`alphamaster_local.py`、`push_adapter.py`、`backup.py`、`probe_debate_data.py`、`audit_orphan_modules.py`、`_beijing_time.py`、`build_institutional_sample.py`、`build_briefing_html.py`、`build_playbook_html.py`、`build_recap_html.py`、`build_recap_outlook.py`

### D7 数据与产物

所有 `*.db`、`data/`、生成的 HTML 报告、`.env`、日志、快照目录。`.gitignore` 覆盖，且 **APEXFIN 全新 `git init`**，不迁移 APEXDATA 的 git 历史——避免历史提交中残留密钥或私有数据。

---

## 三、SKELETONIZE：留接口，玩具实现

| APEXDATA 来源 | APEXFIN 落点 | 保留什么 | 丢弃什么 |
|--------------|-------------|---------|---------|
| `decision_core.py`、`decision_bridge.py`、`decision_bridge_canary.py` | `decision/base.py` | `BaseStrategy` / `Signal` / `Decision` 抽象；「策略只吃只读 `MarketView`」的边界设计 | 全部具体判定逻辑、阈值、标的耦合 |
| `run_dual_momentum.py`、`save_dual_momentum_note.py` | `decision/analysts/technical.py` | 「分析师角色」这个位置 | 原实现整体不搬；technical 角色用动量 + 趋势融合的参考计算 |
| `signal_arbiter.py`、`promote_signals.py`、`evidence_fusion.py`、`evidence_fusion_canary.py`、`signal_registry.py` | `decision/aggregator.py` + `core/registry.py` | 「多信号 -> 单决策」的聚合位置；注册表模式 | 所有权重、优先级、仲裁规则。替换为等权聚合，**刻意不提供任何可调参数**（有参数就有 alpha 嫌疑） |
| `multi_agent_debate_framework.py`、`multi_agent_debate_v2.py`、`run_multi_agent_debate.py`、`debate_agent_synthesis.py`、`author_debate_agent.py`、`weekly_debate.py`、`synthesize_debate_rule_fallback.py` | `analysis/`（P1） | 角色编排骨架（bull / bear / risk 三段）、结构化输出 schema、「每条论断必须引用具体数据」的铁律 | 真实 LLM 调用、provider key、辩论中的个人观点与偏好；替换为确定性 `MockLLMClient` |
| `scripts/pipeline/analyst_roles/*.md`（8 个角色卡） | `analysis/prompts/*.md` | 角色定义、证据引用铁律、「数据缺失标未覆盖」约束 | 涉及个人标的偏好、仓位习惯、私有指标名的句子，逐句人工复核 |
| `llm_client.py`、`ai_analyst_async.py`、`ai_analyst_verify.py`、`validate_ai_output.py` | `analysis/client.py` + `analysis/schema.py` | `LLMClient` 协议、输出结构校验 | 具体 provider 实现、重试策略中的私有端点、key 管理 |
| `accountability_ledger.py` | `accounting/ledger.py`（P1） | 「每个结论落库为带时间戳与理由的记录」骨架 | 领域特定字段、个人评分口径 |
| `falsification_monitor.py` | `accounting/settle.py`（P1） | 「到期用后续行情判定命中/落空」的通用流程 | `macro_hypotheses` 的宏观假设领域模型、权重衰减系数（这是调过的参数） |
| `backtest_engine.py`、`signal_backtest.py`、`calibration.py`、`brier_score_calibrator.py`、`cognitive_evolution_loop.py`、`ai_analyst_evolve.py` | 不进 MVP | — | PRD 十三明确 Out of Scope（回测赛道饱和，README 直接推荐 vectorbt / nautilus_trader） |

骨架化的验收标准：**把玩具实现整个删掉，框架仍能跑通（决策区显示 no_call）。** 如果删掉玩具实现框架就崩，说明抽象没做干净，骨架里还粘着 alpha。

---

## 四、KEEP：迁移 + 重构（项目的全部价值密度）

| APEXDATA 来源 | APEXFIN 落点 | 重构要点 |
|--------------|-------------|---------|
| `common.py`（408 行，混合了连接/日志/写入/运行记录） | 拆为 `storage/engine.py`、`storage/bronze_repo.py`、`storage/run_repo.py`、`core/logging.py` | 违反单一职责与 300 行规则，必须拆；剥离 `FUTU_*` 配置；`insert_raw_bronze` 的去重 + 修订链 + `UpsertStats` 返回值是核心资产，逐行保真 |
| `silver_layer.py`（436 行） | `processing/extractors.py` + `silver_builder.py` + `quality_score.py` | `EXTRACTORS` dict 改为装饰器注册表；`compute_quality_score` 的来源可靠性 × 时效性衰减保留，系数外置到 `sources.yaml`；派生计算（如 SOFR-EFFR 利差）属领域内容，不迁移 |
| `check_quality.py`（527 行，6 个检查函数） | `quality/check_*.py` 六个文件 + `gate.py` | 一文件一检查，满足 300 行规则；`SOURCE_EXPECTATIONS` 常量外置为 `config/expectations.yaml`；**新增 tier 感知裁决**（原实现只报告不阻断，APEXFIN 必须真中断） |
| `check_data_freshness.py`、`audit_freshness.py`、`text_factor_freshness.py` | `quality/check_freshness.py` | 三处新鲜度逻辑合一；判定基准从自然日改为 `TradingCalendar` 交易日 |
| `consistency_checks.py` | `quality/check_consistency.py` | bronze <-> silver 行数与值一致性 |
| `validate_manifest.py`（108 行，3 条断言）、`verify_pipeline_manifest.py` | `pipeline/manifest.py` | 三条断言泛化为「注册表 <-> manifest 双向一致 + keep_daily 依赖合法性 + 无环」四条；新增 JSON Schema 结构校验 |
| `runner.py`、`runner_post.py`（476 行，`POST_STEPS` 手工有序列表） | `pipeline/runner.py` + `planner.py` + `steps.py` | **最重要的一处重构**：手工顺序改为 `depends_on` 声明 + 拓扑排序 + 环检测。`runner_post.py` 的注释里记录了一次真实的依赖倒置 bug，根因就是顺序靠人肉维护，结构上根治 |
| `pipeline_manifest.yaml`（98 步，四档 tier） | `config/pipeline_manifest.yaml`（约 10 步） | 四档 tier 术语原样保留（差异化核心资产）；`why` 字段升级为强制必填非空 |
| `trading_date.py` | `core/calendar.py` | 泛化为 `TradingCalendar` 协议 + `YamlTradingCalendar`；假日表外置 |
| `db_guard.py` | `storage/engine.py` | 并入 PRAGMA 与 busy_timeout 保护 |
| `dashboard_renderer.py`、`dashboard_data_loader.py`、`dashboard_transformer.py` | `reporting/renderer.py` + `datapack.py` | Jinja2 + `autoescape=True` 保留；强制「模板只读 DataPack，不做计算」；新增降级态模板 |
| `extract_daily_prices.py`、`extract_vix_data.py` | `processing/extractors.py` 中的示例实现 | 只保留结构最清晰的一个作为 extractor 范例 |
| `fetch_yahoo.py`（288 行） | `sources/yahoo.py` | 保留：增量窗口逻辑、429/5xx 退避、`--full` 回填开关。删除：UA 轮换、双 host 回退、`FUTU_COVERED` |
| `fetch_fred.py`（266 行） | `sources/fred.py` | 保留：按频率分组的节流（`FREQ_SKIP_DAYS`）、增量逻辑。删除：硬编码 key |
| `check_all.py`、`check_updates.py`、`monitor.py` | `cli/cmd_doctor.py` | 合并为一个自检命令 |
| `spine.py`、`daily_playbook.py`、`final_synthesis.py`、`verify_final_synthesis.py` | 不迁移 | 属于业务产物组装，与个人研究流程强绑定 |

---

## 五、切割前后规模对照

| 指标 | APEXDATA | APEXFIN 目标 | 说明 |
|------|----------|-------------|------|
| Python 文件数 | 213 | 约 60 | 削减 72% |
| 数据源 | 27 个 `fetch_*` | 3 个（fixture / yahoo / fred） | 其余走插件接口 |
| 管道步骤 | 98 步（manifest 实测） | 约 10 步 | 每步 `why` 强制必填 |
| 数据库 | 2 个库、30+ 张表 | 1 个库、9 张表 | 见 `docs/DATA_CONTRACT.md` 八 |
| 顶层运行时依赖 | 12（含 futu-api / akshare / pandas / polars / numpy） | 8 | 见 `docs/ARCHITECTURE.md` 4.2 |
| 单文件最大行数 | 527（`check_quality.py`） | ≤ 300（CI 强制） | |

---

## 六、执行期人工复核清单（不可省略）

自动化只能拦住模式化的泄露，以下必须逐项人眼过：

1. `analysis/prompts/` 8 个角色卡逐句复核，删除涉及个人标的偏好、仓位习惯、私有指标命名的表述。
2. 迁移后的每个质量检查，确认代码内**零魔数**——所有阈值必须来自 `expectations.yaml`。
3. `sources.yaml` 的符号清单复核：不得暴露用户实际关注的完整标的池（这本身是弱 alpha 信息）。MVP 只放通用宽基：`SPY`、`QQQ`、`^VIX` 与 FRED 的 `DGS10`、`DFF`。
4. fixture 样本数据复核：确认只含公开市场行情片段，不含任何派生指标或私有计算结果。
5. 开源前用 `gitleaks detect` 扫描工作区与全量 git 历史，输出报告留档。
6. 全文搜索 `futu`、`ib_insync`、`vnpy`、`position`、`account`、`alphamaster`（不区分大小写），确认零命中。
7. README 与代码中确认零 emoji（CI 已有码点扫描，但首次发布人工再确认一遍）。
