# APEXFIN 抽象接口契约

| 项目 | 内容 |
|------|------|
| 文档 | INTERFACES.md |
| 版本 | v1.0 |
| 撰写 | 高见远（首席架构师） |
| 日期 | 2026-08-02 |
| 约束 | 标识符、docstring、异常信息一律英文（PRD 十·国际化） |

本文给出实现方必须遵守的签名。签名即契约：改签名等于改契约，必须先改本文档并同步 team-lead。

---

## 一、核心数据模型（`core/models.py`）

全部为 pydantic v2 模型，`model_config = ConfigDict(frozen=True, extra="forbid")`。

```python
class RawRecord(BaseModel):
    """One untouched unit fetched from an upstream source."""

    source_name: str  # e.g. "yahoo", "fred", "fixture_equity"
    domain: str  # e.g. "equity", "macro", "volatility"
    symbol: str  # e.g. "SPY", "DGS10"
    event_time: datetime  # business time, tz-aware UTC. NOT fetch time.
    payload: dict[str, Any]  # raw upstream body, serialized as-is
    source_url: str | None = None


class BronzeRecord(BaseModel):
    id: int
    source_name: str
    domain: str
    symbol: str
    event_time: datetime
    event_date: date
    payload: dict[str, Any]
    payload_hash: str  # sha256 of canonical json
    revision: int  # 0 = first seen, N = Nth upstream revision
    ingested_at: datetime


class SilverPoint(BaseModel):
    source_name: str
    domain: str
    symbol: str
    event_time: datetime
    event_date: date
    value: float  # the one number this row means
    value_secondary: float | None = None  # e.g. volume beside close
    unit: str | None = None  # "USD", "percent", "index"
    quality_score: float  # 0.0 - 1.0
    is_filled: bool = False  # True if forward-filled, never silently
    payload_json: dict[str, Any] | None = None


class FetchWindow(BaseModel):
    """Closed interval the collector is asked to cover."""

    start: date
    end: date
    full_refresh: bool = False


class SourceCapabilities(BaseModel):
    source_name: str
    domain: str
    symbols: tuple[str, ...]
    frequency: Frequency  # DAILY | WEEKLY | MONTHLY
    requires_credentials: bool
    supports_full_refresh: bool
    min_request_interval_s: float = 0.0  # politeness floor, honored by base class
```

`Signal` / `Decision` / `QualityFinding` / `StepResult` / `GateVerdict` 定义见对应章节。

---

## 二、采集：`BaseCollector`（`sources/base.py`）

抽象基类而非纯 Protocol——因为退避、限速、空结果防护这些**不该让第三方重写**的逻辑要放在基类里（对应 PRD AC-4：只读 docstring 就能扩展）。

```python
class BaseCollector(ABC):
    """Fetch raw records from one upstream source.

    Subclasses implement `_fetch_raw` only. The base class owns:
      - politeness delay (`capabilities().min_request_interval_s`)
      - retry with exponential backoff + jitter on transient errors
      - empty-result guard: an empty iterable is treated as FAILURE,
        never as a successful no-op (this is the primary defense against
        the silent-failure class of bugs)
      - per-source isolation: exceptions are wrapped into CollectorError
        and reported upward; one failing source must not abort the run
    """

    @abstractmethod
    def capabilities(self) -> SourceCapabilities: ...

    @abstractmethod
    def _fetch_raw(self, window: FetchWindow) -> Iterable[RawRecord]:
        """Fetch and yield RawRecord. Raise on transport/parse failure.

        MUST NOT swallow errors and return an empty iterable — the base
        class cannot distinguish 'genuinely no data' from 'silently broken'
        and will therefore treat empty as failure.
        """

    # provided by base, subclasses do not override:
    def fetch(self, window: FetchWindow) -> CollectResult: ...
```

```python
class CollectResult(BaseModel):
    source_name: str
    records: tuple[RawRecord, ...]
    ok: bool
    error: str | None = None
    requests_made: int
    duration_s: float
```

注册：

```python
@register_source("yahoo")
class YahooCollector(BaseCollector): ...
```

第三方通过 entry point 注册：

