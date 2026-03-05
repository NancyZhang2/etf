"""
研报样本数据生成 — 生成研报、分析结果和投资框架
与 sample_data.py 配合使用，关联到已有25只ETF
"""

import logging
import random
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.research import ResearchFramework, ResearchReport
from backend.app.services.research import (
    generate_mock_analysis,
    generate_mock_reports,
    _sentiment_to_score,
)
from backend.app.services.sample_data import SAMPLE_ETFS

logger = logging.getLogger(__name__)


def _build_etf_list() -> List[Dict[str, str]]:
    """从 SAMPLE_ETFS 构建 etf_list"""
    return [
        {"code": code, "name": name, "category": cat}
        for code, name, cat, *_ in SAMPLE_ETFS
    ]


async def generate_sample_research(db: AsyncSession) -> Dict[str, int]:
    """生成研报样本数据，返回统计"""
    stats = {"reports": 0, "frameworks": 0}
    etf_list = _build_etf_list()

    # 1. 生成研报 + 分析结果
    reports = generate_mock_reports(etf_list, count=40, seed=42)

    for r in reports:
        stmt = pg_insert(ResearchReport).values(
            title=r["title"],
            source=r["source"],
            content=r["content"],
            etf_code=r["etf_code"],
            report_date=r["report_date"],
            analysis=r["analysis"],
        ).on_conflict_do_nothing(
            constraint="uq_report_title_source_date"
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            stats["reports"] += 1

    await db.commit()
    logger.info("写入 %d 条研报", stats["reports"])

    # 2. 生成投资框架
    rng = random.Random(42)
    week_date = date.today() - timedelta(days=date.today().weekday())  # 本周一

    # 按ETF分组
    etf_reports: Dict[str, List[Dict]] = {}
    for r in reports:
        code = r["etf_code"]
        if code not in etf_reports:
            etf_reports[code] = []
        etf_reports[code].append(r)

    for code, code_reports in etf_reports.items():
        sentiments = []
        key_points_all = []
        risk_factors_all = []
        report_ids = []

        for r in code_reports:
            analysis = r.get("analysis", {})
            rel = analysis.get("etf_relevance", {})
            sentiments.append(rel.get("sentiment", "neutral"))
            key_points_all.extend(analysis.get("key_points", []))
            risk_factors_all.extend(analysis.get("risk_factors", []))

        sentiment_score = _sentiment_to_score(sentiments)
        fundamental_score = round(rng.uniform(4.0, 8.5), 2)
        technical_score = round(rng.uniform(4.0, 8.5), 2)
        overall_score = round(
            fundamental_score * 0.3 + technical_score * 0.3 + sentiment_score * 0.4, 2
        )

        framework_data = {
            "report_count": len(code_reports),
            "sentiment_distribution": dict(Counter(sentiments)),
            "economy_consensus": "stable",
            "key_points": list(set(key_points_all))[:8],
            "risk_factors": list(set(risk_factors_all))[:6],
        }

        stmt = pg_insert(ResearchFramework).values(
            etf_code=code,
            week_date=week_date,
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            overall_score=overall_score,
            framework_data=framework_data,
            source_report_ids=report_ids or None,
        ).on_conflict_do_nothing()
        result = await db.execute(stmt)
        if result.rowcount > 0:
            stats["frameworks"] += 1

    await db.commit()
    logger.info("写入 %d 条投资框架", stats["frameworks"])
    logger.info("研报样本数据生成完成: %s", stats)
    return stats
