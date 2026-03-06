"""
虚拟持仓跟踪服务 — 虚拟资金法模拟交易
"""

import logging
import math
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.etf import EtfDaily
from backend.app.models.strategy import VirtualPortfolio
from backend.app.models.virtual_portfolio import (
    VirtualAccount, VirtualPosition, VirtualTrade,
)

logger = logging.getLogger(__name__)

# 常量
COMMISSION_RATE = Decimal("0.00015")  # 万1.5
MIN_COMMISSION = Decimal("0.1")       # 最低佣金 0.1 元
LOT_SIZE = 100                        # ETF 最小交易单位
DEFAULT_CAPITAL = Decimal("200000")   # 默认 20 万


async def create_account(
    db: AsyncSession,
    strategy_id: int,
    initial_capital: Decimal = DEFAULT_CAPITAL,
) -> VirtualAccount:
    """为策略创建虚拟账户"""
    account = VirtualAccount(
        strategy_id=strategy_id,
        initial_capital=initial_capital,
        cash=initial_capital,
        total_value=initial_capital,
    )
    db.add(account)
    await db.flush()
    return account


async def get_account(db: AsyncSession, strategy_id: int) -> Optional[VirtualAccount]:
    """获取策略的虚拟账户"""
    result = await db.execute(
        select(VirtualAccount).where(VirtualAccount.strategy_id == strategy_id)
    )
    return result.scalar_one_or_none()


async def execute_signals(
    db: AsyncSession,
    strategy_id: int,
    signals: List[Dict],
    trade_date: date,
) -> List[VirtualTrade]:
    """
    根据信号执行虚拟交易

    signals: [{etf_code, signal, target_weight}]
    """
    account = await get_account(db, strategy_id)
    if not account:
        return []

    # 获取当日收盘价
    etf_codes = [s["etf_code"] for s in signals]
    prices = await _get_close_prices(db, etf_codes, trade_date)
    if not prices:
        logger.warning("策略 %d 无法获取 %s 收盘价", strategy_id, trade_date)
        return []

    # 先更新现有持仓市值以计算 total_value
    await _refresh_market_values(db, account, prices)
    total_value = account.cash + await _sum_market_values(db, account.id)

    trades: List[VirtualTrade] = []

    # 先处理 SELL，释放资金
    for sig in signals:
        if sig["signal"] != "SELL":
            continue
        trade = await _execute_sell(
            db, account, sig, trade_date, prices, total_value,
        )
        if trade:
            trades.append(trade)

    # 刷新 total_value（卖出后现金增加了）
    total_value = account.cash + await _sum_market_values(db, account.id)

    # 再处理 BUY
    for sig in signals:
        if sig["signal"] != "BUY":
            continue
        trade = await _execute_buy(
            db, account, sig, trade_date, prices, total_value,
        )
        if trade:
            trades.append(trade)

    # 更新账户 total_value
    account.total_value = account.cash + await _sum_market_values(db, account.id)
    await db.flush()
    return trades


async def update_daily_snapshot(
    db: AsyncSession,
    strategy_id: int,
    trade_date: date,
) -> None:
    """写入每日快照到 virtual_portfolios"""
    account = await get_account(db, strategy_id)
    if not account:
        return

    # 获取所有持仓的当日价格
    positions = await _get_positions(db, account.id)
    etf_codes = [p.etf_code for p in positions]
    prices = await _get_close_prices(db, etf_codes, trade_date) if etf_codes else {}

    # 更新持仓市值
    await _refresh_market_values(db, account, prices)
    today_total = account.cash + await _sum_market_values(db, account.id)
    account.total_value = today_total

    # 取昨日快照计算 daily_return
    prev = await db.execute(
        select(VirtualPortfolio)
        .where(
            VirtualPortfolio.strategy_id == strategy_id,
            VirtualPortfolio.trade_date < trade_date,
        )
        .order_by(VirtualPortfolio.trade_date.desc())
        .limit(1)
    )
    prev_row = prev.scalar_one_or_none()
    if prev_row and prev_row.nav and float(prev_row.nav) > 0:
        daily_return = (today_total - prev_row.nav) / prev_row.nav
    else:
        daily_return = Decimal("0")

    # 写入快照（聚合行：etf_code 为空字符串表示整个组合）
    snapshot = VirtualPortfolio(
        strategy_id=strategy_id,
        trade_date=trade_date,
        etf_code="",
        position=Decimal("0"),
        nav=today_total,
        daily_return=daily_return,
    )
    db.add(snapshot)
    await db.flush()


