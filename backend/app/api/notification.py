"""
Notification模块路由 — 占位
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/notify/subscribe")
async def subscribe():
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.delete("/notify/subscribe/{subscription_id}")
async def unsubscribe(subscription_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.get("/notify/subscriptions")
async def subscriptions(user_id: int = None):
    return {"code": 501, "data": None, "message": "Not Implemented"}


@router.put("/notify/subscribe/{subscription_id}")
async def update_subscription(subscription_id: int):
    return {"code": 501, "data": None, "message": "Not Implemented"}
