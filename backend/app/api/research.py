"""
Research模块路由 — 占位
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/research/reports")
async def research_reports(etf_code: str = None, page: int = 1, page_size: int = 20):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/research/reports/{report_id}")
async def research_report_detail(report_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/research/{etf_code}/framework")
async def research_framework(etf_code: str):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/research/{etf_code}/sentiment")
async def research_sentiment(etf_code: str):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/research/macro")
async def research_macro():
    return {"code": 501, "data": None, "message": "Not Implemented"}