async def get_account_summary(db: AsyncSession, strategy_id: int) -> Optional[Dict]:
    """返回账户概览 + 持仓明细"""
    account = await get_account(db, strategy_id)
    if not account:
        return None

    positions = await _get_positions(db, account.id)
    total_value = float(account.total_value)
    initial = float(account.initial_capital)
    total_return_pct = (total_value - initial) / initial if initial > 0 else 0

    pos_list = []
    for p in positions:
        if p.quantity <= 0:
            continue
        avg_cost = float(p.avg_cost) if p.avg_cost else 0
        mv = float(p.market_value) if p.market_value else 0
        cost_total = avg_cost * p.quantity
        profit_pct = (mv - cost_total) / cost_total if cost_total > 0 else 0
        pos_list.append({
            "etf_code": p.etf_code,
            "quantity": p.quantity,
            "avg_cost": round(avg_cost, 4),
            "market_value": round(mv, 2),
            "profit_pct": round(profit_pct, 4),
        })

    return {
        "initial_capital": initial,
        "cash": round(float(account.cash), 2),
        "total_value": round(total_value, 2),
        "total_return_pct": round(total_return_pct, 4),
        "positions": pos_list,
        "start_date": account.created_at.date().isoformat() if account.created_at else None,
    }


async def get_trade_history(
    db: AsyncSession,
    strategy_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Dict]:
    """交易记录列表"""
    account = await get_account(db, strategy_id)
    if not account:
        return []

    query = select(VirtualTrade).where(VirtualTrade.account_id == account.id)
    if start_date:
        query = query.where(VirtualTrade.trade_date >= start_date)
    if end_date:
        query = query.where(VirtualTrade.trade_date <= end_date)
    query = query.order_by(VirtualTrade.trade_date.desc(), VirtualTrade.id.desc())

    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": t.id,
            "etf_code": t.etf_code,
            "trade_date": t.trade_date.isoformat(),
            "direction": t.direction,
            "price": round(float(t.price), 4),
            "quantity": t.quantity,
            "amount": round(float(t.amount), 2),
            "commission": round(float(t.commission), 2),
        }
        for t in rows
    ]


# ========== 内部辅助函数 ==========

