"""
Quant模块路由 — 占位
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/strategies")
async def strategy_list(category_id: int = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/strategies/{strategy_id}")
async def strategy_detail(strategy_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/strategies/{strategy_id}/backtest")
async def strategy_backtest(strategy_id: int, year: int = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.post("/strategies/{strategy_id}/backtest")
async def strategy_backtest_custom(strategy_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/strategies/{strategy_id}/backtest/yearly")
async def strategy_backtest_yearly(strategy_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/strategies/{strategy_id}/portfolio")
async def strategy_portfolio(strategy_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/signals/latest")
async def signals_latest(strategy_id: int = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/signals/history")
async def signals_history(
    strategy_id: int = None, etf_code: str = None,
    start_date: str = None, end_date: str = None,
):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/signals/calendar")
async def signals_calendar(month: str = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.post("/strategies/{strategy_id}/optimize")
async def strategy_optimize(strategy_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}