```toml
[project.entry-points."apexfin.sources"]
my_broker = "my_pkg.collectors:MyBrokerCollector"
```

---

## 三、归一：`Extractor`（`core/contracts.py`）

```python
class Extractor(Protocol):
    source_name: str

    def extract(self, record: BronzeRecord) -> list[SilverPoint]:
        """Turn one bronze payload into zero or more silver points.

        Returning an empty list is legal here (a payload may carry no
        usable numeric value) but MUST be logged with a reason.
        """
```

注册：`@register_extractor("yahoo")`。派发键为 `source_name`，未注册的源在 process 阶段报 `ExtractorNotFound`，不静默跳过。

---

## 四、质量：`QualityCheck`（`quality/base.py`）

```python
class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class QualityFinding(BaseModel):
    check_id: str  # "freshness", "continuity", ...
    severity: Severity
    source_name: str
    symbol: str | None
    message: str  # English, must state observed vs expected
    observed: str | None = None
    expected: str | None = None
    tier: Tier  # inherited from the source's manifest tier


class QualityContext(BaseModel):
    run_id: str
    clock: Clock
    calendar: TradingCalendar
    expectations: ExpectationTable
    silver: SilverReadPort  # read-only port, no write access
    bronze: BronzeReadPort


class QualityCheck(ABC):
    check_id: ClassVar[str]
    default_severity: ClassVar[Severity]

    @abstractmethod
    def run(self, ctx: QualityContext) -> list[QualityFinding]:
        """Return findings. An empty list means the check passed.

        A check MUST NOT raise for data problems — data problems are
        findings. Raising is reserved for check-internal bugs.
        """
```

内置六个（每个一个文件）：`freshness`、`completeness`、`duplicates`、`consistency`、`continuity`、`range`。

闸门裁决（`quality/gate.py`）：

```python
class GateVerdict(StrEnum):
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


def decide(findings: Sequence[QualityFinding]) -> GateDecision:
    """Tier-aware verdict.

    BLOCKED  if any finding is BLOCKING and tier == risk_essential
    DEGRADED if any finding is BLOCKING/WARNING on other tiers
    PASS     otherwise
    """
```

`GateDecision` 携带 `verdict`、`blocking_findings`、`degraded_sources`、`human_summary`（用于 CLI stderr 与看板顶部区块）。

---

## 五、时间与日历（`core/clock.py`、`core/calendar.py`）

```python
class Clock(Protocol):
    def now(self) -> datetime: ...  # tz-aware UTC
    def today(self) -> date: ...


class SystemClock: ...


class FrozenClock:  # used by tests and by demo fixture packs
    def __init__(self, at: datetime) -> None: ...


class TradingCalendar(Protocol):
    name: str

    def is_trading_day(self, d: date) -> bool: ...
    def previous_trading_day(self, d: date) -> date: ...
    def trading_days_between(self, start: date, end: date) -> int:
        """Count trading days in (start, end]. Zero if end <= start."""
```

内置 `YamlTradingCalendar(name="NYSE")`：周末 + `config/calendars/nyse.yaml` 假日表。诚实边界：不处理半日休市、不处理临时休市，超出范围的年份直接 `raise CalendarRangeError`（而不是猜）。

**全项目禁止直接调用 `datetime.now()` / `date.today()`**，一律经 `Clock`。这是故障注入能干净实现的前提。

---

## 六、编排：`PipelineStep`（`core/contracts.py`）

```python
class StepStatus(StrEnum):
    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepResult(BaseModel):
    step_name: str
    status: StepStatus
    duration_s: float
    message: str | None = None
    metrics: dict[str, float] = {}


class RunContext(BaseModel):
    run_id: str
    clock: Clock
    calendar: TradingCalendar
    settings: Settings
    conn: sqlite3.Connection  # one shared connection, built once in the composition root (O-11)
    gate_state: GateVerdict  # steps may short-circuit on BLOCKED


class PipelineStep(Protocol):
    name: str
    tier: Tier
    depends_on: tuple[str, ...]
    critical: bool
    timeout_s: int

    def run(self, ctx: RunContext) -> StepResult: ...
```

注册：

