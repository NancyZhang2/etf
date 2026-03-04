# PROGRESS.md — 经验库

> Worker完成任务后在此追加经验教训。
> 格式：## [日期] [模块名] / 任务：xxx / 教训：xxx
> 本文件通过软链接共享给所有Worktree。

---

## 2026-03-03 [项目规划] 项目初始化与需求定义

任务：完成竞品调研、项目需求文档、CLAUDE.md架构设计、竞品策略逆向工程

教训：
1. 竞品调研覆盖了17个平台（国内量化回测4个、ETF工具4个、投顾组合3个、海外平台5个），
   发现A股市场缺少"ETF专精 + AI研报 + 信号推送"三合一的平台，这是我们的切入点。
2. 从蛋卷/果仁/华宝/集思录共提取了10个可复刻策略（B1~B10），
   其中蛋卷二八轮动(B1)和果仁动量溢价轮动(B6)为第一批实现目标。
3. 策略体系最终定为两大类六子类（经典A1~A4 + 竞品B1~B2），
   项目需求.md中有完整的伪代码和参数表，竞品策略.md中有10个策略的逆向细节。

关键决策记录：
- 回测引擎选vectorbt，禁止backtrader（性能和API设计更优）
- 数据源选akshare（免费、覆盖全A股ETF）
- 研报分析用Claude API（结构化输出能力强）
- 前端React 18 + TypeScript + TailwindCSS（响应式，手机优先）
- 所有模块间通信必须走REST API，禁止直接import
- 系统架构采用 Orchestrator/Worker 模式（4个独立进程）
- 开发隔离使用 Git Worktree，每模块独立分支
- 管理入口使用 Web Manager（手机友好，端口8080）

---

## 2026-03-04 [基础设施] Phase 0 基础设施搭建

任务：从零搭建完整项目基础设施（目录骨架、Git、后端框架、调度器、管理界面、定时任务、备份脚本、Worktree）

教训：
1. Git worktree 创建前必须有至少一个 commit，否则无法 checkout 分支。
2. Orchestrator dry-run 模式验证通过，可识别5个模块的待办任务（data:D1、quant:Q1、research:R1、frontend:F1、notification:N1）。
3. TODO.md 的解析依赖固定格式（"## X1. 标题" + "状态：xxx"），Worker 修改 TODO.md 时必须保持格式一致。
4. Web Manager 静态文件使用 FastAPI StaticFiles 挂载，index.html 通过 API 轮询获取任务状态。
5. scheduler.py 使用 APScheduler BlockingScheduler，交易日判断先检查周末，再尝试从 Data API 获取日历。

---

## 阶段进度追踪

### Phase 0：基础设施搭建
状态：已完成

