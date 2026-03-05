"""
ETF 数据服务 — akshare 数据拉取、清洗、增量更新
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import akshare as ak
import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.etf import EtfBasic, EtfDaily, TradingCalendar

logger = logging.getLogger(__name__)

# akshare 是同步库，用线程池包装
_executor = ThreadPoolExecutor(max_workers=2)

# ETF 分类关键词映射
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "宽基": ["沪深300", "中证500", "中证1000", "上证50", "创业板", "科创",
             "中证100", "中证200", "中证800", "中证A50", "MSCI", "万得全A",
             "深证100", "深证成指", "红利", "价值", "成长", "大盘", "小盘",
             "中盘", "龙头", "基本面", "A50"],
    "行业": ["银行", "证券", "保险", "金融", "地产", "房地产",
             "医药", "医疗", "生物", "中药", "创新药",
             "消费", "食品", "饮料", "白酒", "家电",
             "科技", "电子", "芯片", "半导体", "通信", "5G", "计算机", "软件",
             "新能源", "光伏", "锂电", "电力", "煤炭", "钢铁", "有色",
             "军工", "国防", "航天",
             "汽车", "机械", "建材", "化工", "农业", "畜牧",
             "传媒", "游戏", "影视", "教育",
             "交通", "运输", "物流", "港口", "航空",
             "环保", "水务", "稀土"],
    "主题": ["ESG", "碳中和", "一带一路", "国企改革", "专精特新",
             "人工智能", "机器人", "数字经济", "数据", "云计算", "大数据",
             "物联网", "区块链", "元宇宙", "网络安全",
             "养老", "北交所", "REITs", "央企"],
    "商品": ["黄金", "白银", "原油", "能源化工", "有色金属", "豆粕", "商品"],
    "债券": ["国债", "企债", "信用债", "可转债", "利率债", "城投债", "债券"],
    "货币": ["货币", "现金", "理财"],
    "跨境": ["恒生", "港股", "纳斯达克", "纳指", "标普", "日经", "德国",
             "法国", "东南亚", "中概", "港股通", "H股", "美国",
             "亚太", "印度", "韩国", "越南", "沙特"],
}


def _classify_etf(name: str) -> str:
    """根据ETF名称分类"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return category
    return "宽基"  # 默认归入宽基


def _detect_exchange(code: str) -> str:
    """根据代码判断交易所"""
    if code.startswith(("51", "56", "58", "60")):
        return "SH"
    return "SZ"