```python
@step(name="collect", tier=Tier.RISK_ESSENTIAL, depends_on=(), critical=True, timeout_s=120)
def collect_step(ctx: RunContext) -> StepResult: ...
```

Runner 保证：每个 step 在独立 SAVEPOINT 中执行（继承 APEXDATA 的 `run_pipeline_step` 隔离语义）；失败时回滚该 step 的写入但保留 `step_runs` 记录；`critical=True` 的 step 失败终止整个 run。

**O-11 约束（SAVEPOINT 的前提）**：`ctx.conn` 是**全 run 唯一的共享连接**，由组合根（`cli/context.build_context`）建一次后注入 `RunContext`，五个 repository 与 runner 全部复用同一个连接对象。SQLite 的 SAVEPOINT 是连接级原语，跨连接不生效——若有人把连接改为按调用新开（`connect()` 每次新开），本条保证即静默失效（回滚成功返回、写入原样留库），属 fail-silent 禁区，不得回归。`ConnectionFactory` 协议保留但职责收紧为「只在组合根调用一次」。

---

## 七、决策（`decision/base.py`）

```python
class Signal(BaseModel):
    strategy: str
    symbol: str
    direction: Literal["long", "short", "flat"]
    strength: float  # -1.0 .. 1.0
    as_of: date
    rationale: str  # must cite the concrete inputs used
    inputs: dict[str, float]  # the numbers the signal was computed from


class Decision(BaseModel):
    run_id: str
    as_of: date
    symbol: str
    stance: Literal["long", "short", "flat", "no_call"]
    confidence: float  # 0.0 .. 1.0
    rationale: str
    contributing_signals: tuple[str, ...]
    degraded: bool  # True if produced under DEGRADED gate


class MarketView(Protocol):
    """Read-only projection handed to strategies.

    Strategies never receive a database connection. This keeps them
    replaceable (PRD AC-5), testable, and unable to write anywhere.
    """

    as_of: date

    def series(self, symbol: str, lookback: int) -> tuple[SilverPoint, ...]: ...
    def symbols(self) -> tuple[str, ...]: ...
    def is_healthy(self, symbol: str) -> bool: ...


class BaseStrategy(ABC):
    name: ClassVar[str]

    @abstractmethod
    def generate(self, view: MarketView) -> list[Signal]:
        """Produce signals. MUST return [] rather than guessing when
        `view.is_healthy(symbol)` is False."""


class SignalAggregator(Protocol):
    def aggregate(self, signals: Sequence[Signal], as_of: date) -> list[Decision]: ...
```

内置 `ToyMomentum`（文件头必须写明：demonstration only, not investment advice, deliberately naive）与 `EqualWeightAggregator`（等权，无任何可调参数——有参数就有 alpha 嫌疑）。

---

## 八、AI 分析契约（`analysis/`，P1）

```python
class RoleCard(BaseModel):
    role_id: str  # "bull", "bear", "risk", ...
    title: str
    prompt_template: str
    required_inputs: tuple[str, ...]
    output_schema_ref: str


class AnalysisOutput(BaseModel):
    role_id: str
    stance: Literal["bullish", "bearish", "neutral", "insufficient_data"]
    claims: tuple[Claim, ...]  # each Claim carries the data it cites
    caveats: tuple[str, ...]


class Claim(BaseModel):
    statement: str
    cited_symbol: str
    cited_value: float
    cited_as_of: date  # forces every claim to name its evidence


class LLMClient(Protocol):
    def complete(self, prompt: str, *, role_id: str) -> LLMResponse: ...
```

`MockLLMClient` 为默认实现：对相同输入返回相同输出（哈希驱动的模板填充），使 demo 完全离线且可复现。数据缺失时必须输出 `insufficient_data` 而不是编造——这是从 APEXDATA 角色卡铁律继承的约束，写进 schema 层面强制。

---

## 九、渲染（`reporting/`）

