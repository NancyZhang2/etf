# ETF量化投研平台 - CLAUDE.md

## 项目概述
全A股场内ETF量化投研平台，面向有投资经验的个人投资者。
核心功能：ETF数据自动管理、量化策略编写与回测、
研报AI分析、每日交易信号推送、前端可视化展示。
详细需求见 项目需求.md，竞品分析见 竞品调研.md。

## 技术栈
- 后端：Python 3.11 + FastAPI
- 数据库：PostgreSQL 15
- ORM：SQLAlchemy 2.0
- 数据源：akshare（ETF行情）、
          东方财富+券商网站（研报爬取）、
          Claude API（研报分析）
- 回测引擎：vectorbt（禁止使用backtrader）
- 前端：React 18 + TypeScript + TailwindCSS
- 推送：微信公众号模板消息 + SMTP邮件
- 部署：远程服务器，Nginx反向代理

## 系统架构总览

整个系统由四个独立进程组成，各自独立启动：

### 1. Orchestrator（orchestrator/orchestrator.py）
核心调度器，长期运行。
监控五个模块的TODO.md，发现未完成任务时
启动Worker（新的Claude Code实例）去完成。
支持最多5个Worker并行，每个模块最多1个。
解析Worker的stream-json日志，失败时带诊断信息重试。

### 2. Worker（每次由Orchestrator启动的Claude Code实例）
每个Worker是一个独立的Claude Code进程。
在对应模块的Worktree目录下工作。
完成一个任务后exit，不跨任务持续运行。
启动命令格式：
claude -p "[prompt]" \
  --dangerously-skip-permissions \
  --output-format stream-json \
  --verbose

### 3. Web Manager（web_manager/main.py，端口8080）
手机友好的Web管理界面。
功能：任务派发、任务看板、Worker状态、
      日志查看、语音输入。
是用户唯一的日常交互入口。

### 4. 定时任务（scripts/scheduler.py）
每天15:30触发Data模块增量更新。
每天16:00触发Quant模块全策略信号生成。
每天18:00触发Research模块研报爬取。
每周日触发Research模块投资框架更新。
每小时触发数据库备份。

