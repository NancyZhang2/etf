"""
运行全部策略的回测并持久化到 backtest_results 表，然后生成当日信号。
"""
import asyncio
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run_all_backtests():
    from backend.app.database import async_session
    from backend.app.models.etf import EtfDaily
    from backend.app.models.strategy import Strategy, BacktestResult
    from backend.app.services.backtest import BacktestEngine
    from backend.app.services.signal import _get_strategy_classes

    strategy_classes = _get_strategy_classes()
    engine = BacktestEngine()

    async with async_session() as db:
        # Load all strategies
        result = await db.execute(select(Strategy).where(Strategy.is_active == True))
        strategies = result.scalars().all()
        logger.info("=== 开始回测 %d 个策略 ===", len(strategies))

        for s in strategies:
            cls = strategy_classes.get(s.strategy_type)
            if not cls:
                logger.warning("跳过 %s: 未知策略类型 %s", s.name, s.strategy_type)
                continue

            logger.info("--- 回测策略: %s (%s) ---", s.name, s.strategy_type)

            # Instantiate strategy
            strategy_instance = cls(params=s.params or s.default_params)
            etf_pool = strategy_instance.get_etf_pool()
            hedge_etf = strategy_instance.params.get("hedge_etf", "511880")
            all_codes = list(set(etf_pool + [hedge_etf]))

            # Load ETF data from DB
            data = {}
            for code in all_codes:
                rows = await db.execute(
                    select(EtfDaily).where(EtfDaily.code == code).order_by(EtfDaily.trade_date)
                )
                records = rows.scalars().all()
                if not records:
                    logger.warning("  ETF %s 无数据", code)
                    continue
                df = pd.DataFrame([{
                    "date": r.trade_date,
                    "open": float(r.open) if r.open else None,
                    "high": float(r.high) if r.high else None,
                    "low": float(r.low) if r.low else None,
                    "close": float(r.close) if r.close else None,
                    "volume": r.volume,
                } for r in records])
                data[code] = df

            if not data:
                logger.warning("  无可用数据，跳过")
                continue

            logger.info("  加载了 %d 只ETF数据", len(data))

            # Generate weights
            try:
                weights = strategy_instance.generate_signals(data)
            except Exception as e:
                logger.error("  信号生成失败: %s", e)
                continue

            if weights.empty:
                logger.warning("  权重矩阵为空，跳过")
                continue

            logger.info("  权重矩阵: %d 行 x %d 列", weights.shape[0], weights.shape[1])

            # Build close price matrix
            close_dict = {}
            for code, df in data.items():
                if df.empty:
                    continue
                series = df.set_index("date")["close"].sort_index()
                series.index = pd.to_datetime(series.index)
                close_dict[code] = series
            close_df = pd.DataFrame(close_dict).sort_index().ffill()

            # Run full-period backtest
            try:
                full_metrics = engine.run_backtest(close_df, weights, benchmark_code="510300")
            except Exception as e:
                logger.error("  全区间回测失败: %s", e)
                continue

            logger.info("  全区间: 年化%.2f%% 回撤%.2f%% 夏普%.2f",
                        full_metrics["annual_return"] * 100,
                        full_metrics["max_drawdown"] * 100,
                        full_metrics["sharpe_ratio"])

            # Delete old results for this strategy
            await db.execute(
                delete(BacktestResult).where(BacktestResult.strategy_id == s.id)
            )

            # Save full-period result (year=0)
            await db.execute(
                pg_insert(BacktestResult).values(
                    strategy_id=s.id,
                    year=0,
                    params_snapshot=s.params,
                    **full_metrics,
                )
            )

            # Run yearly backtest (last 5 years)
            try:
                yearly = engine.run_yearly_backtest(close_df, weights, years=5, benchmark_code="510300")
                for ym in yearly:
                    year = ym.pop("year")
                    await db.execute(
                        pg_insert(BacktestResult).values(
                            strategy_id=s.id,
                            year=year,
                            params_snapshot=s.params,
                            **ym,
                        )
                    )
                logger.info("  逐年回测: %d 年", len(yearly))
            except Exception as e:
                logger.error("  逐年回测失败: %s", e)

            await db.commit()

        # Final count
        cnt = await db.execute(select(BacktestResult))
        total = len(cnt.scalars().all())
        logger.info("=== 回测完成, backtest_results 共 %d 条记录 ===", total)


async def run_all_signals():
    from backend.app.database import async_session
    from backend.app.services.signal import generate_all_signals

    logger.info("=== 开始生成信号 ===")
    async with async_session() as db:
        total = await generate_all_signals(db)
        logger.info("=== 信号生成完成, 共 %d 条 ===", total)


async def main():
    await run_all_backtests()
    await run_all_signals()


if __name__ == "__main__":
    asyncio.run(main())