```python
class DataPack(BaseModel):
    """The only object templates may read. Templates do no computation."""

    generated_at: datetime
    run_id: str
    gate: GateSummary  # verdict + per-source status + human text
    health_rows: tuple[HealthRow, ...]
    decisions: tuple[DecisionRow, ...]
    charts: tuple[ChartSpec, ...]  # pre-serialized ECharts option dicts
    ledger: tuple[LedgerRow, ...]
    notices: tuple[Notice, ...]  # empty-state / degraded copy, concrete
    run_footer: RunFooter  # pipeline liveness, wall-clock, ONE per run


class RunFooter(BaseModel):
    """Wall-clock facts about the run. Never rendered next to freshness."""

    finished_at: datetime  # pipeline_runs.finished_at
    finished_label: str  # "2026-08-02 14:03（+08:00）"
    duration_seconds: float  # machine-readable, --json envelope only
    duration_label: str  # human-readable, the ONLY field templates read


class Renderer(Protocol):
    def render(self, pack: DataPack, out_path: Path) -> Path: ...
```

### 9.1 `HealthRow` / `FreshnessBar`

之前只写了「三重编码字段」一句，字段表未定。本轮依据 OPEN-DECISIONS O-07 补齐为完整契约。

```python
class FreshnessBar(BaseModel):
    """Pre-computed SLA bar. Absent when lag is unknown."""

    bar_value: int  # aria-valuenow, already clamped to bar_max
    bar_max: int  # aria-valuemax, always >= 1
    overdue: bool  # lag exceeded the threshold
    label: str  # "lag 3 交易日 / 阈值 1 交易日"


class HealthRow(BaseModel):
    source_name: str
    symbol: str
    state: Literal["healthy", "degraded", "blocked", "unknown"]

    # Triple encoding: text + shape + colour. Never colour alone.
    label_text: str  # "健康" / "降级" / "阻断" / "未知"
    icon_id: str  # sprite symbol id, from the state map
    tone: Literal["ok", "warn", "danger", "muted"]

    # Freshness, trading-day semantics only. No hours anywhere.
    lag_trading_days: int | None
    max_lag_trading_days: int
    freshness: FreshnessBar | None  # None when lag_trading_days is None

    last_event_date: date | None  # business date of the newest data point
    last_event_label: str | None  # pre-formatted, e.g. "07-31（周五）"
    note: str | None
```

约束：

1. **无小时字段**。`lag_hours` / `sla_hours` / `sla_ratio` 不是本契约的一部分，任何层都不引入。理由见 ARCHITECTURE 5.3.1。
2. **`freshness` 全有或全无**。`lag_trading_days is None`（`state == "unknown"`，从未成功采集）时 `freshness` 为 `None`，模板不渲染进度条，改渲染 `circle-dashed` 加空状态文案，具体原因取自 `note`。用嵌套模型而非平铺字段，就是为了让「没有滞后数据时进度条整块不存在」在类型上成立，而不是靠模板去判断三个平铺字段是否同时为空。
3. **`bar_value` 已夹取**，模板直接填进 `aria-valuenow`，不得自行 `min()`。超期的真实幅度在 `label` 里。
4. **`tone` 与 `state` 一一对应**，映射在 `datapack.py` 集中声明；`icon_id` 同理走状态图标表。模板不得自行判断状态到图标或颜色的对应（ARCHITECTURE 9.1）。
5. **`overdue` 不得反推 `state`**。`support` 档超期是 `degraded`，`risk_essential` 档超期才是 `blocked`，状态色只认 `state`。
6. **`last_event_date` 是业务日期，健康行内不得派生相对时间串**。此前本条允许由它派生「2 小时前」，已撤回——日粒度值派生不出小时，实现者只能转而取写入时间，而写入时间与进度条的业务时间会朝危险方向背离（详见 ARCHITECTURE 5.3.1.1）。该位置显示 `last_event_label`（如 `"07-31（周五）"`），由 `datapack.py` 预格式化，周几必须带上——它是读者判断「跨了个周末」的关键信息。
7. **`HealthRow` 中没有任何写入时间字段**。`last_checked_at` 属于 `series_health` 表但不进 `HealthRow`：管道存活状态是关于本次运行的**一个**事实，不是每序列一份，它由 `DataPack.run_footer` 承载（来源 `pipeline_runs.finished_at`），全局渲染一处，措辞明确指向采集动作而非数据年龄。