## 项目结构
```
project-etf/                    # 主repo（main分支）
├── CLAUDE.md                   # 本文件（软链接源头）
├── PROGRESS.md                 # 经验库（软链接源头）
├── 项目需求.md                  # 详细需求文档
├── 竞品调研.md                  # 竞品分析报告
├── modules/
│   ├── data/TODO.md            # data模块任务队列（软链接源头）
│   ├── quant/TODO.md
│   ├── research/TODO.md
│   ├── frontend/TODO.md
│   └── notification/TODO.md
├── orchestrator/
│   ├── orchestrator.py
│   └── worker_prompt_template.txt
├── web_manager/
│   ├── main.py                 # FastAPI，端口8080
│   └── static/                 # 前端HTML/JS
├── scripts/
│   ├── backup.sh               # 数据库备份
│   └── scheduler.py            # 定时任务
├── logs/                       # Worker的stream-json日志
│   └── [模块名]-[时间戳].jsonl
└── backend/                    # 由各模块Worker开发
    ├── app/
    │   ├── main.py             # FastAPI入口
    │   ├── config.py           # 环境变量配置
    │   ├── api/
    │   │   ├── data.py         # Data模块路由
    │   │   ├── quant.py        # Quant模块路由
    │   │   ├── research.py     # Research模块路由
    │   │   └── notification.py # Notification模块路由
    │   ├── services/
    │   │   ├── etf_data.py     # ETF数据拉取与清洗
    │   │   ├── backtest.py     # vectorbt回测引擎
    │   │   ├── strategies/     # 策略实现
    │   │   │   ├── base.py     # 策略基类
    │   │   │   ├── momentum.py # A1.动量轮动
    │   │   │   ├── ma_trend.py # A2.均线趋势
    │   │   │   ├── grid.py     # A3.网格交易
    │   │   │   ├── asset_alloc.py # A4.大类资产配置
    │   │   │   ├── egg_28.py   # B1.蛋卷二八轮动复刻
    │   │   │   └── guorn_rotation.py # B2.果仁行业轮动复刻
    │   │   ├── signal.py       # 信号生成与虚拟持仓
    │   │   ├── research.py     # 研报爬取与AI分析
    │   │   └── notify.py       # 推送服务
    │   ├── models/             # SQLAlchemy模型
    │   └── schemas/            # Pydantic请求/响应模型
    ├── tests/
    └── requirements.txt

# 前端项目（独立目录）
frontend/
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx       # 首页（信号摘要+行情+研报速览）
│   │   ├── EtfList.tsx         # ETF列表（分类浏览/搜索/排序）
│   │   ├── EtfDetail.tsx       # ETF详情（行情+K线+研报+信号）
│   │   ├── StrategyList.tsx    # 策略列表（经典/竞品两大类）
│   │   ├── StrategyDetail.tsx  # 策略详情（参数配置+回测+信号）
│   │   ├── StrategyCompare.tsx # 策略对比（2~4个并排）
│   │   ├── SignalPanel.tsx     # 信号面板（今日/日历/历史）
│   │   ├── ResearchList.tsx    # 研报列表
│   │   ├── ResearchDetail.tsx  # 研报详情（原文+AI分析）
│   │   └── UserCenter.tsx      # 订阅管理+推送设置
│   ├── components/
│   │   ├── charts/             # 图表组件（净值曲线/热力图/柱状图）
│   │   └── common/             # 通用组件
│   └── services/               # API调用层
├── package.json
└── tsconfig.json

# Worktree目录（与主repo平级）
../worktree-data/               # feature/data分支
├── CLAUDE.md -> ../project-etf/CLAUDE.md（软链接）
├── PROGRESS.md -> ../project-etf/PROGRESS.md（软链接）
├── TODO.md -> ../project-etf/modules/data/TODO.md（软链接）
└── backend/（Worker在此目录下开发data模块代码）

../worktree-quant/              # feature/quant分支
../worktree-research/           # feature/research分支
../worktree-frontend/           # feature/frontend分支
../worktree-notification/       # feature/notification分支
```

## 模块划分与职责

### Data模块（worktree-data）
- 职责：全A股场内ETF数据管理
  - ETF基础信息维护（900+只，含分类：宽基/行业/主题/商品/债券/货币/跨境）
  - 历史行情一次性全量拉取（约180万条记录）
  - 每日定时增量更新（15:30后触发）
  - 数据清洗（停牌标记、异常值检测、复权处理、去重校验）
  - 每周ETF列表全量同步（新上市/退市）
- 数据来源：akshare
- 对外接口：REST API，供其他所有模块调用
- 数据校验：增量更新后校验记录数 ≥ 已知ETF的90%，否则告警
- 禁止：其他模块直接读写数据库，必须通过Data API

### Quant模块（worktree-quant）
- 职责：量化策略实现、回测、信号生成、实盘跟踪
- 策略体系（两大类六个子类）：
  A. 经典量化策略
     A1. 动量轮动策略（ETF池动量排名+定期调仓+避险机制）
     A2. 均线趋势策略（单均线/双均线交叉+大盘过滤器）
     A3. 网格交易策略（等差/等比网格+价格触发）
     A4. 大类资产配置策略（全天候/风险平价/股债动态平衡三模型）
  B. 竞品逆向工程策略
     B1. 蛋卷二八轮动复刻版（300/500动量对比+切换缓冲+均线保护）
     B2. 果仁行业轮动复刻版（动量+溢价率双因子排名+行业集中度限制）
- 回测引擎：vectorbt，输出逐年（近5年）+全区间回测结果
  指标：年化收益/最大回撤/夏普/索提诺/卡尔玛/胜率/盈亏比/换手率等
- 信号生成：每日数据更新后自动运行全部已启用策略，产出BUY/SELL/HOLD信号
- 实盘跟踪：虚拟持仓模拟执行，跟踪净值曲线，监控实盘与回测偏差
- 参数优化：支持1~2个参数网格搜索+Walk-Forward验证
- 所有策略参数通过JSON配置，用户可在前端调参后重新回测
- 依赖：Data模块REST API
- 未完成前使用mock数据开发

