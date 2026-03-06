"""
ETF 数据服务 — tushare 数据源
拉取全量ETF列表和日线行情，存入 PostgreSQL。
"""

import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import tushare as ts
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.etf import EtfBasic, EtfDaily

logger = logging.getLogger(__name__)

TUSHARE_TOKEN = "fef20f81e2511af987005aed159cfbdd1f094620593670b136ecf859"
FIELDS_DAILY = "ts_code,trade_date,pre_close,open,high,low,close,change,pct_chg,vol,amount"
PAGE_LIMIT = 2000  # tushare 单次最大返回行数
REQUEST_INTERVAL = 0.15  # 两次请求最小间隔（秒）

# ETF 分类关键词映射（与 etf_data.py 保持一致）
CATEGORY_KEYWORDS = {
    "货币": ["货币", "现金", "理财"],
    "债券": ["国债", "企债", "信用债", "可转债", "利率债", "城投债", "债券", "债"],
    "商品": ["黄金", "白银", "原油", "能源化工", "有色金属", "豆粕", "商品", "铜"],
    "跨境": ["恒生", "港股", "纳斯达克", "纳指", "标普", "日经", "德国",
             "法国", "东南亚", "中概", "港股通", "H股", "美国",
             "亚太", "印度", "韩国", "越南", "沙特"],
    "行业": ["银行", "证券", "保险", "金融", "地产", "房地产",
             "医药", "医疗", "生物", "中药", "创新药",
             "消费", "食品", "饮料", "白酒", "家电",
             "电子", "芯片", "半导体", "通信", "5G", "计算机", "软件",
             "新能源", "光伏", "锂电", "电力", "煤炭", "钢铁", "有色",
             "军工", "国防", "航天", "汽车", "机械", "建材", "化工",
             "农业", "畜牧", "传媒", "游戏", "环保", "稀土"],
    "主题": ["ESG", "碳中和", "一带一路", "国企改革", "专精特新",
             "人工智能", "AI", "机器人", "数字经济", "云计算", "大数据",
             "区块链", "元宇宙", "网络安全", "养老", "北交所", "REITs",
             "央企", "红利", "科技"],
}


def _classify_etf(name: str) -> str:
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return cat
    return "宽基"


def _get_pro() -> ts.pro_api:
    return ts.pro_api(TUSHARE_TOKEN)


async def sync_etf_list(db: AsyncSession) -> dict:
    """
    从 tushare fund_basic 拉取场内基金列表，筛选 ETF，写入 etf_basic。
    返回 {total, inserted, updated, skipped}
    """
    pro = _get_pro()
    df = pro.fund_basic(
        market="E",
        fields="ts_code,name,fund_type,list_date,delist_date,status",
    )
    if df is None or df.empty:
        return {"total": 0, "inserted": 0, "updated": 0, "skipped": 0}

    # 只保留名称中含 ETF 的（排除 LOF 等）
    df = df[df["name"].str.contains("ETF", case=False, na=False)].copy()
    listed = df[df["status"] == "L"]

    stats = {"total": len(listed), "inserted": 0, "updated": 0, "skipped": 0}
    for _, row in listed.iterrows():
        ts_code = row["ts_code"]  # e.g. "510300.SH"
        code = ts_code.split(".")[0]
        exchange = ts_code.split(".")[1]
        name = row["name"]
        list_date = None
        if pd.notna(row.get("list_date")) and row["list_date"]:
            try:
                list_date = datetime.strptime(str(row["list_date"]), "%Y%m%d").date()
            except (ValueError, TypeError):
                pass
        category = _classify_etf(name)

        stmt = pg_insert(EtfBasic).values(
            code=code, name=name, category=category,
            exchange=exchange, list_date=list_date, is_active=True,
        ).on_conflict_do_update(
            index_elements=["code"],
            set_={"name": name, "category": category, "is_active": True,
                   "list_date": list_date},
        )
        result = await db.execute(stmt)
        if result.rowcount > 0:
            stats["inserted"] += 1
        else:
            stats["skipped"] += 1

    # 标记已退市的 ETF
    delisted = df[df["status"] == "D"]
    for _, row in delisted.iterrows():
        code = row["ts_code"].split(".")[0]
        await db.execute(
            EtfBasic.__table__.update()
            .where(EtfBasic.code == code)
            .values(is_active=False)
        )

    await db.commit()
    logger.info("ETF列表同步完成: %s", stats)
    return stats


