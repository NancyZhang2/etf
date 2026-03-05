"""
Data模块 Pydantic Schemas
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class EtfBasicOut(BaseModel):
    code: str
    name: str
    category: Optional[str] = None
    exchange: Optional[str] = None
    list_date: Optional[date] = None

    model_config = {"from_attributes": True}


class EtfDailyOut(BaseModel):
    trade_date: date
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None
    amount: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class CategoryCount(BaseModel):
    category: str
    count: int


class DataStatus(BaseModel):
    last_sync: Optional[datetime] = None
    record_count: int = 0
    etf_count: int = 0
    status: str = "unknown"


class CalendarDay(BaseModel):
    date: date
    is_trading_day: bool

    model_config = {"from_attributes": True}
