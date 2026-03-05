"""
ETF量化投研平台 — FastAPI 入口
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.api import data, quant, research, notification
from backend.app.database import engine
from backend.app.models import Base
from backend.app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时建表，关闭时清理连接池"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表已创建/确认")
    yield
    await engine.dispose()


app = FastAPI(
    title="ETF量化投研平台",
    description="全A股场内ETF量化投研平台 API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理异常: %s", exc)
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
