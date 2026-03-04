# Data模块 — 任务队列

> Orchestrator 监控此文件，发现"待开始"任务时启动 Worker 执行。
> 状态：待开始 → 进行中 → 已完成 / BLOCKED

---

## D1. PostgreSQL 建库建表
状态：待开始
优先级：P0
描述：创建数据库 etf_quant，建立全部10张核心表（etf_basic、etf_daily、strategies、strategy_categories、backtest_results、trading_signals、virtual_portfolios、research_reports、research_frameworks、users、user_subscriptions）。使用 SQLAlchemy 2.0 模型定义，支持 alembic 迁移。
验收：所有表可通过 SQLAlchemy 模型正常 CRUD。

## D2. ETF 基础信息拉取
状态：待开始
优先级：P0
依赖：D1
描述：通过 akshare 的 fund_etf_spot_em() 接口拉取全 A 股场内 ETF 基础信息（约900+只），写入 etf_basic 表。分类映射：宽基/行业/主题/商品/债券/货币/跨境。
验收：etf_basic 表记录数 ≥ 800，分类覆盖全部7类。

## D3. 历史日K线全量拉取
状态：待开始
优先级：P0
依赖：D2
描述：遍历 etf_basic 全部 ETF，通过 akshare 的 fund_etf_hist_em() 拉取历史日K线（前复权），写入 etf_daily 表。预估约180万条记录。需实现：批量写入、断点续传、限速控制（每次请求间隔0.3s）、进度日志。
验收：etf_daily 表记录数 ≥ 150万，无重复记录。

## D4. 数据清洗流程
状态：待开始
优先级：P0
依赖：D3
描述：实现数据清洗管道：停牌日标记（volume=0）、异常值检测（涨跌幅超15%告警）、复权价格校验（pre_close一致性）、去重校验（UNIQUE约束）。
验收：清洗后数据无重复，异常值已标记。

## D5. 每日增量更新
状态：待开始
优先级：P0
依赖：D4
描述：实现增量更新逻辑：查询每只 ETF 最后一条记录的日期，仅拉取之后的新数据。由 scheduler.py 在15:30触发（POST /api/v1/data/sync）。更新后校验：记录数 ≥ 已知活跃 ETF 的90%，否则告警。
验收：增量更新可通过 API 触发，校验逻辑正常。

## D6. 每周 ETF 列表全量同步
状态：待开始
优先级：P1
依赖：D2
描述：每周日全量同步 ETF 列表，检测新上市/退市 ETF，更新 etf_basic 表的 is_active 字段。
验收：能检测到新增和退市 ETF。

## D7. Data 模块 REST API
状态：待开始
优先级：P0
依赖：D1
描述：实现 CLAUDE.md 中定义的9个 Data API 端点：GET /api/v1/etf/list、GET /api/v1/etf/list/categories、GET /api/v1/etf/{code}/info、GET /api/v1/etf/{code}/daily、GET /api/v1/etf/{code}/latest、GET /api/v1/etf/batch/daily、POST /api/v1/data/sync、GET /api/v1/data/status、GET /api/v1/data/calendar。统一响应格式。
验收：所有端点可调用，返回格式符合契约。

## D8. 交易日历维护
状态：待开始
优先级：P1
依赖：D1
描述：通过 akshare 的 tool_trade_date_hist_sina() 获取交易日历，存入数据库或缓存。供 scheduler.py 判断是否为交易日。
验收：GET /api/v1/data/calendar 返回正确的交易日历。
