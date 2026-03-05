"""
Research模块路由 — 研报、投资框架、情绪、宏观共识API
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import async_session, get_db
from backend.app.models.research import ResearchFramework, ResearchReport
from backend.app.services.research import (
    analyze_pending_reports,
    crawl_eastmoney_reports,
    generate_frameworks,
    get_macro_consensus,
    get_sentiment_stats,
)
from backend.app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────── 5个GET端点 ────────────────


@router.get("/research/reports")
async def research_reports(
    etf_code: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """研报列表（分页，可按etf_code筛选）"""
    base_query = select(ResearchReport)
    count_query = select(func.count(ResearchReport.id))

    if etf_code:
        base_query = base_query.where(ResearchReport.etf_code == etf_code)
        count_query = count_query.where(ResearchReport.etf_code == etf_code)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = (
        base_query
        .order_by(ResearchReport.report_date.desc(), ResearchReport.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    items = []
    for r in rows:
        summary = None
        if r.analysis and isinstance(r.analysis, dict):
            summary = r.analysis.get("summary")
        items.append({
            "id": r.id,
            "title": r.title,
            "source": r.source,
            "report_date": r.report_date.isoformat() if r.report_date else None,
            "summary": summary,
            "etf_code": r.etf_code,
        })

    return success_response({"total": total, "items": items})


@router.get("/research/macro")
async def research_macro(db: AsyncSession = Depends(get_db)):
    """宏观共识"""
    data = await get_macro_consensus(db)
    return success_response(data)


@router.get("/research/reports/{report_id}")
async def research_report_detail(report_id: int, db: AsyncSession = Depends(get_db)):
    """研报详情"""
    result = await db.execute(
        select(ResearchReport).where(ResearchReport.id == report_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        return error_response(404, f"研报 {report_id} 不存在")

    return success_response({
        "id": r.id,
        "title": r.title,
        "source": r.source,
        "content": r.content,
        "analysis": r.analysis,
        "report_date": r.report_date.isoformat() if r.report_date else None,
        "etf_code": r.etf_code,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    })


@router.get("/research/{etf_code}/framework")
async def research_framework(etf_code: str, db: AsyncSession = Depends(get_db)):
    """最新投资框架"""
    result = await db.execute(
        select(ResearchFramework)
        .where(ResearchFramework.etf_code == etf_code)
        .order_by(ResearchFramework.week_date.desc())
        .limit(1)
    )
    fw = result.scalar_one_or_none()
    if not fw:
        return error_response(404, f"ETF {etf_code} 无投资框架数据")

    return success_response({
        "etf_code": fw.etf_code,
        "week_date": fw.week_date.isoformat() if fw.week_date else None,
        "fundamental_score": float(fw.fundamental_score) if fw.fundamental_score else None,
        "technical_score": float(fw.technical_score) if fw.technical_score else None,
        "sentiment_score": float(fw.sentiment_score) if fw.sentiment_score else None,
        "overall_score": float(fw.overall_score) if fw.overall_score else None,
        "framework_data": fw.framework_data,
    })


@router.get("/research/{etf_code}/sentiment")
async def research_sentiment(etf_code: str, db: AsyncSession = Depends(get_db)):
    """情绪统计"""
    data = await get_sentiment_stats(db, etf_code)
    return success_response(data)


# ──────────────── 2个POST端点（scheduler调用） ────────────────


async def _crawl_and_analyze():
    """后台任务：爬取 + 分析"""
    async with async_session() as db:
        try:
            inserted = await crawl_eastmoney_reports(db)
            logger.info("爬取完成: %d 条新研报", inserted)
        except Exception as e:
            logger.error("爬取失败: %s", e)

        try:
            analyzed = await analyze_pending_reports(db)
            logger.info("分析完成: %d 条", analyzed)
        except Exception as e:
            logger.error("分析失败: %s", e)


async def _update_frameworks():
    """后台任务：更新投资框架"""
    async with async_session() as db:
        try:
            created = await generate_frameworks(db)
            logger.info("框架更新完成: %d 条", created)
        except Exception as e:
            logger.error("框架更新失败: %s", e)


@router.post("/research/crawl")
async def research_crawl(background_tasks: BackgroundTasks):
    """触发研报爬取+分析（后台执行）"""
    background_tasks.add_task(_crawl_and_analyze)
    return success_response({"message": "研报爬取任务已启动"})


@router.post("/research/framework/update")
async def research_framework_update(background_tasks: BackgroundTasks):
    """触发投资框架更新（后台执行）"""
    background_tasks.add_task(_update_frameworks)
    return success_response({"message": "投资框架更新任务已启动"})
