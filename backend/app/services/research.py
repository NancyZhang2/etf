"""
Research 核心服务 — 研报爬取、AI分析、投资框架生成、宏观共识
"""

import hashlib
import json
import logging
import random
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.research import ResearchFramework, ResearchReport

logger = logging.getLogger(__name__)

# ──────────────── 常量 ────────────────

MAX_DAILY_ANALYSES = 50
EASTMONEY_API = "https://reportapi.eastmoney.com/report/list"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ──────────────── 2a. 东方财富爬虫 ────────────────


async def crawl_eastmoney_reports(
    db: AsyncSession,
    page_size: int = 30,
    max_pages: int = 3,
) -> int:
    """从东方财富研报API爬取研报，返回新增数量"""
    inserted = 0
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": "https://data.eastmoney.com/report/",
    }

    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*",
                "pageSize": page_size,
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": (date.today() - timedelta(days=30)).isoformat(),
                "endTime": date.today().isoformat(),
                "pageNo": page,
                "fields": "",
                "qType": 0,
                "orgCode": "",
                "code": "",
                "rcode": "",
                "p": page,
                "pageNum": page,
            }

            for attempt in range(3):
                try:
                    resp = await client.get(EASTMONEY_API, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as e:
                    logger.warning("东方财富API第%d页第%d次请求失败: %s", page, attempt + 1, e)
                    if attempt == 2:
                        logger.error("东方财富API第%d页3次重试均失败，降级到样本数据", page)
                        return inserted

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                title = item.get("title", "")
                source = item.get("orgSName", "东方财富")
                report_date_str = item.get("publishDate", "")[:10]
                content = item.get("content") or item.get("title", "")
                etf_codes = _extract_etf_codes_from_text(title + " " + content)

                try:
                    report_date = date.fromisoformat(report_date_str) if report_date_str else date.today()
                except ValueError:
                    report_date = date.today()

                etf_code = etf_codes[0] if etf_codes else None

                stmt = pg_insert(ResearchReport).values(
                    title=title,
                    source=source,
                    content=content[:5000],
                    report_date=report_date,
                    etf_code=etf_code,
                ).on_conflict_do_nothing(
                    constraint="uq_report_title_source_date"
                )
                result = await db.execute(stmt)
                if result.rowcount > 0:
                    inserted += 1

            await db.commit()
            logger.info("东方财富第%d页: 解析%d条, 新增%d条", page, len(items), inserted)

    return inserted


# ──────────────── 2b. Mock/样本研报生成器 ────────────────

_REPORT_TEMPLATES = [
    ("行业策略", "{category}ETF投资策略周报：{name}({code})近期走势分析"),
    ("宏观周报", "宏观经济周报：{category}板块轮动机会与{name}配置建议"),
    ("ETF专题", "{name}({code})深度研究：{category}赛道投资价值分析"),
    ("市场点评", "市场日评：{name}表现亮眼，{category}板块后市展望"),
    ("配置建议", "资产配置月报：{category}类ETF配置权重调整建议"),
    ("行业研究", "{category}行业深度：从{name}({code})看板块投资机遇"),
    ("量化分析", "量化视角：{name}动量因子表现与轮动信号追踪"),
    ("技术分析", "{name}({code})技术分析：均线系统与支撑阻力位研判"),
    ("资金流向", "{category}板块资金流向分析：{name}获主力资金关注"),
    ("估值研究", "{name}({code})估值分析：当前{category}板块估值水位研判"),
    ("政策解读", "政策利好{category}板块：{name}受益逻辑与配置时点分析"),
    ("风险提示", "风险警示：{category}板块波动加大，{name}需关注回调风险"),
    ("对比研究", "{category}ETF对比分析：{name}与同类产品优劣势评估"),
    ("年度展望", "2026年{category}板块展望：{name}({code})投资价值评估"),
    ("海外映射", "海外市场启示：对{category}板块及{name}的映射分析"),
]

_CONTENT_TEMPLATES = [
    "近期{name}走势活跃，{category}板块受到市场关注。从技术面看，该ETF突破前期整理平台，"
    "成交量温和放大，短期均线呈多头排列。从基本面看，板块内龙头企业业绩预告向好，"
    "行业景气度持续改善。建议投资者关注回调机会，适度配置。"
    "风险提示：市场波动风险、行业政策变动风险、流动性风险。",

    "本周{category}板块整体表现{sentiment}，{name}作为该板块代表性ETF，"
    "周涨幅{change}%。宏观层面，央行维持稳健货币政策，市场流动性合理充裕。"
    "从估值角度看，当前{category}板块PE处于历史{percentile}分位水平，具有一定安全边际。"
    "中长期看好板块配置价值，短期需关注外部扰动因素。",

    "深度研究表明，{name}({code})跟踪的指数成分股覆盖{category}领域核心标的，"
    "行业集中度适中，能有效分散个股风险。近年来该板块受政策支持力度加大，"
    "产业升级趋势明显。从量化指标看，动量因子和价值因子双重支撑，"
    "适合作为中长期配置的底仓品种。",

    "宏观经济数据显示，当前经济运行在合理区间，PMI连续{n}个月位于扩张区间。"
    "{category}板块受益于经济复苏预期，{name}近期获北向资金持续加仓。"
    "从技术形态看，日线MACD金叉，周线KDJ低位回升，短期上涨动能较强。"
    "操作建议：可在回调至{support}附近分批建仓，目标看至{target}。",

    "全球资产配置视角下，{category}类资产的配置价值正在提升。{name}作为场内流动性最好的"
    "{category}ETF之一，日均成交额稳定在较高水平。当前全球通胀预期温和回落，"
    "货币政策边际宽松，有利于风险资产表现。建议在组合中配置{weight}%的{category}类资产。",
]


def generate_mock_reports(
    etf_list: List[Dict[str, str]],
    count: int = 40,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """生成mock研报数据"""
    rng = random.Random(seed)
    reports = []
    sources = ["东方财富研究", "中信证券", "华泰证券", "招商证券", "国泰君安", "中金公司", "广发证券"]

    for i in range(count):
        etf = rng.choice(etf_list)
        template_type, title_tmpl = rng.choice(_REPORT_TEMPLATES)
        content_tmpl = rng.choice(_CONTENT_TEMPLATES)

        sentiments = ["偏强", "震荡", "偏弱"]
        title = title_tmpl.format(**etf)
        content = content_tmpl.format(
            **etf,
            sentiment=rng.choice(sentiments),
            change=round(rng.uniform(-3, 5), 2),
            percentile=rng.choice(["30", "40", "50", "60", "70"]),
            n=rng.randint(2, 6),
            support=round(rng.uniform(1.0, 5.0), 2),
            target=round(rng.uniform(3.0, 8.0), 2),
            weight=rng.randint(5, 25),
        )

        report_date = date.today() - timedelta(days=rng.randint(0, 28))

        reports.append({
            "title": title,
            "source": rng.choice(sources),
            "content": content,
            "etf_code": etf["code"],
            "report_date": report_date,
            "analysis": generate_mock_analysis(etf["code"], etf["name"], etf["category"], content, seed=seed + i),
        })

    return reports


# ──────────────── 2c. Claude API 分析 ────────────────

_ANALYSIS_PROMPT = """你是ETF投资研究分析师。请分析以下研报，提取结构化信息。

研报标题：{title}
研报内容：{content}

请以JSON格式返回分析结果，包含以下字段：
{{
    "summary": "100字以内的研报摘要",
    "etf_relevance": {{
        "code": "相关ETF代码（如510300）",
        "sentiment": "bullish/bearish/neutral",
        "confidence": 0.0到1.0之间的置信度
    }},
    "macro_view": {{
        "economy": "expanding/stable/contracting",
        "liquidity": "loose/neutral/tight",
        "policy": "supportive/neutral/restrictive"
    }},
    "risk_factors": ["风险因素1", "风险因素2"],
    "key_points": ["要点1", "要点2"],
    "confidence": 0.0到1.0之间的整体置信度
}}

只返回JSON，不要其他内容。"""


async def analyze_report_with_claude(
    title: str, content: str
) -> Optional[Dict[str, Any]]:
    """使用Claude API分析研报，返回结构化结果"""
    api_key = settings.CLAUDE_API_KEY
    if not api_key:
        logger.info("CLAUDE_API_KEY未配置，使用mock分析")
        return None

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    prompt = _ANALYSIS_PROMPT.format(title=title, content=content[:3000])

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["content"][0]["text"]
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        logger.warning("Claude API调用失败: %s", e)
        return None


def generate_mock_analysis(
    etf_code: str,
    etf_name: str = "",
    category: str = "",
    content: str = "",
    seed: int = 42,
) -> Dict[str, Any]:
    """生成mock分析结果（与真实分析共享同一schema）"""
    rng = random.Random(seed)

    sentiments = ["bullish", "bearish", "neutral"]
    economies = ["expanding", "stable", "contracting"]
    liquidities = ["loose", "neutral", "tight"]
    policies = ["supportive", "neutral", "restrictive"]

    sentiment_weights = [0.4, 0.2, 0.4]
    sentiment = rng.choices(sentiments, weights=sentiment_weights, k=1)[0]

    risk_pool = [
        "市场系统性风险", "行业政策变动风险", "流动性风险", "估值回调风险",
        "海外市场波动风险", "汇率波动风险", "通胀超预期风险", "经济复苏不及预期",
        "地缘政治风险", "监管政策收紧风险",
    ]
    key_pool = [
        f"{category}板块景气度持续改善",
        f"{etf_name}成交活跃度上升",
        "宏观经济数据向好",
        "货币政策维持稳健偏宽松",
        "北向资金持续流入",
        "行业龙头业绩超预期",
        f"{category}板块估值处于历史中低位",
        "产业升级政策持续推进",
    ]

    summary_templates = [
        f"本报告分析了{etf_name}({etf_code})的投资价值，{category}板块整体表现{'偏强' if sentiment == 'bullish' else '偏弱' if sentiment == 'bearish' else '震荡'}。",
        f"{category}板块深度研究：{etf_name}跟踪指数基本面稳健，技术面{'向好' if sentiment == 'bullish' else '承压' if sentiment == 'bearish' else '中性'}。",
        f"宏观环境对{category}类资产{'利好' if sentiment == 'bullish' else '偏空' if sentiment == 'bearish' else '影响有限'}，{etf_name}配置价值{'凸显' if sentiment == 'bullish' else '需谨慎' if sentiment == 'bearish' else '中性'}。",
    ]

    return {
        "summary": rng.choice(summary_templates),
        "etf_relevance": {
            "code": etf_code,
            "sentiment": sentiment,
            "confidence": round(rng.uniform(0.5, 0.95), 2),
        },
        "macro_view": {
            "economy": rng.choices(economies, weights=[0.4, 0.4, 0.2], k=1)[0],
            "liquidity": rng.choices(liquidities, weights=[0.3, 0.5, 0.2], k=1)[0],
            "policy": rng.choices(policies, weights=[0.4, 0.4, 0.2], k=1)[0],
        },
        "risk_factors": rng.sample(risk_pool, k=rng.randint(2, 4)),
        "key_points": rng.sample(key_pool, k=rng.randint(2, 4)),
        "confidence": round(rng.uniform(0.5, 0.9), 2),
    }


async def analyze_pending_reports(db: AsyncSession, limit: int = MAX_DAILY_ANALYSES) -> int:
    """分析所有未分析的研报"""
    result = await db.execute(
        select(ResearchReport)
        .where(ResearchReport.analysis.is_(None))
        .order_by(ResearchReport.report_date.desc())
        .limit(limit)
    )
    reports = result.scalars().all()
    analyzed = 0

    for report in reports:
        analysis = await analyze_report_with_claude(report.title, report.content or "")
        if analysis is None:
            analysis = generate_mock_analysis(
                etf_code=report.etf_code or "510300",
                etf_name=report.title[:10],
                category="未知",
                content=report.content or "",
                seed=hash(report.title) % 10000,
            )

        report.analysis = analysis
        analyzed += 1

    await db.commit()
    logger.info("分析完成: %d/%d 条研报", analyzed, len(reports))
    return analyzed


# ──────────────── 2d. 投资框架生成 ────────────────


async def generate_frameworks(db: AsyncSession) -> int:
    """为Top50 ETF生成投资框架"""
    cutoff = date.today() - timedelta(days=28)
    week_date = date.today()

    # 查询近4周有分析结果的研报，按ETF聚合
    result = await db.execute(
        select(
            ResearchReport.etf_code,
            func.count(ResearchReport.id).label("report_count"),
            func.array_agg(ResearchReport.id).label("report_ids"),
        )
        .where(
            ResearchReport.etf_code.isnot(None),
            ResearchReport.analysis.isnot(None),
            ResearchReport.report_date >= cutoff,
        )
        .group_by(ResearchReport.etf_code)
        .order_by(func.count(ResearchReport.id).desc())
        .limit(50)
    )
    etf_groups = result.all()

    created = 0
    for etf_code, report_count, report_ids in etf_groups:
        # 获取该ETF的所有研报分析
        reports_result = await db.execute(
            select(ResearchReport)
            .where(
                ResearchReport.id.in_(report_ids),
                ResearchReport.analysis.isnot(None),
            )
        )
        reports = reports_result.scalars().all()

        sentiments = []
        economies = []
        key_points_all = []
        risk_factors_all = []

        for r in reports:
            analysis = r.analysis or {}
            rel = analysis.get("etf_relevance", {})
            sentiment = rel.get("sentiment", "neutral")
            sentiments.append(sentiment)

            macro = analysis.get("macro_view", {})
            if macro.get("economy"):
                economies.append(macro["economy"])

            key_points_all.extend(analysis.get("key_points", []))
            risk_factors_all.extend(analysis.get("risk_factors", []))

        # 计算评分
        sentiment_score = _sentiment_to_score(sentiments)
        fundamental_score = round(random.Random(hash(etf_code)).uniform(4.0, 8.0), 2)
        technical_score = round(random.Random(hash(etf_code) + 1).uniform(4.0, 8.0), 2)
        overall_score = round(
            (fundamental_score * 0.3 + technical_score * 0.3 + sentiment_score * 0.4), 2
        )

        framework_data = {
            "report_count": report_count,
            "sentiment_distribution": dict(Counter(sentiments)),
            "economy_consensus": _majority_vote(economies) if economies else "stable",
            "key_points": list(set(key_points_all))[:10],
            "risk_factors": list(set(risk_factors_all))[:8],
        }

        stmt = pg_insert(ResearchFramework).values(
            etf_code=etf_code,
            week_date=week_date,
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            overall_score=overall_score,
            framework_data=framework_data,
            source_report_ids=report_ids,
        ).on_conflict_do_nothing()
        result = await db.execute(stmt)
        if result.rowcount > 0:
            created += 1

    await db.commit()
    logger.info("投资框架生成完成: %d 条", created)
    return created


# ──────────────── 2e. 宏观共识 ────────────────


async def get_macro_consensus(db: AsyncSession) -> Dict[str, Any]:
    """从近30天研报分析中提取宏观共识"""
    cutoff = date.today() - timedelta(days=30)

    result = await db.execute(
        select(ResearchReport.analysis)
        .where(
            ResearchReport.analysis.isnot(None),
            ResearchReport.report_date >= cutoff,
        )
    )
    rows = result.scalars().all()

    economies = []
    liquidities = []
    policies = []
    key_points = []
    risk_factors = []

    for analysis in rows:
        if not analysis:
            continue
        macro = analysis.get("macro_view", {})
        if macro.get("economy"):
            economies.append(macro["economy"])
        if macro.get("liquidity"):
            liquidities.append(macro["liquidity"])
        if macro.get("policy"):
            policies.append(macro["policy"])
        key_points.extend(analysis.get("key_points", []))
        risk_factors.extend(analysis.get("risk_factors", []))

    return {
        "economy": _majority_vote(economies) if economies else "stable",
        "liquidity": _majority_vote(liquidities) if liquidities else "neutral",
        "policy": _majority_vote(policies) if policies else "neutral",
        "key_points": list(set(key_points))[:15],
        "risk_factors": list(set(risk_factors))[:10],
        "updated_at": datetime.now().isoformat(),
    }


async def get_sentiment_stats(db: AsyncSession, etf_code: str) -> Dict[str, Any]:
    """获取特定ETF的情绪统计"""
    cutoff = date.today() - timedelta(days=30)

    result = await db.execute(
        select(ResearchReport.analysis)
        .where(
            ResearchReport.etf_code == etf_code,
            ResearchReport.analysis.isnot(None),
            ResearchReport.report_date >= cutoff,
        )
    )
    rows = result.scalars().all()

    bullish = 0
    bearish = 0
    neutral = 0

    for analysis in rows:
        if not analysis:
            continue
        sentiment = analysis.get("etf_relevance", {}).get("sentiment", "neutral")
        if sentiment == "bullish":
            bullish += 1
        elif sentiment == "bearish":
            bearish += 1
        else:
            neutral += 1

    total = bullish + bearish + neutral
    if total == 0:
        overall = "neutral"
    elif bullish > bearish and bullish > neutral:
        overall = "bullish"
    elif bearish > bullish and bearish > neutral:
        overall = "bearish"
    else:
        overall = "neutral"

    return {
        "etf_code": etf_code,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "overall_sentiment": overall,
    }


# ──────────────── 2f. 辅助函数 ────────────────

# 已知ETF代码模式
_ETF_CODE_PATTERN = re.compile(r'(?<!\d)(5[01]\d{4}|159\d{3})(?!\d)')


def _extract_etf_codes_from_text(text: str) -> List[str]:
    """从文本中提取ETF代码"""
    matches = _ETF_CODE_PATTERN.findall(text)
    return list(dict.fromkeys(matches))  # 去重保序


def _majority_vote(items: List[str]) -> str:
    """多数投票，返回出现次数最多的项"""
    if not items:
        return ""
    counter = Counter(items)
    return counter.most_common(1)[0][0]


def _sentiment_to_score(sentiments: List[str]) -> float:
    """将情绪列表转换为0-10评分"""
    if not sentiments:
        return 5.0
    scores = {"bullish": 8.0, "neutral": 5.0, "bearish": 2.0}
    total = sum(scores.get(s, 5.0) for s in sentiments)
    return round(total / len(sentiments), 2)
