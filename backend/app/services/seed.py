"""
种子数据 — 策略分类 + 全部14个策略记录
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.strategy import Strategy, StrategyCategory

logger = logging.getLogger(__name__)


async def seed_strategy_data(db: AsyncSession) -> None:
    """写入策略分类和所有策略种子数据"""
    from backend.app.services.strategies.momentum import MomentumStrategy
    from backend.app.services.strategies.ma_trend import MATrendStrategy
    from backend.app.services.strategies.grid import GridStrategy
    from backend.app.services.strategies.asset_alloc import AssetAllocStrategy
    from backend.app.services.strategies.egg_28 import Egg28Strategy
    from backend.app.services.strategies.guorn_rotation import GuornRotationStrategy
    from backend.app.services.strategies.egg_28_plus import Egg28PlusStrategy
    from backend.app.services.strategies.baxian import BaxianStrategy
    from backend.app.services.strategies.sleep_balance import SleepBalanceStrategy
    from backend.app.services.strategies.all_weather_cn import AllWeatherCNStrategy
    from backend.app.services.strategies.value_rotation import ValueRotationStrategy
    from backend.app.services.strategies.huabao_grid import HuabaoGridStrategy
    from backend.app.services.strategies.rsrs_momentum import RSRSMomentumStrategy
    from backend.app.services.strategies.multi_factor import MultiFactorStrategy

    # 1. 策略分类
    existing = await db.execute(select(StrategyCategory))
    if not existing.scalars().first():
        cat_classic = StrategyCategory(
            name="经典量化策略",
            description="基于经典量化理论的策略实现，包括动量、均线、网格、资产配置等",
        )
        cat_reverse = StrategyCategory(
            name="竞品逆向策略",
            description="对知名量化平台策略的逆向工程复刻，包括蛋卷二八、果仁行业轮动等",
        )
        db.add_all([cat_classic, cat_reverse])
        await db.flush()
        classic_id = cat_classic.id
        reverse_id = cat_reverse.id
        logger.info("策略分类已创建")
    else:
        cats = await db.execute(select(StrategyCategory))
        cat_list = cats.scalars().all()
        classic_id = cat_list[0].id
        reverse_id = cat_list[1].id if len(cat_list) > 1 else cat_list[0].id

    # 2. 策略列表
    strategy_defs = [
        (MomentumStrategy, classic_id),
        (MATrendStrategy, classic_id),
        (GridStrategy, classic_id),
        (AssetAllocStrategy, classic_id),
        (Egg28Strategy, reverse_id),
        (GuornRotationStrategy, reverse_id),
        (Egg28PlusStrategy, reverse_id),
        (BaxianStrategy, reverse_id),
        (SleepBalanceStrategy, reverse_id),
        (AllWeatherCNStrategy, reverse_id),
        (ValueRotationStrategy, reverse_id),
        (HuabaoGridStrategy, reverse_id),
        (RSRSMomentumStrategy, reverse_id),
        (MultiFactorStrategy, reverse_id),
    ]

    for cls, cat_id in strategy_defs:
        instance = cls()
        # 检查是否已存在
        existing = await db.execute(
            select(Strategy).where(Strategy.strategy_type == instance.strategy_type)
        )
        if existing.scalar_one_or_none():
            continue

        strategy = Strategy(
            category_id=cat_id,
            name=instance.strategy_name,
            strategy_type=instance.strategy_type,
            description=instance.description,
            params=instance.get_default_params(),
            default_params=instance.get_default_params(),
            etf_pool=instance.get_etf_pool(),
            is_active=True,
        )
        db.add(strategy)
        logger.info("已添加策略: %s", instance.strategy_name)

    await db.commit()
    logger.info("种子数据写入完成")
