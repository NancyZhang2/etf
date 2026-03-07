"""
Quant模块路由 — 策略、回测、信号API
"""

import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.etf import EtfBasic, EtfDaily
from backend.app.models.strategy import (
    BacktestResult, Strategy, StrategyCategory, TradingSignal, VirtualPortfolio,
)
from backend.app.schemas.quant import BacktestRequest
from backend.app.services.backtest import BacktestEngine
from backend.app.services import virtual_portfolio as vp_service
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
from backend.app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)
router = APIRouter()

# 策略类型 → 策略类映射
STRATEGY_CLASSES = {
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
}


@router.get("/strategies")
async def strategy_list(category_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """策略列表"""
    query = select(Strategy, StrategyCategory.name.label("cat_name")).outerjoin(
        StrategyCategory, Strategy.category_id == StrategyCategory.id
    )
    if category_id:
        query = query.where(Strategy.category_id == category_id)

    result = await db.execute(query)
    rows = result.all()
    data = [
        {
            "id": s.id, "name": s.name, "category": cat_name,
            "strategy_type": s.strategy_type, "description": s.description,
            "is_active": s.is_active,
        }
        for s, cat_name in rows
    ]
    return success_response(data)


@router.get("/strategies/{strategy_id}")
async def strategy_detail(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """策略详情"""
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    s = result.scalar_one_or_none()
    if not s:
        return error_response(404, f"策略 {strategy_id} 不存在")

    return success_response({
        "id": s.id, "name": s.name, "strategy_type": s.strategy_type,
        "description": s.description, "params": s.params,
        "default_params": s.default_params, "etf_pool": s.etf_pool,
        "is_active": s.is_active,
    })


@router.get("/strategies/{strategy_id}/backtest")
async def strategy_backtest(
    strategy_id: int, year: Optional[int] = None, db: AsyncSession = Depends(get_db)
):
    """获取已保存的回测结果"""
    query = select(BacktestResult).where(BacktestResult.strategy_id == strategy_id)
    if year is not None:
        query = query.where(BacktestResult.year == year)
    else:
        query = query.where(BacktestResult.year == 0)  # 全区间

    result = await db.execute(query)
    bt = result.scalar_one_or_none()
    if not bt:
        return error_response(404, "无回测结果，请先运行回测")

    return success_response({
        "year": bt.year, "total_return": _f(bt.total_return),
        "annual_return": _f(bt.annual_return), "max_drawdown": _f(bt.max_drawdown),
        "annual_volatility": _f(bt.annual_volatility), "sharpe_ratio": _f(bt.sharpe_ratio),
        "sortino_ratio": _f(bt.sortino_ratio), "calmar_ratio": _f(bt.calmar_ratio),
        "win_rate": _f(bt.win_rate), "profit_loss_ratio": _f(bt.profit_loss_ratio),
        "total_trades": bt.total_trades, "benchmark_return": _f(bt.benchmark_return),
        "excess_return": _f(bt.excess_return),
    })


@router.post("/strategies/{strategy_id}/backtest")
async def strategy_backtest_custom(
    strategy_id: int, req: BacktestRequest, db: AsyncSession = Depends(get_db)
):
    """自定义参数运行回测"""
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy_row = result.scalar_one_or_none()
    if not strategy_row:
        return error_response(404, f"策略 {strategy_id} 不存在")

    cls = STRATEGY_CLASSES.get(strategy_row.strategy_type)
    if not cls:
        return error_response(501, f"策略类型 {strategy_row.strategy_type} 尚未实现")

    # 合并参数
    merged_params = {**(strategy_row.default_params or {}), **req.params}
    strategy_instance = cls(params=merged_params)
    etf_pool = strategy_instance.get_etf_pool()

    # 加载数据
    data = await _load_etf_data(db, etf_pool)
    if not data:
        return error_response(400, "无可用ETF数据")

    # 生成信号
    weights = strategy_instance.generate_signals(data)
    if weights.empty:
        return error_response(400, "信号生成失败")

    # 构建收盘价矩阵
    close_df = _build_close_df(data)

    # 回测
    engine = BacktestEngine()
    metrics = engine.run_backtest(close_df, weights, benchmark_code="510300")

    return success_response(metrics)


@router.get("/strategies/{strategy_id}/backtest/yearly")
async def strategy_backtest_yearly(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """逐年回测结果"""
    result = await db.execute(
        select(BacktestResult)
        .where(BacktestResult.strategy_id == strategy_id, BacktestResult.year > 0)
        .order_by(BacktestResult.year)
    )
    rows = result.scalars().all()
    if not rows:
        return error_response(404, "无逐年回测结果")

    data = [
        {
            "year": bt.year, "annual_return": _f(bt.annual_return),
            "max_drawdown": _f(bt.max_drawdown), "sharpe_ratio": _f(bt.sharpe_ratio),
            "sortino_ratio": _f(bt.sortino_ratio), "calmar_ratio": _f(bt.calmar_ratio),
            "win_rate": _f(bt.win_rate), "total_trades": bt.total_trades,
        }
        for bt in rows
    ]
    return success_response(data)


@router.get("/strategies/{strategy_id}/portfolio")
async def strategy_portfolio(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """虚拟持仓"""
    result = await db.execute(
        select(VirtualPortfolio)
        .where(VirtualPortfolio.strategy_id == strategy_id)
        .order_by(VirtualPortfolio.trade_date)
    )
    rows = result.scalars().all()
    data = [
        {
            "trade_date": r.trade_date.isoformat(), "etf_code": r.etf_code,
            "position": _f(r.position), "nav": _f(r.nav),
            "daily_return": _f(r.daily_return),
        }
        for r in rows
    ]
    return success_response(data)


@router.get("/signals/latest")
async def signals_latest(strategy_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """最新交易信号"""
    query = (
        select(TradingSignal, Strategy.name.label("strategy_name"), EtfBasic.name.label("etf_name"))
        .join(Strategy, TradingSignal.strategy_id == Strategy.id)
        .outerjoin(EtfBasic, TradingSignal.etf_code == EtfBasic.code)
    )
    if strategy_id:
        query = query.where(TradingSignal.strategy_id == strategy_id)

    query = query.order_by(TradingSignal.signal_date.desc()).limit(50)
    result = await db.execute(query)
    rows = result.all()

    data = [
        {
            "strategy_name": sname, "etf_code": sig.etf_code, "etf_name": ename,
            "signal": sig.signal, "target_weight": _f(sig.target_weight),
            "reason": sig.reason, "signal_date": sig.signal_date.isoformat(),
        }
        for sig, sname, ename in rows
    ]
    return success_response(data)


@router.get("/signals/history")
async def signals_history(
    strategy_id: Optional[int] = None,
    etf_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """信号历史"""
    query = select(TradingSignal)
    if strategy_id:
        query = query.where(TradingSignal.strategy_id == strategy_id)
    if etf_code:
        query = query.where(TradingSignal.etf_code == etf_code)
    if start_date:
        query = query.where(TradingSignal.signal_date >= start_date)
    if end_date:
        query = query.where(TradingSignal.signal_date <= end_date)

    query = query.order_by(TradingSignal.signal_date.desc()).limit(200)
    result = await db.execute(query)
    rows = result.scalars().all()

    data = [
        {"signal_date": r.signal_date.isoformat(), "signal": r.signal, "reason": r.reason}
        for r in rows
    ]
    return success_response(data)


@router.get("/signals/calendar")
async def signals_calendar(month: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """信号日历"""
    return error_response(501, "信号日历尚未实现")


@router.post("/strategies/{strategy_id}/optimize")
async def strategy_optimize(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """参数优化"""
    return error_response(501, "参数优化尚未实现")


# ---------- 虚拟持仓跟踪 ----------

@router.post("/strategies/{strategy_id}/virtual/start")
async def virtual_start(
    strategy_id: int,
    req: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
):
    """创建虚拟账户"""
    from decimal import Decimal as D

    # 检查策略是否存在
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    if not result.scalar_one_or_none():
        return error_response(404, f"策略 {strategy_id} 不存在")

    # 检查是否已存在
    existing = await vp_service.get_account(db, strategy_id)
    if existing:
        return error_response(400, "该策略已有虚拟账户")

    capital = D(str(req.get("initial_capital", 200000))) if req else vp_service.DEFAULT_CAPITAL
    account = await vp_service.create_account(db, strategy_id, capital)
    return success_response({
        "account_id": account.id,
        "strategy_id": account.strategy_id,
        "initial_capital": float(account.initial_capital),
        "cash": float(account.cash),
    })


@router.get("/strategies/{strategy_id}/virtual/summary")
async def virtual_summary(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """账户概览 + 持仓明细"""
    summary = await vp_service.get_account_summary(db, strategy_id)
    if summary is None:
        return error_response(404, "该策略无虚拟账户")
    return success_response(summary)


@router.get("/strategies/{strategy_id}/virtual/trades")
async def virtual_trades(
    strategy_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """交易记录列表"""
    from datetime import date as date_type

    sd = date_type.fromisoformat(start_date) if start_date else None
    ed = date_type.fromisoformat(end_date) if end_date else None
    trades = await vp_service.get_trade_history(db, strategy_id, sd, ed)
    return success_response(trades)


@router.get("/strategies/{strategy_id}/virtual/nav")
async def virtual_nav(strategy_id: int, db: AsyncSession = Depends(get_db)):
    """每日总资产序列"""
    result = await db.execute(
        select(VirtualPortfolio)
        .where(
            VirtualPortfolio.strategy_id == strategy_id,
            VirtualPortfolio.etf_code == "",
        )
        .order_by(VirtualPortfolio.trade_date)
    )
    rows = result.scalars().all()
    data = [
        {
            "trade_date": r.trade_date.isoformat(),
            "nav": _f(r.nav) or 0,
            "daily_return": _f(r.daily_return) or 0,
        }
        for r in rows
    ]
    return success_response(data)


# ---------- Helper functions ----------

async def _load_etf_data(db: AsyncSession, etf_codes: list) -> dict:
    """加载ETF数据，返回 {code: DataFrame}"""
    result = {}
    for code in etf_codes:
        rows = await db.execute(
            select(EtfDaily)
            .where(EtfDaily.code == code)
            .order_by(EtfDaily.trade_date)
        )
        records = rows.scalars().all()
        if not records:
            continue
        df = pd.DataFrame([
            {
                "date": r.trade_date,
                "open": float(r.open) if r.open else None,
                "high": float(r.high) if r.high else None,
                "low": float(r.low) if r.low else None,
                "close": float(r.close) if r.close else None,
                "volume": r.volume,
            }
            for r in records
        ])
        result[code] = df
    return result


def _build_close_df(data: dict) -> pd.DataFrame:
    """从 {code: DataFrame} 构建收盘价矩阵"""
    close_dict = {}
    for code, df in data.items():
        if df.empty:
            continue
        series = df.set_index("date")["close"].sort_index()
        series.index = pd.to_datetime(series.index)
        close_dict[code] = series
    return pd.DataFrame(close_dict).sort_index().ffill()


def _f(val) -> Optional[float]:
    """安全转换 Decimal → float，过滤 NaN/Inf"""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None