async def _get_close_prices(
    db: AsyncSession, etf_codes: List[str], trade_date: date,
) -> Dict[str, Decimal]:
    """获取指定日期的收盘价"""
    prices: Dict[str, Decimal] = {}
    for code in etf_codes:
        result = await db.execute(
            select(EtfDaily.close)
            .where(EtfDaily.code == code, EtfDaily.trade_date == trade_date)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            prices[code] = Decimal(str(row))
    return prices


async def _get_positions(db: AsyncSession, account_id: int) -> List[VirtualPosition]:
    """获取账户所有持仓"""
    result = await db.execute(
        select(VirtualPosition).where(VirtualPosition.account_id == account_id)
    )
    return list(result.scalars().all())


async def _get_or_create_position(
    db: AsyncSession, account_id: int, etf_code: str,
) -> VirtualPosition:
    """获取或创建持仓记录"""
    result = await db.execute(
        select(VirtualPosition).where(
            and_(
                VirtualPosition.account_id == account_id,
                VirtualPosition.etf_code == etf_code,
            )
        )
    )
    pos = result.scalar_one_or_none()
    if pos is None:
        pos = VirtualPosition(
            account_id=account_id,
            etf_code=etf_code,
            quantity=0,
            avg_cost=Decimal("0"),
            market_value=Decimal("0"),
        )
        db.add(pos)
        await db.flush()
    return pos


async def _refresh_market_values(
    db: AsyncSession,
    account: VirtualAccount,
    prices: Dict[str, Decimal],
) -> None:
    """用最新价格刷新持仓市值"""
    positions = await _get_positions(db, account.id)
    for pos in positions:
        if pos.etf_code in prices and pos.quantity > 0:
            pos.market_value = prices[pos.etf_code] * pos.quantity
    await db.flush()


async def _sum_market_values(db: AsyncSession, account_id: int) -> Decimal:
    """合计持仓市值"""
    positions = await _get_positions(db, account_id)
    return sum((p.market_value or Decimal("0")) for p in positions)


def _calc_commission(amount: Decimal) -> Decimal:
    """计算佣金"""
    commission = abs(amount) * COMMISSION_RATE
    return max(commission, MIN_COMMISSION)


async def _execute_buy(
    db: AsyncSession,
    account: VirtualAccount,
    sig: Dict,
    trade_date: date,
    prices: Dict[str, Decimal],
    total_value: Decimal,
) -> Optional[VirtualTrade]:
    """执行买入"""
    code = sig["etf_code"]
    target_weight = Decimal(str(sig["target_weight"]))
    price = prices.get(code)
    if not price or price <= 0:
        return None

    pos = await _get_or_create_position(db, account.id, code)
    current_mv = price * pos.quantity
    target_amount = total_value * target_weight
    buy_amount = target_amount - current_mv

    if buy_amount <= 0:
        return None

    # 按手计算
    buy_quantity = int(math.floor(float(buy_amount / price) / LOT_SIZE)) * LOT_SIZE
    if buy_quantity <= 0:
        return None

    actual_amount = price * buy_quantity
    commission = _calc_commission(actual_amount)
    total_cost = actual_amount + commission

    if total_cost > account.cash:
        # 资金不足，尝试减少手数
        buy_quantity = int(math.floor(float(account.cash - MIN_COMMISSION) / float(price) / LOT_SIZE)) * LOT_SIZE
        if buy_quantity <= 0:
            return None
        actual_amount = price * buy_quantity
        commission = _calc_commission(actual_amount)
        total_cost = actual_amount + commission

    # 更新账户
    account.cash -= total_cost

    # 更新持仓
    old_cost_total = pos.avg_cost * pos.quantity
    pos.quantity += buy_quantity
    if pos.quantity > 0:
        pos.avg_cost = (old_cost_total + actual_amount) / pos.quantity
    pos.market_value = price * pos.quantity

    # 记录交易
    trade = VirtualTrade(
        account_id=account.id,
        etf_code=code,
        trade_date=trade_date,
        direction="BUY",
        price=price,
        quantity=buy_quantity,
        amount=actual_amount,
        commission=commission,
    )
    db.add(trade)
    await db.flush()
    return trade


async def _execute_sell(
    db: AsyncSession,
    account: VirtualAccount,
    sig: Dict,
    trade_date: date,
    prices: Dict[str, Decimal],
    total_value: Decimal,
) -> Optional[VirtualTrade]:
    """执行卖出"""
    code = sig["etf_code"]
    target_weight = Decimal(str(sig["target_weight"]))
    price = prices.get(code)
    if not price or price <= 0:
        return None

    pos = await _get_or_create_position(db, account.id, code)
    if pos.quantity <= 0:
        return None

    current_mv = price * pos.quantity
    target_amount = total_value * target_weight

    # target_weight ≈ 0 时全部卖出
    if target_weight < Decimal("0.005"):
        sell_quantity = pos.quantity
    else:
        sell_amount = current_mv - target_amount
        if sell_amount <= 0:
            return None
        sell_quantity = int(math.floor(float(sell_amount / price) / LOT_SIZE)) * LOT_SIZE
        if sell_quantity <= 0:
            return None

    if sell_quantity > pos.quantity:
        sell_quantity = pos.quantity

    actual_amount = price * sell_quantity
    commission = _calc_commission(actual_amount)

    # 更新账户
    account.cash += actual_amount - commission

    # 更新持仓
    pos.quantity -= sell_quantity
    if pos.quantity > 0:
        pos.market_value = price * pos.quantity
    else:
        pos.market_value = Decimal("0")
        pos.avg_cost = Decimal("0")

    # 记录交易
    trade = VirtualTrade(
        account_id=account.id,
        etf_code=code,
        trade_date=trade_date,
        direction="SELL",
        price=price,
        quantity=sell_quantity,
        amount=actual_amount,
        commission=commission,
    )
    db.add(trade)
    await db.flush()
    return trade