async def pull_daily_single(
    db: AsyncSession,
    ts_code: str,
    start_date: str = "20100101",
    end_date: Optional[str] = None,
) -> int:
    """
    拉取单只 ETF 全部日线数据（自动分页），写入 etf_daily。
    ts_code 格式："510300.SH"
    返回新增记录数。
    """
    pro = _get_pro()
    code = ts_code.split(".")[0]
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    all_rows = []
    offset = 0
    while True:
        try:
            df = pro.fund_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=FIELDS_DAILY,
                limit=PAGE_LIMIT,
                offset=offset,
            )
        except Exception as e:
            logger.warning("tushare fund_daily 失败 %s offset=%d: %s", ts_code, offset, e)
            break

        if df is None or df.empty:
            break

        all_rows.append(df)
        if len(df) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(REQUEST_INTERVAL)

    if not all_rows:
        return 0

    combined = pd.concat(all_rows, ignore_index=True)
    count = 0
    for _, row in combined.iterrows():
        trade_date_str = str(row.get("trade_date", ""))
        if not trade_date_str or len(trade_date_str) != 8:
            continue
        try:
            trade_date = datetime.strptime(trade_date_str, "%Y%m%d").date()
        except ValueError:
            continue

        stmt = pg_insert(EtfDaily).values(
            code=code,
            trade_date=trade_date,
            open=_safe_float(row.get("open")),
            high=_safe_float(row.get("high")),
            low=_safe_float(row.get("low")),
            close=_safe_float(row.get("close")),
            volume=_safe_int(row.get("vol")),
            amount=_safe_float(row.get("amount")),
            pre_close=_safe_float(row.get("pre_close")),
        ).on_conflict_do_nothing(constraint="uq_etf_daily_code_date")
        await db.execute(stmt)
        count += 1

    await db.commit()
    return count


async def pull_daily_by_date(
    db: AsyncSession,
    trade_date: str,
) -> int:
    """
    按交易日期拉取所有 ETF 当天行情，写入 etf_daily。
    trade_date 格式："20260306"
    返回新增记录数。
    """
    pro = _get_pro()
    try:
        df = pro.fund_daily(
            trade_date=trade_date,
            fields=FIELDS_DAILY,
            limit=PAGE_LIMIT,
            offset=0,
        )
    except Exception as e:
        logger.warning("tushare fund_daily 按日期拉取失败 %s: %s", trade_date, e)
        return 0

    if df is None or df.empty:
        return 0

    td = datetime.strptime(trade_date, "%Y%m%d").date()

    # 只入库 etf_basic 里已有的 ETF
    existing_result = await db.execute(select(EtfBasic.code))
    existing_codes = {r[0] for r in existing_result.fetchall()}

    count = 0
    for _, row in df.iterrows():
        ts_code = str(row.get("ts_code", ""))
        code = ts_code.split(".")[0] if "." in ts_code else ts_code
        if code not in existing_codes:
            continue

        stmt = pg_insert(EtfDaily).values(
            code=code,
            trade_date=td,
            open=_safe_float(row.get("open")),
            high=_safe_float(row.get("high")),
            low=_safe_float(row.get("low")),
            close=_safe_float(row.get("close")),
            volume=_safe_int(row.get("vol")),
            amount=_safe_float(row.get("amount")),
            pre_close=_safe_float(row.get("pre_close")),
        ).on_conflict_do_nothing(constraint="uq_etf_daily_code_date")
        await db.execute(stmt)
        count += 1

    await db.commit()
    return count


async def pull_all_history(
    db: AsyncSession,
    start_date: str = "20100101",
    skip_existing: bool = True,
    progress_every: int = 50,
) -> dict:
    """
    全量拉取所有活跃 ETF 的日线数据。
    skip_existing=True 时跳过已有 >100 条记录的 ETF。
    返回 {total, processed, skipped, records, errors}
    """
    result = await db.execute(
        select(EtfBasic.code, EtfBasic.exchange)
        .where(EtfBasic.is_active == True)
        .order_by(EtfBasic.code)
    )
    all_etfs = result.fetchall()
    total = len(all_etfs)

    # 已有数据统计
    cnt_result = await db.execute(
        select(EtfDaily.code, func.count().label("cnt"))
        .group_by(EtfDaily.code)
    )
    existing_counts = {r[0]: r[1] for r in cnt_result.fetchall()}

    stats = {"total": total, "processed": 0, "skipped": 0, "records": 0, "errors": 0}
    end_date = datetime.now().strftime("%Y%m%d")

    for i, (code, exchange) in enumerate(all_etfs):
        if skip_existing and existing_counts.get(code, 0) > 100:
            stats["skipped"] += 1
            continue

        ts_code = f"{code}.{exchange}"
        try:
            records = await pull_daily_single(db, ts_code, start_date, end_date)
            stats["records"] += records
            stats["processed"] += 1
        except Exception as e:
            logger.warning("拉取 %s 失败: %s", ts_code, e)
            stats["errors"] += 1

        if (i + 1) % progress_every == 0:
            logger.info("进度: %d/%d, 新增 %d 条, 跳过 %d, 错误 %d",
                        i + 1, total, stats["records"], stats["skipped"], stats["errors"])

        time.sleep(REQUEST_INTERVAL)

    logger.info("全量拉取完成: %s", stats)
    return stats


async def incremental_update(db: AsyncSession, days: int = 5) -> dict:
    """
    增量更新：拉取最近 N 个交易日的数据（按日期拉取，效率高）。
    返回 {dates_processed, records}
    """
    from datetime import timedelta
    end = datetime.now()
    stats = {"dates_processed": 0, "records": 0}

    for d in range(days):
        dt = end - timedelta(days=d)
        date_str = dt.strftime("%Y%m%d")
        records = await pull_daily_by_date(db, date_str)
        if records > 0:
            stats["dates_processed"] += 1
            stats["records"] += records
        time.sleep(REQUEST_INTERVAL)

    logger.info("增量更新完成: %s", stats)
    return stats


def _safe_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        if pd.isna(val):
            return None
        return int(float(val))
    except (TypeError, ValueError):
        return None
