"""
信号生成服务 — 运行策略并产出 BUY/SELL/HOLD 信号
"""

import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.etf import EtfDaily
from backend.app.models.strategy import Strategy, TradingSignal
from backend.app.models.virtual_portfolio import VirtualAccount

logger = logging.getLogger(__name__)

# 策略类映射
STRATEGY_CLASSES = {}


def _get_strategy_classes():
    """延迟导入策略类"""
    if not STRATEGY_CLASSES:
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

        STRATEGY_CLASSES.update({
            "momentum": MomentumStrategy,
            "ma_trend": MATrendStrategy,
            "grid": GridStrategy,
            "asset_alloc": AssetAllocStrategy,
            "egg_28": Egg28Strategy,
            "guorn_rotation": GuornRotationStrategy,
            "egg_28_plus": Egg28PlusStrategy,
            "baxian": BaxianStrategy,
            "sleep_balance": SleepBalanceStrategy,
            "all_weather_cn": AllWeatherCNStrategy,
            "value_rotation": ValueRotationStrategy,
            "huabao_grid": HuabaoGridStrategy,
            "rsrs_momentum": RSRSMomentumStrategy,
            "multi_factor": MultiFactorStrategy,
        })
    return STRATEGY_CLASSES


async def generate_signals_for_strategy(
    db: AsyncSession,
    strategy_row: Strategy,
    signal_date: Optional[date] = None,
) -> List[Dict]:
    """
    为单个策略生成信号

    返回: [{etf_code, signal, target_weight, reason}]
    """
    classes = _get_strategy_classes()
    cls = classes.get(strategy_row.strategy_type)
    if not cls:
        logger.warning("未知策略类型: %s", strategy_row.strategy_type)
        return []

    strategy = cls(params=strategy_row.params)
    etf_pool = strategy.get_etf_pool()
    hedge_etf = strategy.params.get("hedge_etf", "511880")
    all_codes = list(set(etf_pool + [hedge_etf]))

    # 加载数据
    data = await _load_etf_data(db, all_codes)
    if not data:
        logger.warning("策略 %s 无可用数据", strategy_row.name)
        return []

    # 生成权重
    weights = strategy.generate_signals(data)
    if weights.empty:
        return []

    # 取最后一天的权重作为今日信号
    last_weights = weights.iloc[-1]
    if signal_date is None:
        signal_date = weights.index[-1].date() if hasattr(weights.index[-1], 'date') else date.today()

    signals = []
    prev_weights = weights.iloc[-2] if len(weights) > 1 else pd.Series(0.0, index=last_weights.index)

    for code in etf_pool + [hedge_etf]:
        if code not in last_weights.index:
            continue

        curr_w = float(last_weights.get(code, 0))
        prev_w = float(prev_weights.get(code, 0))

        if curr_w > 0.01 and prev_w <= 0.01:
            signal = "BUY"
            reason = f"目标权重 {curr_w:.1%}"
        elif curr_w <= 0.01 and prev_w > 0.01:
            signal = "SELL"
            reason = f"清仓，前权重 {prev_w:.1%}"
        elif curr_w > 0.01:
            signal = "HOLD"
            reason = f"持有，权重 {curr_w:.1%}"
        else:
            continue  # 无持仓且无变化，跳过

        signals.append({
            "etf_code": code,
            "signal": signal,
            "target_weight": round(curr_w, 4),
            "reason": reason,
        })

    return signals


async def generate_all_signals(db: AsyncSession) -> int:
    """运行所有已启用策略，生成信号并存库"""
    result = await db.execute(
        select(Strategy).where(Strategy.is_active == True)
    )
    strategies = result.scalars().all()
    total_signals = 0

    for strategy_row in strategies:
        try:
            signals = await generate_signals_for_strategy(db, strategy_row)
            today = date.today()

            for sig in signals:
                stmt = pg_insert(TradingSignal).values(
                    strategy_id=strategy_row.id,
                    etf_code=sig["etf_code"],
                    signal_date=today,
                    signal=sig["signal"],
                    target_weight=sig["target_weight"],
                    reason=sig["reason"],
                ).on_conflict_do_nothing()
                await db.execute(stmt)
                total_signals += 1

            # 更新策略的最后信号日期
            strategy_row.last_signal_date = today

            # 虚拟持仓联动：若策略有虚拟账户，执行虚拟交易
            await _execute_virtual_trades(db, strategy_row.id, signals, today)

            logger.info("策略 %s: %d 个信号", strategy_row.name, len(signals))

        except Exception as e:
            logger.error("策略 %s 信号生成失败: %s", strategy_row.name, e)

    await db.commit()
    logger.info("全部信号生成完成: %d 个信号", total_signals)
    return total_signals


async def _load_etf_data(db: AsyncSession, etf_codes: list) -> dict:
    """加载ETF数据"""
    result = {}
    for code in etf_codes:
        rows = await db.execute(
            select(EtfDaily).where(EtfDaily.code == code).order_by(EtfDaily.trade_date)
        )
        records = rows.scalars().all()
        if not records:
            continue
        df = pd.DataFrame([{
            "date": r.trade_date,
            "open": float(r.open) if r.open else None,
            "high": float(r.high) if r.high else None,
            "low": float(r.low) if r.low else None,
            "close": float(r.close) if r.close else None,
            "volume": r.volume,
        } for r in records])
        result[code] = df
    return result


async def _execute_virtual_trades(
    db: AsyncSession,
    strategy_id: int,
    signals: List[Dict],
    trade_date: date,
) -> None:
    """信号生成后自动执行虚拟交易（如果策略有虚拟账户）"""
    # 检查是否有虚拟账户
    result = await db.execute(
        select(VirtualAccount).where(VirtualAccount.strategy_id == strategy_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return

    try:
        from backend.app.services.virtual_portfolio import (
            execute_signals, update_daily_snapshot,
        )
        await execute_signals(db, strategy_id, signals, trade_date)
        await update_daily_snapshot(db, strategy_id, trade_date)
        logger.info("策略 %d: 虚拟交易执行完成", strategy_id)
    except Exception as e:
        logger.error("策略 %d 虚拟交易执行失败: %s", strategy_id, e)