`max_lag_trading_days` 由 `series_health` 表透传，是**质量检查执行时的阈值快照**，不是渲染时读 `expectations.yaml` 的现值——理由（历史可解释 + 渲染层不耦合治理层配置格式）见 DATA_CONTRACT 四。

### 9.2 `RunFooter.duration_label` 格式化规则（team-lead 2026-08-02 定，O-08 附带）

由 `datapack.py` 预格式化，**按顺序判断**：

| 条件 | 输出 |
|------|------|
| `duration_seconds < 60` | `"不到 1 分钟"` |
| `duration_seconds >= 60` | `f"约 {round(d / 60)} 分钟"` |

三条约束：

1. **全中文，禁英文缩写**（不出现 `m` / `s` / `min`）。页脚其余文案皆中文，混排不一致。
2. **必须顺序判断**。否则 `d = 59.6` 时 `round(59.6 / 60) == 1`，会输出「约 1 分钟」，与「不到 1 分钟」语义冲突。
3. **超 60 分钟不换算小时**，统一「约 N 分钟」（3700s → 「约 62 分钟」）。管道跑过一小时应触发告警，而非优化文案——为不该发生的状态做美化，等于替它遮丑。

**为什么是 `str` 而非 `str | None`**：`RunFooter` 仅在 run 完成、`finished_at` 确定时构造，duration 必然有值。留一个永不执行的 `None` 分支会诱导下游写判空死代码，并让后来者误以为此处真的可能为空。若实现中发现 duration 确有取不到的路径，属 `pipeline_runs` 生命周期存在未识别状态，须上报而非填 `0.0` 蒙混。

**粒度取舍**（设计师结论，team-lead 采纳）：秒级（72.5s vs 73s）是噪声，无区分价值；但「平时约 1 分钟、今天约 9 分钟」的量级跳跃能暴露上游变慢（FRED 限流 / Yahoo 超时），是廉价且有诊断价值的健康信号。故取分钟粒度，既消灭模板算术，又不丢该信号。

`duration_seconds` 保留不删：它进 `--json` 信封供机器消费；`duration_label` 只给模板。二者并存，非二选一。

---

## 十、存储端口（`storage/`）

Repository 暴露窄接口，领域层依赖端口而非具体类：

```python
class BronzeReadPort(Protocol):
    def latest_event_date(self, source_name: str, symbol: str) -> date | None: ...
    def count_between(self, source_name: str, symbol: str, start: date, end: date) -> int: ...


class BronzeWritePort(Protocol):
    def upsert(self, records: Sequence[RawRecord]) -> UpsertStats: ...

    # UpsertStats: inserted / duplicates / revisions — used to prove progress


class SilverReadPort(Protocol):
    def series(self, source_name: str, symbol: str, lookback: int) -> tuple[SilverPoint, ...]: ...
    def latest_event_date(self, source_name: str, symbol: str) -> date | None: ...
    def distinct_series(self) -> tuple[tuple[str, str], ...]: ...
```

`UpsertStats` 是防静默失效的关键返回值：collect 步骤结束时必须断言「有新增，或有明确的『上游确无新数据且在预期频率内』理由」，否则记为 finding。

---

## 十一、注册表与插件（`core/registry.py`）

```python
REGISTRY_GROUPS = ("apexfin.sources", "apexfin.checks", "apexfin.strategies")


def register_source(name: str) -> Callable[[type[BaseCollector]], type[BaseCollector]]: ...
def register_check(check_id: str) -> Callable[[type[QualityCheck]], type[QualityCheck]]: ...
def register_strategy(name: str) -> Callable[[type[BaseStrategy]], type[BaseStrategy]]: ...


def discover_plugins() -> PluginReport:
    """Load third-party plugins via importlib.metadata.entry_points(group=...).

    Failures are captured into PluginReport.failures, never swallowed:
    `apexfin plugins list` renders them as [FAIL] <name>: <reason>.
    """
```

名称冲突策略：内置优先，第三方同名注册被拒绝并记录冲突（而非静默覆盖），在 `plugins list` 中显示 `[SKIP] name: shadowed by builtin`。