### Research模块（worktree-research）
- 职责：研报采集、AI结构化分析、投资框架生成
  - 研报爬取：东方财富研报中心+券商网站公开研报，每日18:00
  - AI分析：每篇研报通过Claude API提取结构化信息
    （摘要、ETF关联度与情绪、宏观观点、行业展望、风险因素、置信度）
  - 投资框架：综合多篇研报为Top50 ETF生成周度投资框架
    （基本面/技术面/资金面/共识度/综合评分），保留历史快照
- 爬虫策略：失败自动重试2次，第2次失败后
            降级为Claude API基于公开信息生成分析
- 依赖：Data模块REST API

### Frontend模块（worktree-frontend）
- 职责：React网站，面向有投资经验的个人投资者
- 核心页面：
  - 首页Dashboard：今日信号摘要+热门ETF行情+最新研报速览
  - ETF中心：列表（分类浏览/搜索/排序）+ 详情（行情/K线/信号/研报）
  - 策略中心：策略列表（经典/竞品两大类）+ 策略详情（参数配置/回测仪表盘/信号/实盘跟踪）+ 策略对比 + 参数优化可视化
  - 信号面板：今日信号 + 信号日历 + 信号历史
  - 研报中心：研报列表 + 详情（原文+AI分析）+ ETF投资框架 + 宏观观点
  - 用户中心：订阅管理 + 推送设置 + 账户信息
- 回测可视化：净值曲线、回撤曲线、月度热力图、逐年柱状图、持仓变动图、收益分布直方图
- 响应式设计：手机端为信号/研报主场景，PC端为策略配置/回测分析主场景
- 依赖：所有后端REST API
- Data模块API未完成前使用mock数据开发

### Notification模块（worktree-notification）
- 职责：多渠道推送服务
  - 微信公众号模板消息推送
  - SMTP邮件推送（HTML格式，内嵌图表）
  - 推送内容：每日交易信号、重要研报摘要、策略表现周报
  - 推送时间：交易日16:30（数据更新+信号生成完成后）
- 订阅管理：
  - 订阅维度：按策略/按ETF/按类型（信号/研报/周报）
  - 推送频率：实时/每日汇总/每周汇总
  - 渠道选择：微信/邮件/两者
- 依赖：Quant模块信号API、Research模块结论API

## 核心数据库表

### etf_basic（ETF基本信息）
- code: varchar(10) PRIMARY KEY
- name: varchar(100)
- category: varchar(50)         -- 宽基/行业/主题/商品/债券/货币/跨境
- exchange: varchar(10)（SH/SZ）
- list_date: date               -- 上市日期
- is_active: boolean DEFAULT true -- 是否在市（退市标记）
- created_at: timestamp

### etf_daily（ETF日行情）
- id: bigserial PRIMARY KEY
- code: varchar(10) REFERENCES etf_basic
- trade_date: date
- open/high/low/close: decimal(10,4)
- volume: bigint
- amount: decimal(20,2)
- pre_close: decimal(10,4)      -- 前收盘价（复权用）
- UNIQUE(code, trade_date)

### strategy_categories（策略分类）
- id: serial PRIMARY KEY
- name: varchar(50)             -- '经典量化策略' / '竞品逆向策略'
- description: text

### strategies（量化策略）
- id: serial PRIMARY KEY
- category_id: int REFERENCES strategy_categories
- name: varchar(100)
- strategy_type: varchar(50)    -- momentum/ma_trend/grid/asset_alloc/egg_28/guorn_rotation
- description: text
- params: jsonb                 -- 当前参数
- default_params: jsonb         -- 默认参数模板
- etf_pool: jsonb               -- 默认ETF池
- is_active: boolean DEFAULT true -- 是否启用信号生成
- last_signal_date: date
- created_at: timestamp

