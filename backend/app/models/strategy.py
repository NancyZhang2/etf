"""
策略相关模型 — StrategyCategory, Strategy, BacktestResult, TradingSignal, VirtualPortfolio
"""

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.models import Base


class StrategyCategory(Base):
    """策略分类"""
    __tablename__ = "strategy_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)


class Strategy(Base):
    """量化策略"""
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("strategy_categories.id"))
    name = Column(String(100), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    description = Column(Text)
    params = Column(JSONB)
    default_params = Column(JSONB)
    etf_pool = Column(JSONB)
    is_active = Column(Boolean, default=True)
    last_signal_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())


class BacktestResult(Base):
    """回测结果"""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    year = Column(Integer, default=0)  # 0表示全区间
    total_return = Column(Numeric(10, 4))
    annual_return = Column(Numeric(8, 4))
    max_drawdown = Column(Numeric(8, 4))
    annual_volatility = Column(Numeric(8, 4))
    sharpe_ratio = Column(Numeric(8, 4))
    sortino_ratio = Column(Numeric(8, 4))
    calmar_ratio = Column(Numeric(8, 4))
    win_rate = Column(Numeric(8, 4))
    profit_loss_ratio = Column(Numeric(8, 4))
    total_trades = Column(Integer)
    avg_holding_days = Column(Numeric(8, 2))
    turnover_rate = Column(Numeric(8, 4))
    benchmark_return = Column(Numeric(10, 4))
    excess_return = Column(Numeric(10, 4))
    params_snapshot = Column(JSONB)

    __table_args__ = (
        Index("ix_backtest_strategy_year", "strategy_id", "year"),
    )


class TradingSignal(Base):
    """每日交易信号"""
    __tablename__ = "trading_signals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    etf_code = Column(String(10), ForeignKey("etf_basic.code"), nullable=False)
    signal_date = Column(Date, nullable=False)
    signal = Column(String(10), nullable=False)  # BUY/SELL/HOLD
    target_weight = Column(Numeric(6, 4))
    reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_signal_strategy_date", "strategy_id", "signal_date"),
        Index("ix_signal_etf_date", "etf_code", "signal_date"),
    )


class VirtualPortfolio(Base):
    """虚拟持仓跟踪"""
    __tablename__ = "virtual_portfolios"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    etf_code = Column(String(10), nullable=False)
    position = Column(Numeric(10, 4))
    nav = Column(Numeric(12, 4))
    daily_return = Column(Numeric(8, 6))

    __table_args__ = (
        Index("ix_portfolio_strategy_date", "strategy_id", "trade_date"),
    )
