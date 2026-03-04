"""
Data模块路由 — 占位
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/etf/list")
async def etf_list(category: str = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/etf/list/categories")
async def etf_categories():
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/etf/{code}/info")
async def etf_info(code: str):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/etf/{code}/daily")
async def etf_daily(code: str, start_date: str = None, end_date: str = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/etf/{code}/latest")
async def etf_latest(code: str):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/etf/batch/daily")
async def etf_batch_daily(codes: str = "", start_date: str = None, end_date: str = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.post("/data/sync")
async def data_sync():
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/data/status")
async def data_status():
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/data/calendar")
async def data_calendar(year: int = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}
