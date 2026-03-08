"""
从东方财富爬取研报（策略/宏观 + 行业），存入 research_reports 表。
用法: python3 scripts/crawl_research.py [--pages 5] [--days 30]
"""
import asyncio
import logging
import os
import re
import sys
import time
from datetime import date, timedelta

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Referer": "https://data.eastmoney.com/report/"}
LIST_API = "https://reportapi.eastmoney.com/report/list"

# ETF代码和行业/资产关键词 — 用于匹配研报与ETF的关联
ETF_KEYWORDS = {
    "沪深300": "510300", "中证500": "510500", "创业板": "159915",
    "科创50": "588000", "上证50": "510050", "中证1000": "512100",
    "红利": "510880", "消费": "159928", "医药": "512010",
    "半导体": "512480", "芯片": "159995", "新能源": "516160",
    "光伏": "159857", "军工": "512660", "银行": "512800",
    "证券": "512880", "地产": "512200", "煤炭": "515220",
    "钢铁": "515210", "有色": "512400", "化工": "516220",
    "农业": "159825", "食品饮料": "515170", "家电": "159996",
    "汽车": "516110", "电力": "159611", "通信": "515880",
    "计算机": "512720", "传媒": "512980", "建材": "159745",
    "机械": "516960", "黄金": "518880", "原油": "159985",
    "豆粕": "159985", "恒生": "159920", "纳斯达克": "513100",
    "标普500": "513500", "日经": "513880", "德国": "513030",
    "国债": "511010", "信用债": "511260",
    "大类资产": None, "资产配置": None, "ETF": None,
    "指数基金": None, "行业轮动": None, "板块轮动": None,
}

# ETF代码正则
_ETF_CODE_PATTERN = re.compile(r'(?<!\d)(5[01]\d{4}|159\d{3})(?!\d)')


def extract_etf_code(title: str, content: str = "") -> str | None:
    """从标题和内容中提取ETF代码"""
    text = title + " " + content[:500]
    # 直接匹配ETF代码
    codes = _ETF_CODE_PATTERN.findall(text)
    if codes:
        return codes[0]
    # 关键词匹配
    for kw, code in ETF_KEYWORDS.items():
        if kw in text and code:
            return code
    return None


def clean_html(raw: str) -> str:
    """去除HTML标签"""
    text = re.sub(r'<[^>]+>', '', raw)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def fetch_detail_content(client: httpx.AsyncClient, info_code: str) -> str:
    """获取研报详情页正文"""
    # 策略/宏观研报
    url = f"https://data.eastmoney.com/report/zw_macresearch.jshtml?infocode={info_code}"
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            match = re.search(
                r"class=[\"']ctx-content[\"'].*?>(.*?)(?:</div>\s*</div>|<div\s+class=[\"']report)",
                resp.text, re.S
            )
            if match:
                return clean_html(match.group(1))[:5000]
    except Exception as e:
        logger.debug("获取详情失败 %s: %s", info_code, e)
    return ""


async def crawl_reports(max_pages: int = 5, days: int = 30) -> int:
    """爬取研报列表 + 详情"""
    from backend.app.database import async_session
    from backend.app.models.research import ResearchReport
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import select

    # 预加载已有的ETF代码，用于外键校验
    async with async_session() as db:
        from backend.app.models.etf import EtfBasic
        result = await db.execute(select(EtfBasic.code))
        valid_codes = set(r[0] for r in result.all())
    logger.info("数据库中有 %d 个有效ETF代码", len(valid_codes))

    begin_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()
    inserted = 0
    skipped_fk = 0

    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        # 拉两类研报：qType=1(行业), qType=2(策略/宏观)
        for q_type, q_label in [(2, "策略/宏观"), (1, "行业")]:
            logger.info("── 开始爬取 %s 研报 (qType=%d) ──", q_label, q_type)

            for page in range(1, max_pages + 1):
                params = {
                    "industryCode": "*", "pageSize": 50, "industry": "*",
                    "rating": "*", "ratingChange": "*",
                    "beginTime": begin_date, "endTime": end_date,
                    "pageNo": page, "qType": q_type,
                    "p": page, "pageNum": page,
                }

                try:
                    resp = await client.get(LIST_API, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("第%d页请求失败: %s", page, e)
                    continue

                items = data.get("data", [])
                if not items:
                    logger.info("第%d页无数据，停止", page)
                    break

                page_inserted = 0
                for item in items:
                    title = item.get("title", "")
                    source = item.get("orgSName", "东方财富")
                    pub_date_str = (item.get("publishDate") or "")[:10]
                    info_code = item.get("infoCode", "")

                    try:
                        report_date = date.fromisoformat(pub_date_str)
                    except (ValueError, TypeError):
                        report_date = date.today()

                    # 获取正文
                    content = ""
                    if info_code:
                        content = await fetch_detail_content(client, info_code)
                        time.sleep(0.1)  # 控制频率

                    if not content:
                        content = title  # fallback

                    # 提取ETF代码
                    etf_code = extract_etf_code(title, content)
                    # 外键校验
                    if etf_code and etf_code not in valid_codes:
                        skipped_fk += 1
                        etf_code = None

                    async with async_session() as db:
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
                            page_inserted += 1
                            inserted += 1
                        await db.commit()

                logger.info("[%s] 第%d页: %d条, 新增%d条", q_label, page, len(items), page_inserted)

    logger.info("═══ 爬取完成: 新增 %d 篇研报 (跳过FK不匹配 %d 篇) ═══", inserted, skipped_fk)
    return inserted


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=5, help="每类研报爬取页数")
    parser.add_argument("--days", type=int, default=30, help="回溯天数")
    args = parser.parse_args()

    count = await crawl_reports(max_pages=args.pages, days=args.days)
    logger.info("总计入库 %d 篇", count)


if __name__ == "__main__":
    asyncio.run(main())
