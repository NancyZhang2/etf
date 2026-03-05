"""
示例数据生成 — 用于无外网环境的开发测试
生成与真实数据结构一致的ETF基础信息和历史行情
"""

import asyncio
import logging
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.etf import EtfBasic, EtfDaily, TradingCalendar

logger = logging.getLogger(__name__)

# 模拟ETF数据（动量策略池 + 避险ETF + 其他常见ETF）
SAMPLE_ETFS = [
    # 动量策略池
    ("510300", "沪深300ETF", "宽基", "SH", "2012-05-28"),
    ("510500", "中证500ETF", "宽基", "SH", "2013-02-06"),
    ("510050", "上证50ETF", "宽基", "SH", "2005-02-23"),
    ("159915", "创业板ETF", "宽基", "SZ", "2011-12-09"),
    ("510880", "红利ETF", "宽基", "SH", "2007-11-05"),
    ("512010", "医药ETF", "行业", "SH", "2013-08-23"),
    ("512880", "证券ETF", "行业", "SH", "2016-08-16"),
    ("159928", "消费ETF", "宽基", "SZ", "2013-09-10"),
    ("518880", "黄金ETF", "商品", "SH", "2013-07-18"),
    ("511010", "国债ETF", "债券", "SH", "2013-03-05"),
    # 避险
    ("511880", "银华日利", "货币", "SH", "2013-04-25"),
    # 其他常见
    ("159919", "沪深300ETF", "宽基", "SZ", "2012-05-28"),
    ("510330", "华夏沪深300ETF", "宽基", "SH", "2012-12-28"),
    ("159901", "深100ETF", "宽基", "SZ", "2006-03-24"),
    ("510010", "治理ETF", "宽基", "SH", "2009-11-16"),
    ("512000", "券商ETF", "行业", "SH", "2016-06-30"),
    ("515790", "光伏ETF", "行业", "SH", "2021-01-18"),
    ("516160", "新能源ETF", "行业", "SH", "2021-06-15"),
    ("512690", "酒ETF", "行业", "SH", "2019-12-18"),
    ("159869", "游戏ETF", "主题", "SZ", "2021-08-06"),
    ("513100", "纳指ETF", "跨境", "SH", "2013-04-25"),
    ("513050", "中概互联ETF", "跨境", "SH", "2017-01-04"),
    ("159920", "恒生ETF", "跨境", "SZ", "2012-08-09"),
    ("511260", "十年国债ETF", "债券", "SH", "2017-03-31"),
    ("511020", "活跃国债ETF", "债券", "SH", "2014-05-19"),
]


def _generate_price_series(
    start_price: float,
    n_days: int,
    annual_return: float = 0.06,
    daily_vol: float = 0.015,
) -> list:
    """生成模拟价格序列"""
    daily_drift = annual_return / 252
    prices = [start_price]
    for _ in range(n_days - 1):
        change = daily_drift + daily_vol * random.gauss(0, 1)
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 0.01))
    return prices


def _get_trading_days(start: date, end: date) -> list:
    """生成交易日列表（排除周末）"""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 周一到周五
            days.append(current)
        current += timedelta(days=1)
    return days


async def generate_sample_data(db: AsyncSession) -> dict:
    """生成全量示例数据"""
    stats = {"etfs": 0, "daily_records": 0, "calendar_days": 0}

    # 1. 写入ETF基本信息
    for code, name, category, exchange, list_date_str in SAMPLE_ETFS:
        stmt = pg_insert(EtfBasic).values(
            code=code, name=name, category=category,
            exchange=exchange,
            list_date=date.fromisoformat(list_date_str),
            is_active=True,
        ).on_conflict_do_update(
            index_elements=["code"],
            set_={"name": name, "category": category, "is_active": True},
        )
        await db.execute(stmt)
        stats["etfs"] += 1

    await db.commit()
    logger.info("写入 %d 只ETF基本信息", stats["etfs"])

    # 2. 生成历史行情（从2019-01-02到2026-03-03，约7年数据）
    start_date = date(2019, 1, 2)
    end_date = date(2026, 3, 3)
    trading_days = _get_trading_days(start_date, end_date)
    n_days = len(trading_days)

    # 各ETF的初始价格和年化收益率设定
    etf_configs = {
        "510300": (4.0, 0.08, 0.012), "510500": (5.5, 0.06, 0.015),
        "510050": (2.8, 0.07, 0.011), "159915": (1.8, 0.10, 0.018),
        "510880": (2.5, 0.09, 0.010), "512010": (1.2, 0.05, 0.016),
        "512880": (0.9, 0.04, 0.020), "159928": (1.5, 0.12, 0.013),
        "518880": (3.2, 0.05, 0.008), "511010": (115.0, 0.03, 0.002),
        "511880": (100.0, 0.02, 0.0005),
        "159919": (4.1, 0.08, 0.012), "510330": (4.0, 0.08, 0.012),
        "159901": (3.5, 0.07, 0.014), "510010": (1.0, 0.05, 0.013),
        "512000": (0.8, 0.04, 0.021), "515790": (1.0, 0.15, 0.022),
        "516160": (1.0, 0.12, 0.020), "512690": (1.0, 0.14, 0.019),
        "159869": (1.0, 0.03, 0.025), "513100": (1.5, 0.15, 0.016),
        "513050": (1.2, 0.08, 0.020), "159920": (1.5, 0.04, 0.015),
        "511260": (98.0, 0.03, 0.003), "511020": (100.0, 0.03, 0.002),
    }

    random.seed(42)  # 可重复

    for code, name, *_ in SAMPLE_ETFS:
        cfg = etf_configs.get(code, (1.0, 0.06, 0.015))
        start_price, annual_ret, daily_vol = cfg
        prices = _generate_price_series(start_price, n_days, annual_ret, daily_vol)

        batch_values = []
        for j, (td, price) in enumerate(zip(trading_days, prices)):
            high = price * (1 + abs(random.gauss(0, daily_vol * 0.5)))
            low = price * (1 - abs(random.gauss(0, daily_vol * 0.5)))
            open_p = low + (high - low) * random.random()
            volume = random.randint(1_000_000, 500_000_000)
            amount = volume * price

            batch_values.append({
                "code": code,
                "trade_date": td,
                "open": round(open_p, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(price, 4),
                "volume": volume,
                "amount": round(amount, 2),
            })

        # 批量插入
        for i in range(0, len(batch_values), 500):
            batch = batch_values[i:i + 500]
            stmt = pg_insert(EtfDaily).values(batch).on_conflict_do_nothing(
                constraint="uq_etf_daily_code_date"
            )
            await db.execute(stmt)
            await db.commit()

        stats["daily_records"] += len(batch_values)
        logger.info("ETF %s (%s): %d 条行情", code, name, len(batch_values))

    # 3. 交易日历
    for td in trading_days:
        stmt = pg_insert(TradingCalendar).values(
            date=td, is_trading_day=True,
        ).on_conflict_do_nothing(index_elements=["date"])
        await db.execute(stmt)
    await db.commit()
    stats["calendar_days"] = len(trading_days)

    logger.info("示例数据生成完成: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        from backend.app.database import async_session
        from backend.app.services.seed import seed_strategy_data

        async with async_session() as db:
            await seed_strategy_data(db)
            stats = await generate_sample_data(db)
            print(f"Done: {stats}")

    asyncio.run(main())
