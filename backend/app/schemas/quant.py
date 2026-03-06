"""
Quant模块 Pydantic Schemas
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class StrategyOut(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    category_id: Optional[int] = None
    strategy_type: str
    description: Optional[str] = None
    is_active: bool = True
    params: Optional[Dict[str, Any]] = None
    default_params: Optional[Dict[str, Any]] = None
    etf_pool: Optional[List[str]] = None

    model_config = {"from_attributes": True}


class BacktestResultOut(BaseModel):
    year: int = 0
    total_return: Optional[Decimal] = None
    annual_return: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    annual_volatility: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    sortino_ratio: Optional[Decimal] = None
    calmar_ratio: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    profit_loss_ratio: Optional[Decimal] = None
    total_trades: Optional[int] = None
    avg_holding_days: Optional[Decimal] = None
    turnover_rate: Optional[Decimal] = None
    benchmark_return: Optional[Decimal] = None
    excess_return: Optional[Decimal] = None
    params_snapshot: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class SignalOut(BaseModel):
    strategy_name: Optional[str] = None
    strategy_id: Optional[int] = None
    etf_code: str
    etf_name: Optional[str] = None
    signal: str
    target_weight: Optional[Decimal] = None
    reason: Optional[str] = None
    signal_date: date

    model_config = {"from_attributes": True}


class BacktestRequest(BaseModel):
    params: Dict[str, Any]


class OptimizeRequest(BaseModel):
    param_name: str
    param_range: List[Any]
    metric: str = "sharpe_ratio"


class PortfolioOut(BaseModel):
    trade_date: date
    etf_code: str
    position: Optional[Decimal] = None
    nav: Optional[Decimal] = None
    daily_return: Optional[Decimal] = None

    model_config = {"from_attributes": True}


# ---------- 虚拟持仓跟踪 Schemas ----------

class VirtualStartRequest(BaseModel):
    initial_capital: Decimal = Decimal("200000")


class VirtualPositionOut(BaseModel):
    etf_code: str
    quantity: int
    avg_cost: float
    market_value: float
    profit_pct: float


class VirtualSummaryOut(BaseModel):
    initial_capital: float
    cash: float
    total_value: float
    total_return_pct: float
    positions: List[VirtualPositionOut]
    start_date: Optional[str] = None


class VirtualTradeOut(BaseModel):
    id: int
    etf_code: str
    trade_date: str
    direction: str
    price: float
    quantity: int
    amount: float
    commission: float


class VirtualNavOut(BaseModel):
    trade_date: str
    nav: float
    daily_return: float