### backtest_results（回测结果）
- id: serial PRIMARY KEY
- strategy_id: int REFERENCES strategies
- year: int（0表示全区间）
- total_return: decimal(10,4)
- annual_return: decimal(8,4)
- max_drawdown: decimal(8,4)
- annual_volatility: decimal(8,4)
- sharpe_ratio: decimal(8,4)
- sortino_ratio: decimal(8,4)
- calmar_ratio: decimal(8,4)
- win_rate: decimal(8,4)
- profit_loss_ratio: decimal(8,4)
- total_trades: int
- avg_holding_days: decimal(8,2)
- turnover_rate: decimal(8,4)
- benchmark_return: decimal(10,4)
- excess_return: decimal(10,4)
- params_snapshot: jsonb

### trading_signals（每日交易信号）
- id: bigserial PRIMARY KEY
- strategy_id: int REFERENCES strategies
- etf_code: varchar(10) REFERENCES etf_basic
- signal_date: date
- signal: varchar(10)（BUY/SELL/HOLD）
- target_weight: decimal(6,4)   -- 目标权重
- reason: text
- created_at: timestamp

### virtual_portfolios（虚拟持仓跟踪）
- id: bigserial PRIMARY KEY
- strategy_id: int REFERENCES strategies
- trade_date: date
- etf_code: varchar(10)
- position: decimal(10,4)       -- 持仓比例
- nav: decimal(12,4)            -- 当日净值
- daily_return: decimal(8,6)    -- 当日收益率

### research_reports（研报与分析）
- id: serial PRIMARY KEY
- etf_code: varchar(10) REFERENCES etf_basic
- source: varchar(100)
- title: varchar(200)
- content: text
- analysis: jsonb               -- Claude API结构化分析结果
- report_date: date
- created_at: timestamp
- UNIQUE(title, source, report_date)

### research_frameworks（ETF投资框架）
- id: serial PRIMARY KEY
- etf_code: varchar(10) REFERENCES etf_basic
- week_date: date               -- 框架生成周
- fundamental_score: decimal(4,2)
- technical_score: decimal(4,2)
- sentiment_score: decimal(4,2)
- overall_score: decimal(4,2)
- framework_data: jsonb         -- 完整框架JSON
- source_report_ids: int[]      -- 关联研报ID列表

### users（用户表）
- id: serial PRIMARY KEY
- email: varchar(200) UNIQUE
- wechat_openid: varchar(100)
- created_at: timestamp

### user_subscriptions（用户订阅）
- id: serial PRIMARY KEY
- user_id: int REFERENCES users
- subscription_type: varchar(20) -- strategy/etf/signal/research/weekly
- target_id: int
- channel: varchar(20)（wechat/email）
- frequency: varchar(20)        -- realtime/daily/weekly
- is_active: boolean DEFAULT true

## 模块间接口契约

### Data模块对外API
GET  /api/v1/etf/list
     参数：category（可选，分类筛选）
     返回：[{code, name, category, exchange}]

GET  /api/v1/etf/list/categories
     返回：[{category, count}]

GET  /api/v1/etf/{code}/info
     返回：{code, name, category, exchange, list_date}

GET  /api/v1/etf/{code}/daily
     参数：start_date, end_date
     返回：[{trade_date, open, high, low,
             close, volume, amount}]

GET  /api/v1/etf/{code}/latest
     返回：{trade_date, open, high, low,
             close, volume, amount}

GET  /api/v1/etf/batch/daily
     参数：codes（逗号分隔）, start_date, end_date
     返回：{code: [{trade_date, ...}]}

POST /api/v1/data/sync
     触发增量数据更新（定时任务调用）

GET  /api/v1/data/status
     返回：{last_sync, record_count, etf_count, status}

GET  /api/v1/data/calendar
     参数：year（可选）
     返回：[{date, is_trading_day}]

### Quant模块对外API
GET  /api/v1/strategies
     参数：category_id（可选）
     返回：[{id, name, category, strategy_type,
             description, is_active}]

GET  /api/v1/strategies/{id}
     返回：{id, name, strategy_type, description,
             params, default_params, etf_pool}