| 任务 | 类别 | 状态 | 备注 |
|------|------|------|------|
| 项目目录结构搭建 | 项目骨架 | 已完成 | modules/、orchestrator/、web_manager/、scripts/、logs/、backend/ |
| modules/*/TODO.md 创建 | 任务队列 | 已完成 | data/quant/research/frontend/notification 五个模块 |
| Git Worktree 结构搭建 | 开发隔离 | 已完成 | 5个worktree + 软链接（CLAUDE.md/PROGRESS.md/TODO.md） |
| Orchestrator 核心调度器 | 进程1 | 已完成 | 监控TODO.md、启动Worker、解析日志、失败重试 |
| Worker 启动模板 | 进程2 | 已完成 | worker_prompt_template.txt、stream-json日志 |
| Web Manager 管理界面 | 进程3 | 已完成 | FastAPI 8080、任务派发/看板/日志/语音 |
| scheduler.py 定时任务 | 进程4 | 已完成 | 15:30数据/16:00信号/18:00研报/每小时备份 |
| backup.sh 数据库备份 | 运维 | 已完成 | 增量+全量备份脚本 |
| .env 配置模板 | 配置 | 已完成 | DATABASE_URL 等环境变量 |

交付标准：Orchestrator 可启动并监控TODO.md → Web Manager 可打开看板 → Scheduler 可触发定时任务

### Phase 1：数据基座 + 核心回测
状态：未开始

| 任务 | 模块 | 状态 | 备注 |
|------|------|------|------|
| PostgreSQL建库建表 | Data | 待开始 | 10张核心表，见CLAUDE.md |
| ETF基础信息拉取（akshare） | Data | 待开始 | 约900+只ETF |
| 历史日K线全量拉取 | Data | 待开始 | 约180万条记录 |
| 数据清洗流程 | Data | 待开始 | 停牌标记/异常检测/复权/去重 |
| 每日增量更新（15:30定时） | Data | 待开始 | scheduler.py触发 |
| Data模块REST API（9个端点） | Data | 待开始 | 见CLAUDE.md接口契约 |
| vectorbt回测引擎封装 | Quant | 待开始 | 逐年+全区间，含全部指标 |
| 动量轮动策略（A1）实现 | Quant | 待开始 | 第一个策略，验证整条链路 |
| 回测结果存储 | Quant | 待开始 | backtest_results表 |

交付标准：API触发数据更新 → 运行动量轮动回测 → 返回JSON结果

### Phase 2：策略矩阵 + 信号系统
状态：未开始

| 任务 | 模块 | 状态 | 备注 |
|------|------|------|------|
| 均线趋势策略（A2） | Quant | 待开始 | 单均线/双均线+大盘过滤器 |
| 网格交易策略（A3） | Quant | 待开始 | 等差/等比网格 |
| 大类资产配置策略（A4） | Quant | 待开始 | 全天候/风险平价/股债平衡 |
| 蛋卷二八轮动复刻（B1） | Quant | 待开始 | 含切换缓冲+均线保护增强 |
| 果仁行业轮动复刻（B6） | Quant | 待开始 | 动量+溢价率双因子 |
| 每日信号自动生成 | Quant | 待开始 | 16:00定时，全策略运行 |
| 策略参数优化 | Quant | 待开始 | P1，网格搜索+Walk-Forward |
| 虚拟持仓跟踪 | Quant | 待开始 | P1，virtual_portfolios表 |

交付标准：六大策略可回测、可生成信号、信号写入数据库

### Phase 3：研报引擎
状态：未开始

| 任务 | 模块 | 状态 | 备注 |
|------|------|------|------|
| 东方财富研报爬虫 | Research | 待开始 | 每日18:00，失败重试2次 |
| Claude API结构化分析 | Research | 待开始 | 输出摘要/情绪/宏观/行业/风险 |
| 投资框架自动生成 | Research | 待开始 | P1，Top50 ETF周度框架 |
| 宏观观点汇总 | Research | 待开始 | P1 |
| Research模块REST API | Research | 待开始 | 5个端点 |

交付标准：每日自动爬取研报并AI分析，API可查询

### Phase 4：前端 + 推送
状态：未开始

| 任务 | 模块 | 状态 | 备注 |
|------|------|------|------|
| 首页Dashboard | Frontend | 待开始 | 信号摘要+行情+研报速览 |
| ETF列表+详情页 | Frontend | 待开始 | 分类浏览/K线图/关联信号 |
| 策略中心 | Frontend | 待开始 | 核心页面，回测可视化 |
| 信号面板 | Frontend | 待开始 | 今日/日历/历史 |
| 微信模板消息推送 | Notification | 待开始 | 16:30推送 |
| 邮件推送 | Notification | 待开始 | HTML格式+内嵌图表 |
| 研报中心页面 | Frontend | 待开始 | P1 |
| 用户订阅管理 | Frontend/Notification | 待开始 | P1 |
| 策略对比 | Frontend | 待开始 | P1，2~4个策略并排 |
| 参数优化可视化 | Frontend | 待开始 | P2，热力图 |
| 信号日历视图 | Frontend | 待开始 | P2 |

交付标准：完整可用Web应用，用户可注册、查看策略、收到推送

---

## 技术备忘

### akshare常用接口
- `fund_etf_spot_em()` — ETF实时行情/基础信息
- `fund_etf_hist_em(symbol, period="daily", adjust="qfq")` — 历史日K（前复权）
- `tool_trade_date_hist_sina()` — 交易日历

### vectorbt使用注意
- 输入数据必须是pandas DataFrame，index为DatetimeIndex
- `vbt.Portfolio.from_signals()` 是核心回测入口
- 逐年回测需手动切片数据后循环调用
- 设置 `fees=0.0001`（万1佣金）、`slippage=0.001`（0.1%滑点）

### 策略基类设计要点
- 所有策略继承 `BaseStrategy`
- 必须实现 `generate_signals(data) -> DataFrame[BUY/SELL/HOLD]`
- 必须实现 `get_default_params() -> dict`
- 参数通过 `__init__(params: dict)` 注入，支持JSON序列化
- 信号生成逻辑必须与回测逻辑完全一致（同一份代码）

### 数据库连接
- 使用SQLAlchemy 2.0的async session
- 所有操作在事务内
- 连接串从环境变量 `DATABASE_URL` 读取

### 已知风险
- akshare接口不稳定，可能被限速 → 需实现重试+指数退避
- ETF溢价率数据akshare可能不提供 → B6策略溢价率因子可能需降级为纯动量
- Claude API调用成本需控制 → 研报分析设每日上限，优先分析热门ETF相关研报
