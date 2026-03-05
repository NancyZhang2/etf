"""
用户相关模型 — User, UserSubscription
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, func,
)

from backend.app.models import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True)
    wechat_openid = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())


class UserSubscription(Base):
    """用户订阅"""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_type = Column(String(20), nullable=False)  # strategy/etf/signal/research/weekly
    target_id = Column(Integer)
    channel = Column(String(20), nullable=False)  # wechat/email
    frequency = Column(String(20), default="daily")  # realtime/daily/weekly
    is_active = Column(Boolean, default=True)
