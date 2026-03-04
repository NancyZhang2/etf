# Research模块 — 任务队列

> Orchestrator 监控此文件，发现"待开始"任务时启动 Worker 执行。
> 状态：待开始 → 进行中 → 已完成 / BLOCKED

---

## R1. 东方财富研报爬虫
状态：待开始
优先级：P0
描述：爬取东方财富研报中心公开研报，每日18:00由 scheduler.py 触发。实现：请求限速、失败重试2次、第2次失败后降级为 Claude API 基于公开信息生成分析。写入 research_reports 表。
验收：可正常爬取研报，去重（UNIQUE约束），降级机制可工作。

## R2. Claude API 结构化分析
状态：待开始
优先级：P0
依赖：R1
描述：每篇研报通过 Claude API 提取结构化信息：摘要、ETF关联度与情绪（看多/看空/中性）、宏观观点、行业展望、风险因素、置信度（0-1）。结果写入 research_reports.analysis（jsonb）。设每日分析上限控制成本。
验收：分析结果格式正确，可通过API查询。

## R3. 投资框架自动生成
状态：待开始
优先级：P1
依赖：R2
描述：综合多篇研报，为 Top50 ETF 生成周度投资框架：基本面评分、技术面评分、资金面/情绪评分、共识度、综合评分。写入 research_frameworks 表，保留历史快照。每周日由 scheduler.py 触发。
验收：框架可自动生成，历史快照可查询。

## R4. 宏观观点汇总
状态：待开始
优先级：P1
依赖：R2
描述：从多篇研报的宏观观点中提取共识：经济形势、流动性、政策方向、关键风险点。通过 GET /api/v1/research/macro 返回。
验收：宏观观点可正常汇总和查询。

## R5. Research 模块 REST API
状态：待开始
优先级：P0
描述：实现 CLAUDE.md 中定义的5个 Research API 端点：GET /reports、GET /reports/{id}、GET /{etf_code}/framework、GET /{etf_code}/sentiment、GET /macro。统一响应格式。
验收：所有端点可调用。
