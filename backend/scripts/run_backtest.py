"""
运行全部策略回测并保存结果到数据库
"""

import asyncio
import logging
import sys

import pandas as pd
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_all_backtests():
    from backend.app.database import async_session
    from backend.app.models.etf import EtfDaily
    from backend.app.models.strategy import BacktestResult, Strategy
    from backend.app.services.backtest import BacktestEngine
    from backend.app.services.signal import _get_strategy_classes

    classes = _get_strategy_classes()

    async with async_session() as db:
        # 清除旧的回测结果
        await db.execute(delete(BacktestResult))
        await db.commit()

        strategies = await db.execute(select(Strategy))
        all_strategies = strategies.scalars().all()

        for strategy_row in all_strategies:
            cls = classes.get(strategy_row.strategy_type)
            if not cls:
                logger.warning("跳过未知策略: %s", strategy_row.strategy_type)
                continue

            logger.info("=== 回测策略: %s ===", strategy_row.name)

            strategy = cls(params=strategy_row.params)
            etf_pool = strategy.get_etf_pool()
            hedge_etf = strategy.params.get("hedge_etf", "511880")
            all_codes = list(set(etf_pool + [hedge_etf]))

            # 加载数据
            data = {}
            for code in all_codes:
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
                data[code] = df

            if not data:
                logger.warning("策略 %s: 无数据", strategy_row.name)
                continue

            # 生成信号
            weights = strategy.generate_signals(data)
            if weights.empty:
                logger.warning("策略 %s: 信号为空", strategy_row.name)
                continue

            logger.info("信号矩阵: %d行 x %d列", *weights.shape)

            # 构建收盘价矩阵
            close_dict = {}
            for code, df in data.items():
                series = df.set_index("date")["close"].sort_index()
                series.index = pd.to_datetime(series.index)
                close_dict[code] = series
            close_df = pd.DataFrame(close_dict).sort_index().ffill()

            # 全区间回测
            engine = BacktestEngine()
            metrics = engine.run_backtest(close_df, weights, benchmark_code="510300")
            logger.info("全区间: return=%.2f%%, sharpe=%.2f, drawdown=%.2f%%",
                        metrics["annual_return"] * 100, metrics["sharpe_ratio"],
                        metrics["max_drawdown"] * 100)

            # 保存全区间 (year=0)
            await _save_backtest(db, strategy_row.id, 0, metrics, strategy_row.params)

            # 逐年回测
            yearly = engine.run_yearly_backtest(close_df, weights, years=5, benchmark_code="510300")
            for yr in yearly:
                await _save_backtest(db, strategy_row.id, yr["year"], yr, strategy_row.params)
                logger.info("  %d: return=%.2f%%, sharpe=%.2f",
                            yr["year"], yr["annual_return"] * 100, yr["sharpe_ratio"])

            await db.commit()

        logger.info("=== 全部回测完成 ===")


async def _save_backtest(db, strategy_id, year, metrics, params):
    from backend.app.models.strategy import BacktestResult
    stmt = pg_insert(BacktestResult).values(
        strategy_id=strategy_id,
        year=year,
        total_return=metrics["total_return"],
        annual_return=metrics["annual_return"],
        max_drawdown=metrics["max_drawdown"],
        annual_volatility=metrics["annual_volatility"],
        sharpe_ratio=metrics["sharpe_ratio"],
        sortino_ratio=metrics["sortino_ratio"],
        calmar_ratio=metrics["calmar_ratio"],
        win_rate=metrics["win_rate"],
        profit_loss_ratio=metrics["profit_loss_ratio"],
        total_trades=metrics["total_trades"],
        turnover_rate=metrics["turnover_rate"],
        benchmark_return=metrics.get("benchmark_return", 0),
        excess_return=metrics.get("excess_return", 0),
        params_snapshot=params,
    ).on_conflict_do_nothing()
    await db.execute(stmt)


if __name__ == "__main__":
    asyncio.run(run_all_backtests())
