"""
虚拟持仓跟踪模型 — VirtualAccount, VirtualTrade, VirtualPosition
"""

from sqlalchemy import (
    BigInteger, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, UniqueConstraint, func,
)

from backend.app.models import Base


class VirtualAccount(Base):
    """虚拟账户（每策略一个）"""
    __tablename__ = "virtual_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, unique=True)
    initial_capital = Column(Numeric(14, 2), nullable=False, default=200000)
    cash = Column(Numeric(14, 2), nullable=False)
    total_value = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class VirtualTrade(Base):
    """交易明细"""
    __tablename__ = "virtual_trades"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("virtual_accounts.id"), nullable=False)
    etf_code = Column(String(10), nullable=False)
    trade_date = Column(Date, nullable=False)
    direction = Column(String(4), nullable=False)  # BUY / SELL
    price = Column(Numeric(10, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    commission = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        Index("ix_virtual_trades_account_date", "account_id", "trade_date"),
    )


class VirtualPosition(Base):
    """当前持仓"""
    __tablename__ = "virtual_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("virtual_accounts.id"), nullable=False)
    etf_code = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    avg_cost = Column(Numeric(10, 4), nullable=False, default=0)
    market_value = Column(Numeric(14, 2), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("account_id", "etf_code", name="uq_virtual_position_account_etf"),
    )
