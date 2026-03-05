"""
ETF 数据模型 — EtfBasic, EtfDaily, TradingCalendar
"""

from sqlalchemy import (
    Boolean, BigInteger, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, UniqueConstraint, func,
)

from backend.app.models import Base


class EtfBasic(Base):
    """ETF基本信息"""
    __tablename__ = "etf_basic"

    code = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))  # 宽基/行业/主题/商品/债券/货币/跨境
    exchange = Column(String(10))  # SH/SZ
    list_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class EtfDaily(Base):
    """ETF日行情"""
    __tablename__ = "etf_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), ForeignKey("etf_basic.code"), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric(10, 4))
    high = Column(Numeric(10, 4))
    low = Column(Numeric(10, 4))
    close = Column(Numeric(10, 4))
    volume = Column(BigInteger)
    amount = Column(Numeric(20, 2))
    pre_close = Column(Numeric(10, 4))

    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_etf_daily_code_date"),
        Index("ix_etf_daily_code", "code"),
        Index("ix_etf_daily_trade_date", "trade_date"),
        Index("ix_etf_daily_code_date", "code", "trade_date"),
    )


class TradingCalendar(Base):
    """交易日历"""
    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    is_trading_day = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_trading_calendar_date", "date"),
    )
