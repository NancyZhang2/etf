"""
统一响应格式工具函数
"""

from typing import Any


def success_response(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "data": data, "message": message}


def error_response(code: int, message: str) -> dict:
    return {"code": code, "data": None, "message": message}
