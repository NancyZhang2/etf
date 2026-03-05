"""
Research模块 Pydantic Schemas
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ReportSummaryOut(BaseModel):
    id: int
    title: str
    source: Optional[str] = None
    report_date: Optional[date] = None
    summary: Optional[str] = None
    etf_code: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportDetailOut(BaseModel):
    id: int
    title: str
    source: Optional[str] = None
    content: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    report_date: Optional[date] = None
    etf_code: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    total: int
    items: List[ReportSummaryOut]


class FrameworkOut(BaseModel):
    etf_code: str
    week_date: Optional[date] = None
    fundamental_score: Optional[Decimal] = None
    technical_score: Optional[Decimal] = None
    sentiment_score: Optional[Decimal] = None
    overall_score: Optional[Decimal] = None
    framework_data: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class SentimentOut(BaseModel):
    etf_code: str
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    overall_sentiment: str = "neutral"


class MacroViewOut(BaseModel):
    economy: str = "stable"
    liquidity: str = "neutral"
    policy: str = "neutral"
    key_points: List[str] = []
    risk_factors: List[str] = []
    updated_at: Optional[datetime] = None