GET  /api/v1/strategies/{id}/backtest
     参数：year（可选，不传返回全区间）
     返回：{total_return, annual_return, max_drawdown,
             sharpe_ratio, sortino_ratio, calmar_ratio,
             win_rate, profit_loss_ratio, total_trades,
             benchmark_return, excess_return}

POST /api/v1/strategies/{id}/backtest
     body：{params}（自定义参数重新回测）
     返回：同上

GET  /api/v1/strategies/{id}/backtest/yearly
     返回：[{year, annual_return, max_drawdown,
              sharpe_ratio, ...}]（近5年逐年结果）

GET  /api/v1/strategies/{id}/portfolio
     返回：[{trade_date, etf_code, position,
              nav, daily_return}]（虚拟持仓）

GET  /api/v1/signals/latest
     参数：strategy_id（可选）
     返回：[{strategy_name, etf_code, etf_name,
              signal, target_weight, reason, signal_date}]

GET  /api/v1/signals/history
     参数：strategy_id, etf_code, start_date, end_date
     返回：[{signal_date, signal, reason}]

GET  /api/v1/signals/calendar
     参数：month（YYYY-MM）
     返回：{date: [{strategy_name, etf_code, signal}]}

POST /api/v1/strategies/{id}/optimize
     body：{param_name, param_range, metric}
     返回：[{param_value, sharpe_ratio, annual_return, ...}]

### Research模块对外API
GET  /api/v1/research/reports
     参数：etf_code, page, page_size
     返回：{total, items: [{id, title, source,
              report_date, summary}]}

GET  /api/v1/research/reports/{id}
     返回：{title, source, content, analysis,
             report_date}

GET  /api/v1/research/{etf_code}/framework
     返回：{fundamental_score, technical_score,
             sentiment_score, overall_score,
             framework_data, week_date}

GET  /api/v1/research/{etf_code}/sentiment
     返回：{bullish_count, bearish_count,
             neutral_count, overall_sentiment}

GET  /api/v1/research/macro
     返回：{economy, liquidity, policy,
             key_points, updated_at}

### Notification模块对外API
POST /api/v1/notify/subscribe
     body：{user_id, subscription_type,
             target_id, channel, frequency}

DELETE /api/v1/notify/subscribe/{id}
     退订

GET  /api/v1/notify/subscriptions
     参数：user_id
     返回：[{id, subscription_type, target_id,
              channel, frequency, is_active}]

PUT  /api/v1/notify/subscribe/{id}
     body：{channel, frequency, is_active}
     修改订阅设置

## 代码规范

### 必须遵守
- 所有API接口统一返回格式：
  成功：{"code": 0, "data": ..., "message": "ok"}
  失败：{"code": 错误码, "data": null,
        "message": "错误描述"}
- 所有数据库操作必须在事务内执行
- 所有外部API调用必须有超时设置和重试逻辑
- 业务逻辑写在services层，不在api层
- 新增功能必须写对应测试用例

### 禁止事项
- 禁止硬编码配置，统一用环境变量或.env文件
- 禁止跨模块直接调用service函数，必须通过REST API
- 禁止修改etf_daily表的历史数据

## 任务管理规则

### Worker接收任务的方式
Worker启动时任务已经通过prompt传入，
不需要自己去读TODO.md取任务。
Orchestrator负责取任务和传递给Worker。

### Worker完成任务后必须做的事
1. 确保代码可运行，相关测试通过
2. 将经验教训追加到PROGRESS.md
   格式：## [日期] [模块名]\n任务：xxx\n教训：xxx
3. git add + git commit
   格式：[模块名] 具体描述
4. exit

### Worker遇到无法完成的任务时
1. 不要无限尝试，最多自行重试2次
2. 在PROGRESS.md记录失败原因
3. exit（Orchestrator会处理后续重试和BLOCKED标记）

## 日志规范
- Worker日志路径：
  主repo的logs/[模块名]-[任务序号]-[时间戳].jsonl
- 日志格式：stream-json，每行一个JSON事件
- Orchestrator通过解析此日志诊断失败原因