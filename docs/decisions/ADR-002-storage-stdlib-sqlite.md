# ADR-002: 数据层用标准库 sqlite3 + 薄 Repository，不用 ORM

## Status

Accepted (2026-08-02) — 高见远

## Background

APEXFIN 是单机、零外部服务、9 张表的参考实现（PRD 十三：PostgreSQL 与云数据库明确 Out of Scope）。核心读者行为是「clone 下来读三十分钟，抄走结构」（PRD 二·P1 画像）。数据层选型要同时满足：零外部服务、依赖预算、可读性、以及「治理层能被单独抄走」。

APEXDATA 的 `requirements.txt` 里有 `sqlalchemy>=2.0.0`，但实际 `common.py` 用的是裸 `sqlite3`——依赖声明了却没真正使用，这本身是个信号。

候选：标准库 `sqlite3`、SQLAlchemy 2.0.51 Core、SQLAlchemy ORM、DuckDB 1.5.5、Peewee。

## Decision

采用**标准库 `sqlite3` + 手写薄 Repository 层**。SQL 以字符串常量写在各 Repository 文件顶部，DDL 集中在 `storage/migrations/*.sql` 作为单一真源。

| 候选 | 依赖成本 | 可读性 | 判定 |
|------|---------|-------|------|
| stdlib sqlite3 | 0 | SQL 显式可见 | **选定** |
| SQLAlchemy Core | +1 顶层依赖，约 10 MB | 需先懂 SQLAlchemy 表达式语言 | 落选 |
| SQLAlchemy ORM | 同上 | 关系映射对 9 张表是净负担；懒加载会掩盖查询成本 | 落选 |
| DuckDB | +1 顶层依赖，约 40 MB | 分析能力强，但改变整个存储范式 | 落选：本项目的瓶颈不是分析性能 |
| Peewee | +1 | 轻量但生态小 | 落选 |

关键判断：**对参考实现而言，ORM 是负价值。** 读者来抄的是「bronze 怎么去重、修订链怎么留痕、质量检查怎么查」，这些的答案就是 SQL 本身。用 ORM 包一层，读者要先学 ORM 才能看懂业务逻辑，等于给核心资产加了一道门槛。9 张表也远未到 ORM 能省下可观样板代码的规模。

DuckDB 的落选值得单独说明：它在列式分析上确实更强，但本项目 fixture 数据总量 < 1 MB，真实使用场景也是日频数据，SQLite 的窗口函数（`LAG`、`ROW_NUMBER`，3.25+ 支持）足够覆盖连续性检查与收益率计算。为一个不存在的性能问题引入 40 MB 依赖，与依赖预算和 5 分钟指标直接冲突。

配套约束：
- 领域层依赖窄端口（`BronzeReadPort` / `SilverReadPort` 等 Protocol），不依赖具体 Repository 类——这保证质量层可被单独抄走。
- 连接期 PRAGMA：`foreign_keys=ON`、`journal_mode=WAL`、`synchronous=NORMAL`、`busy_timeout=5000`。锁等待 5 秒后 fail-loud，不无限挂起。
- 每个 pipeline step 在独立 SAVEPOINT 中执行（继承 APEXDATA `run_pipeline_step` 的隔离语义）。
- 迁移只前进不回滚，checksum 不符立即报错退出码 3。

## Consequences

正面：
- 零额外依赖，安装体积与冷启动都最优。
- SQL 显式可读，直接服务「被抄走」这个核心用户行为。
- 端口抽象让未来换库（若真有人要 PostgreSQL）只需新增一组 Repository 实现，领域层零改动。

负面：
- 手写 SQL 有拼写与注入风险。缓解：全部使用参数化查询，Ruff 的 `S608` 规则禁止 f-string 拼 SQL；Repository 有独立单测覆盖。
- 无自动迁移生成。缓解：9 张表且 MVP 阶段 schema 稳定，手写迁移成本低于引入 Alembic 的成本。
- 并发写入能力受 SQLite 限制。缓解：本项目是单进程 CLI，不存在并发写场景；WAL 已覆盖「渲染读」与「管道写」并存的情况。

## Related ADRs

ADR-008（不引入 pandas，与本决策共同构成「纯标准库处理数据」的一致取向）
