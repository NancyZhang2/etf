"""
Data模块路由 — 9个API端点完整实现
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.etf import EtfBasic, EtfDaily, TradingCalendar
from backend.app.services.etf_data import (
    fetch_and_store_etf_list,
    fetch_trading_calendar,
    incremental_update,
    get_data_status,
)
from backend.app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/etf/list")
async def etf_list(category: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """ETF列表，可按分类筛选"""
    query = select(EtfBasic).where(EtfBasic.is_active == True)
    if category:
        query = query.where(EtfBasic.category == category)
    query = query.order_by(EtfBasic.code)

    result = await db.execute(query)
    etfs = result.scalars().all()
    data = [
        {"code": e.code, "name": e.name, "category": e.category, "exchange": e.exchange}
        for e in etfs
    ]
    return success_response(data)


@router.get("/etf/list/categories")
async def etf_categories(db: AsyncSession = Depends(get_db)):
    """ETF分类及数量"""
    query = (
        select(EtfBasic.category, func.count().label("count"))
        .where(EtfBasic.is_active == True)
        .group_by(EtfBasic.category)
        .order_by(func.count().desc())
    )
    result = await db.execute(query)
    data = [{"category": row[0], "count": row[1]} for row in result.fetchall()]
    return success_response(data)


@router.get("/etf/batch/daily")
async def etf_batch_daily(
    codes: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """批量获取多只ETF日行情"""
    if not codes:
        return error_response(400, "codes参数不能为空")

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) > 20:
        return error_response(400, "单次最多查询20只ETF")

    result_data = {}
    for code in code_list:
        query = select(EtfDaily).where(EtfDaily.code == code)
        if start_date:
            query = query.where(EtfDaily.trade_date >= _parse_date(start_date))
        if end_date:
            query = query.where(EtfDaily.trade_date <= _parse_date(end_date))
        query = query.order_by(EtfDaily.trade_date)

        result = await db.execute(query)
        rows = result.scalars().all()
        result_data[code] = [
            {
                "trade_date": r.trade_date.isoformat(),
                "open": float(r.open) if r.open else None,
                "high": float(r.high) if r.high else None,
                "low": float(r.low) if r.low else None,
                "close": float(r.close) if r.close else None,
                "volume": r.volume,
                "amount": float(r.amount) if r.amount else None,
            }
            for r in rows
        ]

    return success_response(result_data)


@router.get("/etf/{code}/info")
async def etf_info(code: str, db: AsyncSession = Depends(get_db)):
    """单只ETF基本信息"""
    result = await db.execute(select(EtfBasic).where(EtfBasic.code == code))
    etf = result.scalar_one_or_none()
    if not etf:
        return error_response(404, f"ETF {code} 不存在")
    return success_response({
        "code": etf.code,
        "name": etf.name,
        "category": etf.category,
        "exchange": etf.exchange,
        "list_date": etf.list_date.isoformat() if etf.list_date else None,
    })


@router.get("/etf/{code}/daily")
async def etf_daily(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """ETF日行情"""
    # 验证ETF存在
    etf_result = await db.execute(select(EtfBasic.code).where(EtfBasic.code == code))
    if not etf_result.scalar_one_or_none():
        return error_response(404, f"ETF {code} 不存在")

    query = select(EtfDaily).where(EtfDaily.code == code)

    if start_date:
        query = query.where(EtfDaily.trade_date >= _parse_date(start_date))
    if end_date:
        query = query.where(EtfDaily.trade_date <= _parse_date(end_date))

    query = query.order_by(EtfDaily.trade_date)
    result = await db.execute(query)
    rows = result.scalars().all()

    data = [
        {
            "trade_date": r.trade_date.isoformat(),
            "open": float(r.open) if r.open else None,
            "high": float(r.high) if r.high else None,
            "low": float(r.low) if r.low else None,
            "close": float(r.close) if r.close else None,
            "volume": r.volume,
            "amount": float(r.amount) if r.amount else None,
        }
        for r in rows
    ]
    return success_response(data)


@router.get("/etf/{code}/latest")
async def etf_latest(code: str, db: AsyncSession = Depends(get_db)):
    """ETF最新行情"""
    query = (
        select(EtfDaily)
        .where(EtfDaily.code == code)
        .order_by(EtfDaily.trade_date.desc())
        .limit(1)
    )
    result = await db.execute(query)
    row = result.scalar_one_or_none()
    if not row:
        return error_response(404, f"ETF {code} 无行情数据")

    return success_response({
        "trade_date": row.trade_date.isoformat(),
        "open": float(row.open) if row.open else None,
        "high": float(row.high) if row.high else None,
        "low": float(row.low) if row.low else None,
        "close": float(row.close) if row.close else None,
        "volume": row.volume,
        "amount": float(row.amount) if row.amount else None,
    })


@router.post("/data/sync")
async def data_sync(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """触发增量数据更新"""
    async def _do_sync():
        from backend.app.database import async_session
        async with async_session() as session:
            try:
                await incremental_update(session)
            except Exception as e:
                logger.error("增量更新失败: %s", e)

    background_tasks.add_task(_do_sync)
    return success_response({"message": "增量更新已触发"})


@router.get("/data/status")
async def data_status(db: AsyncSession = Depends(get_db)):
    """数据状态概览"""
    status = await get_data_status(db)
    return success_response(status)


@router.get("/data/calendar")
async def data_calendar(year: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """交易日历"""
    query = select(TradingCalendar).order_by(TradingCalendar.date)
    if year:
        from datetime import date as dt_date
        query = query.where(
            TradingCalendar.date >= dt_date(year, 1, 1),
            TradingCalendar.date <= dt_date(year, 12, 31),
        )

    result = await db.execute(query)
    rows = result.scalars().all()
    data = [{"date": r.date.isoformat(), "is_trading_day": r.is_trading_day} for r in rows]
    return success_response(data)


def _parse_date(date_str: str) -> date:
    """解析日期字符串，支持 YYYY-MM-DD 和 YYYYMMDD"""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {date_str}")