async def _run_sync(func_call):
    """在线程池中运行同步 akshare 调用"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func_call)


async def _run_sync_with_retry(func_call, retries: int = 3, delay: float = 5.0):
    """带重试的同步调用包装"""
    last_err = None
    for attempt in range(retries):
        try:
            return await _run_sync(func_call)
        except Exception as e:
            last_err = e
            logger.warning("第 %d 次尝试失败: %s，%s秒后重试", attempt + 1, e, delay)
            await asyncio.sleep(delay)
            delay *= 1.5  # 退避
    raise last_err


async def fetch_and_store_etf_list(db: AsyncSession) -> int:
    """
    拉取全量ETF列表并存入 etf_basic
    返回：新增/更新的ETF数量
    """
    logger.info("开始拉取ETF列表...")

    try:
        df = await _run_sync_with_retry(lambda: ak.fund_etf_spot_em())
    except Exception as e:
        logger.error("akshare fund_etf_spot_em 调用失败: %s", e)
        raise

    if df is None or df.empty:
        logger.warning("未获取到ETF数据")
        return 0

    count = 0
    for _, row in df.iterrows():
        code = str(row.get("代码", "")).strip()
        name = str(row.get("名称", "")).strip()
        if not code or not name:
            continue

        category = _classify_etf(name)
        exchange = _detect_exchange(code)

        stmt = pg_insert(EtfBasic).values(
            code=code,
            name=name,
            category=category,
            exchange=exchange,
            is_active=True,
        ).on_conflict_do_update(
            index_elements=["code"],
            set_={"name": name, "category": category, "is_active": True},
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("ETF列表拉取完成，共 %d 只", count)
    return count


async def fetch_history_for_single_etf(
    db: AsyncSession,
    code: str,
    start_date: str = "20100101",
    end_date: Optional[str] = None,
) -> int:
    """
    拉取单只ETF历史行情并入库
    返回：新插入的记录数
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    try:
        df = await _run_sync_with_retry(
            lambda: ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date,
                adjust="qfq",
            )
        )
    except Exception as e:
        logger.warning("ETF %s 历史数据拉取失败: %s", code, e)
        return 0

    if df is None or df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        trade_date = pd.to_datetime(row.get("日期")).date() if pd.notna(row.get("日期")) else None
        if trade_date is None:
            continue

        stmt = pg_insert(EtfDaily).values(
            code=code,
            trade_date=trade_date,
            open=_safe_decimal(row.get("开盘")),
            high=_safe_decimal(row.get("最高")),
            low=_safe_decimal(row.get("最低")),
            close=_safe_decimal(row.get("收盘")),
            volume=_safe_int(row.get("成交量")),
            amount=_safe_decimal(row.get("成交额")),
        ).on_conflict_do_nothing(
            constraint="uq_etf_daily_code_date"
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    return count


def _safe_decimal(val) -> Optional[float]:
    """安全转换为 decimal/float"""
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    """安全转换为 int"""
    try:
        if pd.isna(val):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


async def fetch_all_history(
    db: AsyncSession,
    start_date: str = "20100101",
    delay: float = 0.3,
) -> Tuple[int, int]:
    """
    全量拉取所有ETF历史数据（断点续传）
    返回：(已处理ETF数, 总新增记录数)
    """
    result = await db.execute(
        select(EtfBasic.code).where(EtfBasic.is_active == True).order_by(EtfBasic.code)
    )
    all_codes = [r[0] for r in result.fetchall()]
    total_etfs = len(all_codes)
    logger.info("开始全量拉取 %d 只ETF的历史数据...", total_etfs)

    processed = 0
    total_records = 0

    for i, code in enumerate(all_codes):
        # 断点续传：检查已有数据量
        cnt_result = await db.execute(
            select(func.count()).select_from(EtfDaily).where(EtfDaily.code == code)
        )
        existing_count = cnt_result.scalar() or 0
        if existing_count > 100:
            # 已有足够数据，跳过（增量更新会补齐）
            processed += 1
            continue

        records = await fetch_history_for_single_etf(db, code, start_date)
        total_records += records
        processed += 1

        if (i + 1) % 50 == 0:
            logger.info("进度: %d/%d，本轮新增 %d 条", i + 1, total_etfs, total_records)

        await asyncio.sleep(delay)

    logger.info("全量拉取完成: %d 只ETF，共 %d 条新记录", processed, total_records)
    return processed, total_records


async def incremental_update(db: AsyncSession) -> Tuple[int, int]:
    """
    增量更新（只拉取最近5个交易日数据）
    校验：更新后记录数 >= 已知活跃ETF的90%
    返回：(更新ETF数, 新增记录数)
    """
    result = await db.execute(
        select(EtfBasic.code).where(EtfBasic.is_active == True)
    )
    all_codes = [r[0] for r in result.fetchall()]
    total_etfs = len(all_codes)

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

    logger.info("开始增量更新 %d 只ETF...", total_etfs)

    updated = 0
    total_records = 0

    for i, code in enumerate(all_codes):
        records = await fetch_history_for_single_etf(db, code, start_date, end_date)
        total_records += records
        if records > 0:
            updated += 1

        if (i + 1) % 100 == 0:
            logger.info("增量进度: %d/%d", i + 1, total_etfs)

        await asyncio.sleep(0.2)

    # 校验
    if updated < total_etfs * 0.9:
        logger.warning(
            "增量更新校验告警: 仅 %d/%d (%.1f%%) ETF有新数据",
            updated, total_etfs, updated / total_etfs * 100 if total_etfs else 0,
        )

    logger.info("增量更新完成: %d 只ETF有更新，共 %d 条新记录", updated, total_records)
    return updated, total_records


async def clean_data(db: AsyncSession) -> Dict[str, int]:
    """
    数据清洗：停牌标记 + 异常值检测 + 去重
    返回：各项清洗统计
    """
    stats = {"duplicates_removed": 0, "anomalies_flagged": 0, "suspended_marked": 0}

    # 1. 去重（保留id最小的）
    dedup_sql = text("""
        DELETE FROM etf_daily a
        USING etf_daily b
        WHERE a.id > b.id
          AND a.code = b.code
          AND a.trade_date = b.trade_date
    """)
    result = await db.execute(dedup_sql)
    stats["duplicates_removed"] = result.rowcount
    await db.commit()

    # 2. 停牌检测（成交量为0或NULL的标记）
    suspended_sql = text("""
        SELECT COUNT(*) FROM etf_daily
        WHERE (volume IS NULL OR volume = 0)
          AND close IS NOT NULL
    """)
    result = await db.execute(suspended_sql)
    stats["suspended_marked"] = result.scalar() or 0

    # 3. 异常值检测（单日涨跌超过20%的记录）
    anomaly_sql = text("""
        SELECT COUNT(*) FROM etf_daily d1
        JOIN etf_daily d2 ON d1.code = d2.code
          AND d2.trade_date = (
            SELECT MAX(trade_date) FROM etf_daily
            WHERE code = d1.code AND trade_date < d1.trade_date
          )
        WHERE d2.close > 0
          AND ABS((d1.close - d2.close) / d2.close) > 0.20
    """)
    try:
        result = await db.execute(anomaly_sql)
        stats["anomalies_flagged"] = result.scalar() or 0
    except Exception as e:
        logger.warning("异常值检测查询失败: %s", e)

    logger.info("数据清洗完成: %s", stats)
    return stats


async def fetch_trading_calendar(db: AsyncSession) -> int:
    """
    拉取交易日历（使用 akshare tool_trade_date_hist_sina）
    返回：写入记录数
    """
    logger.info("开始拉取交易日历...")

    try:
        df = await _run_sync_with_retry(lambda: ak.tool_trade_date_hist_sina())
    except Exception as e:
        logger.error("交易日历拉取失败: %s", e)
        raise

    if df is None or df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        trade_date = pd.to_datetime(row.get("trade_date")).date() if pd.notna(row.get("trade_date")) else None
        if trade_date is None:
            continue

        stmt = pg_insert(TradingCalendar).values(
            date=trade_date,
            is_trading_day=True,
        ).on_conflict_do_nothing(index_elements=["date"])
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info("交易日历写入 %d 个交易日", count)
    return count


async def get_data_status(db: AsyncSession) -> Dict:
    """获取数据状态概览"""
    etf_count_result = await db.execute(
        select(func.count()).select_from(EtfBasic).where(EtfBasic.is_active == True)
    )
    etf_count = etf_count_result.scalar() or 0

    record_count_result = await db.execute(
        select(func.count()).select_from(EtfDaily)
    )
    record_count = record_count_result.scalar() or 0

    last_sync_result = await db.execute(
        select(func.max(EtfDaily.trade_date))
    )
    last_date = last_sync_result.scalar()

    status = "ok" if record_count > 0 else "empty"

    return {
        "last_sync": last_date.isoformat() if last_date else None,
        "record_count": record_count,
        "etf_count": etf_count,
        "status": status,
    }
