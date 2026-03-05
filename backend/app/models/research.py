"""
研报相关模型 — ResearchReport, ResearchFramework
"""

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from backend.app.models import Base


class ResearchReport(Base):
    """研报与分析"""
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    etf_code = Column(String(10), ForeignKey("etf_basic.code"))
    source = Column(String(100))
    title = Column(String(200), nullable=False)
    content = Column(Text)
    analysis = Column(JSONB)  # Claude API结构化分析结果
    report_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("title", "source", "report_date", name="uq_report_title_source_date"),
        Index("ix_report_etf_code", "etf_code"),
    )


class ResearchFramework(Base):
    """ETF投资框架"""
    __tablename__ = "research_frameworks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    etf_code = Column(String(10), ForeignKey("etf_basic.code"), nullable=False)
    week_date = Column(Date, nullable=False)
    fundamental_score = Column(Numeric(4, 2))
    technical_score = Column(Numeric(4, 2))
    sentiment_score = Column(Numeric(4, 2))
    overall_score = Column(Numeric(4, 2))
    framework_data = Column(JSONB)
    source_report_ids = Column(ARRAY(Integer))

    __table_args__ = (
        Index("ix_framework_etf_week", "etf_code", "week_date"),
    )
