"""
统一响应 Schema
"""

from typing import Any, Optional

from pydantic import BaseModel


class APIResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 0
    data: Optional[Any] = None
    message: str = "ok"
