"""
ETF量化投研平台 — FastAPI 入口
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api import data, quant, research, notification

app = FastAPI(
    title="ETF量化投研平台",
    description="全A股场内ETF量化投研平台 API",
    version="0.1.0",
)


# ---------- 统一响应格式 ----------

def success_response(data=None, message: str = "ok"):
    return {"code": 0, "data": data, "message": message}


def error_response(code: int, message: str):
    return {"code": code, "data": None, "message": message}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(500, str(exc)),
    )


# ---------- 挂载模块路由 ----------

app.include_router(data.router, prefix="/api/v1", tags=["Data"])
app.include_router(quant.router, prefix="/api/v1", tags=["Quant"])
app.include_router(research.router, prefix="/api/v1", tags=["Research"])
app.include_router(notification.router, prefix="/api/v1", tags=["Notification"])


@app.get("/")
async def root():
    return success_response({"status": "running", "version": "0.1.0"})
