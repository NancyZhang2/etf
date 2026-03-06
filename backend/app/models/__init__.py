"""
SQLAlchemy 模型基类 + 导入所有模型
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# 导入所有模型，确保 create_all 能发现它们
from backend.app.models.etf import EtfBasic, EtfDaily, TradingCalendar  # noqa: E402, F401
from backend.app.models.strategy import (  # noqa: E402, F401
    StrategyCategory, Strategy, BacktestResult, TradingSignal, VirtualPortfolio,
)
from backend.app.models.virtual_portfolio import (  # noqa: E402, F401
    VirtualAccount, VirtualTrade, VirtualPosition,
)
from backend.app.models.research import ResearchReport, ResearchFramework  # noqa: E402, F401
from backend.app.models.user import User, UserSubscription  # noqa: E402, F401
