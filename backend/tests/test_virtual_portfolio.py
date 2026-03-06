"""
虚拟持仓跟踪测试
"""

import pytest
import pytest_asyncio
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Base
from backend.app.models.etf import EtfBasic, EtfDaily
from backend.app.models.strategy import Strategy, StrategyCategory, VirtualPortfolio
from backend.app.models.virtual_portfolio import (
    VirtualAccount, VirtualPosition, VirtualTrade,
)
from backend.app.services.virtual_portfolio import (
    COMMISSION_RATE, DEFAULT_CAPITAL, LOT_SIZE, MIN_COMMISSION,
    create_account, execute_signals, get_account, get_account_summary,
    get_trade_history, update_daily_snapshot, _calc_commission,
)


# ---------- Fixtures ----------

@pytest_asyncio.fixture
async def setup_data(db_session: AsyncSession):
    """插入测试用基础数据"""
    # 清理可能残留的数据（按依赖顺序）
    await db_session.execute(text("DELETE FROM virtual_trades"))
    await db_session.execute(text("DELETE FROM virtual_positions"))
    await db_session.execute(text("DELETE FROM virtual_portfolios"))
    await db_session.execute(text("DELETE FROM virtual_accounts"))
    await db_session.execute(text("DELETE FROM trading_signals"))
    await db_session.execute(text("DELETE FROM backtest_results"))
    await db_session.execute(text("DELETE FROM research_frameworks"))
    await db_session.execute(text("DELETE FROM research_reports"))
    await db_session.execute(text("DELETE FROM user_subscriptions"))
    await db_session.execute(text("DELETE FROM etf_daily"))
    await db_session.execute(text("DELETE FROM strategies"))
    await db_session.execute(text("DELETE FROM strategy_categories"))
    await db_session.execute(text("DELETE FROM etf_basic"))
    await db_session.commit()

    # 插入 ETF 基础数据
    etf1 = EtfBasic(code="510300", name="沪深300ETF", category="宽基", exchange="SH")
    etf2 = EtfBasic(code="510500", name="中证500ETF", category="宽基", exchange="SH")
    etf3 = EtfBasic(code="511880", name="银华日利", category="货币", exchange="SH")
    db_session.add_all([etf1, etf2, etf3])
    await db_session.flush()

    # 插入行情数据
    trade_date_1 = date(2026, 3, 4)
    trade_date_2 = date(2026, 3, 5)
    trade_date_3 = date(2026, 3, 6)

    daily_records = [
        # 510300
        EtfDaily(code="510300", trade_date=trade_date_1, open=Decimal("4.000"), high=Decimal("4.100"),
                 low=Decimal("3.950"), close=Decimal("4.050"), volume=100000, amount=Decimal("405000"),
                 pre_close=Decimal("3.980")),
        EtfDaily(code="510300", trade_date=trade_date_2, open=Decimal("4.050"), high=Decimal("4.150"),
                 low=Decimal("4.000"), close=Decimal("4.100"), volume=120000, amount=Decimal("492000"),
                 pre_close=Decimal("4.050")),
        EtfDaily(code="510300", trade_date=trade_date_3, open=Decimal("4.100"), high=Decimal("4.200"),
                 low=Decimal("4.050"), close=Decimal("4.150"), volume=110000, amount=Decimal("456500"),
                 pre_close=Decimal("4.100")),
        # 510500
        EtfDaily(code="510500", trade_date=trade_date_1, open=Decimal("6.000"), high=Decimal("6.100"),
                 low=Decimal("5.950"), close=Decimal("6.050"), volume=80000, amount=Decimal("484000"),
                 pre_close=Decimal("5.980")),
        EtfDaily(code="510500", trade_date=trade_date_2, open=Decimal("6.050"), high=Decimal("6.150"),
                 low=Decimal("6.000"), close=Decimal("6.100"), volume=90000, amount=Decimal("549000"),
                 pre_close=Decimal("6.050")),
        EtfDaily(code="510500", trade_date=trade_date_3, open=Decimal("6.100"), high=Decimal("6.200"),
                 low=Decimal("6.050"), close=Decimal("6.150"), volume=85000, amount=Decimal("522750"),
                 pre_close=Decimal("6.100")),
        # 511880
        EtfDaily(code="511880", trade_date=trade_date_1, open=Decimal("100.000"), high=Decimal("100.010"),
                 low=Decimal("99.990"), close=Decimal("100.005"), volume=50000, amount=Decimal("5000250"),
                 pre_close=Decimal("100.000")),
        EtfDaily(code="511880", trade_date=trade_date_2, open=Decimal("100.005"), high=Decimal("100.015"),
                 low=Decimal("99.995"), close=Decimal("100.010"), volume=55000, amount=Decimal("5500550"),
                 pre_close=Decimal("100.005")),
        EtfDaily(code="511880", trade_date=trade_date_3, open=Decimal("100.010"), high=Decimal("100.020"),
                 low=Decimal("100.000"), close=Decimal("100.015"), volume=52000, amount=Decimal("5200780"),
                 pre_close=Decimal("100.010")),
    ]
    db_session.add_all(daily_records)
    await db_session.flush()

    # 插入策略
    cat = StrategyCategory(name="经典量化策略", description="测试分类")
    db_session.add(cat)
    await db_session.flush()

    strategy = Strategy(
        category_id=cat.id,
        name="测试动量策略",
        strategy_type="momentum",
        description="测试用",
        params={"lookback": 20},
        default_params={"lookback": 20},
        etf_pool=["510300", "510500"],
        is_active=True,
    )
    db_session.add(strategy)
    await db_session.flush()
    await db_session.commit()

    return {
        "strategy_id": strategy.id,
        "trade_dates": [trade_date_1, trade_date_2, trade_date_3],
    }


# ---------- 单元测试 ----------

class TestCalcCommission:
    def test_normal_commission(self):
        amount = Decimal("10000")
        result = _calc_commission(amount)
        expected = amount * COMMISSION_RATE  # 1.5
        assert result == expected

    def test_min_commission(self):
        amount = Decimal("100")
        result = _calc_commission(amount)
        assert result == MIN_COMMISSION  # 0.1

    def test_zero_amount(self):
        result = _calc_commission(Decimal("0"))
        assert result == MIN_COMMISSION


class TestCreateAccount:
    @pytest.mark.anyio
    async def test_create_default(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        account = await create_account(db_session, sid)
        assert account.strategy_id == sid
        assert account.initial_capital == DEFAULT_CAPITAL
        assert account.cash == DEFAULT_CAPITAL
        assert account.total_value == DEFAULT_CAPITAL

    @pytest.mark.anyio
    async def test_create_custom_capital(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        # 先清理上面可能创建的
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        capital = Decimal("500000")
        account = await create_account(db_session, sid, capital)
        assert account.initial_capital == capital
        assert account.cash == capital


class TestGetAccount:
    @pytest.mark.anyio
    async def test_existing(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()
        await create_account(db_session, sid)
        account = await get_account(db_session, sid)
        assert account is not None
        assert account.strategy_id == sid

    @pytest.mark.anyio
    async def test_not_existing(self, db_session):
        account = await get_account(db_session, 99999)
        assert account is None


class TestExecuteSignals:
    @pytest.mark.anyio
    async def test_buy_signal(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)

        signals = [
            {"etf_code": "510300", "signal": "BUY", "target_weight": 0.5},
        ]
        trades = await execute_signals(db_session, sid, signals, td)

        assert len(trades) == 1
        trade = trades[0]
        assert trade.direction == "BUY"
        assert trade.etf_code == "510300"
        assert trade.price == Decimal("4.050")
        assert trade.quantity > 0
        assert trade.quantity % LOT_SIZE == 0  # 整手
        assert float(trade.commission) > 0

        # 验证账户现金减少
        account = await get_account(db_session, sid)
        assert float(account.cash) < float(DEFAULT_CAPITAL)

    @pytest.mark.anyio
    async def test_sell_signal(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td1 = setup_data["trade_dates"][0]
        td2 = setup_data["trade_dates"][1]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)

        # 先买入
        buy_signals = [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.5}]
        await execute_signals(db_session, sid, buy_signals, td1)

        account_after_buy = await get_account(db_session, sid)
        cash_after_buy = float(account_after_buy.cash)

        # 再卖出（清仓）
        sell_signals = [{"etf_code": "510300", "signal": "SELL", "target_weight": 0.0}]
        trades = await execute_signals(db_session, sid, sell_signals, td2)

        assert len(trades) == 1
        assert trades[0].direction == "SELL"

        # 验证现金增加
        account = await get_account(db_session, sid)
        assert float(account.cash) > cash_after_buy

    @pytest.mark.anyio
    async def test_no_account(self, db_session, setup_data):
        """没有虚拟账户时应返回空列表"""
        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        trades = await execute_signals(
            db_session, setup_data["strategy_id"],
            [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.5}],
            date(2026, 3, 4),
        )
        assert trades == []

    @pytest.mark.anyio
    async def test_buy_quantity_lot_size(self, db_session, setup_data):
        """买入数量必须是 LOT_SIZE 的整数倍"""
        sid = setup_data["strategy_id"]
        td = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)

        signals = [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.3}]
        trades = await execute_signals(db_session, sid, signals, td)

        assert len(trades) == 1
        assert trades[0].quantity % LOT_SIZE == 0

    @pytest.mark.anyio
    async def test_multiple_signals(self, db_session, setup_data):
        """同时买入多只ETF"""
        sid = setup_data["strategy_id"]
        td = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)

        signals = [
            {"etf_code": "510300", "signal": "BUY", "target_weight": 0.3},
            {"etf_code": "510500", "signal": "BUY", "target_weight": 0.3},
        ]
        # SELL first, then BUY — only BUY here
        trades = await execute_signals(db_session, sid, signals, td)
        assert len(trades) == 2


class TestUpdateDailySnapshot:
    @pytest.mark.anyio
    async def test_snapshot_created(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td1 = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_portfolios WHERE strategy_id = :sid"), {"sid": sid})
        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)
        await update_daily_snapshot(db_session, sid, td1)

        result = await db_session.execute(
            select(VirtualPortfolio).where(
                VirtualPortfolio.strategy_id == sid,
                VirtualPortfolio.trade_date == td1,
            )
        )
        snapshot = result.scalar_one_or_none()
        assert snapshot is not None
        assert float(snapshot.nav) == float(DEFAULT_CAPITAL)

    @pytest.mark.anyio
    async def test_daily_return_calc(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td1, td2 = setup_data["trade_dates"][0], setup_data["trade_dates"][1]

        await db_session.execute(text("DELETE FROM virtual_portfolios WHERE strategy_id = :sid"), {"sid": sid})
        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)
        await update_daily_snapshot(db_session, sid, td1)

        # 买入一些
        signals = [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.5}]
        await execute_signals(db_session, sid, signals, td1)
        await update_daily_snapshot(db_session, sid, td2)

        result = await db_session.execute(
            select(VirtualPortfolio).where(
                VirtualPortfolio.strategy_id == sid,
                VirtualPortfolio.trade_date == td2,
                VirtualPortfolio.etf_code == "",
            )
        )
        snapshot = result.scalar_one_or_none()
        assert snapshot is not None
        # daily_return 应该有值
        assert snapshot.daily_return is not None


class TestGetAccountSummary:
    @pytest.mark.anyio
    async def test_summary_structure(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)
        signals = [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.5}]
        await execute_signals(db_session, sid, signals, td)

        summary = await get_account_summary(db_session, sid)
        assert summary is not None
        assert "initial_capital" in summary
        assert "cash" in summary
        assert "total_value" in summary
        assert "total_return_pct" in summary
        assert "positions" in summary
        assert isinstance(summary["positions"], list)
        assert len(summary["positions"]) > 0

    @pytest.mark.anyio
    async def test_no_account(self, db_session):
        summary = await get_account_summary(db_session, 99999)
        assert summary is None


class TestGetTradeHistory:
    @pytest.mark.anyio
    async def test_trade_history(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td = setup_data["trade_dates"][0]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)
        signals = [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.5}]
        await execute_signals(db_session, sid, signals, td)

        history = await get_trade_history(db_session, sid)
        assert len(history) == 1
        trade = history[0]
        assert trade["etf_code"] == "510300"
        assert trade["direction"] == "BUY"
        assert trade["quantity"] > 0
        assert trade["amount"] > 0
        assert trade["commission"] > 0

    @pytest.mark.anyio
    async def test_empty_history(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)
        history = await get_trade_history(db_session, sid)
        assert history == []

    @pytest.mark.anyio
    async def test_date_filter(self, db_session, setup_data):
        sid = setup_data["strategy_id"]
        td1, td2 = setup_data["trade_dates"][0], setup_data["trade_dates"][1]

        await db_session.execute(text("DELETE FROM virtual_trades"))
        await db_session.execute(text("DELETE FROM virtual_positions"))
        await db_session.execute(text("DELETE FROM virtual_accounts"))
        await db_session.commit()

        await create_account(db_session, sid)

        # 两天各做一笔交易
        await execute_signals(
            db_session, sid,
            [{"etf_code": "510300", "signal": "BUY", "target_weight": 0.3}],
            td1,
        )
        await execute_signals(
            db_session, sid,
            [{"etf_code": "510500", "signal": "BUY", "target_weight": 0.3}],
            td2,
        )

        # 只查 td1
        history = await get_trade_history(db_session, sid, start_date=td1, end_date=td1)
        assert len(history) == 1
        assert history[0]["trade_date"] == td1.isoformat()


# ---------- API 集成测试 ----------

class TestVirtualAPI:
    @pytest.mark.anyio
    async def test_start_endpoint(self, api_client, setup_data):
        sid = setup_data["strategy_id"]
        # 先清理
        from backend.app.database import get_db
        from backend.app.main import app
        from sqlalchemy import text as sa_text

        resp = await api_client.post(f"/api/v1/strategies/{sid}/virtual/start")
        data = resp.json()
        assert data["code"] == 0 or data["code"] == 400  # 0=成功, 400=已存在

    @pytest.mark.anyio
    async def test_summary_endpoint(self, api_client, setup_data):
        sid = setup_data["strategy_id"]
        resp = await api_client.get(f"/api/v1/strategies/{sid}/virtual/summary")
        data = resp.json()
        # 可能成功（有账户）或 404（无账户）
        assert data["code"] in (0, 404)

    @pytest.mark.anyio
    async def test_trades_endpoint(self, api_client, setup_data):
        sid = setup_data["strategy_id"]
        resp = await api_client.get(f"/api/v1/strategies/{sid}/virtual/trades")
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    @pytest.mark.anyio
    async def test_nav_endpoint(self, api_client, setup_data):
        sid = setup_data["strategy_id"]
        resp = await api_client.get(f"/api/v1/strategies/{sid}/virtual/nav")
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    @pytest.mark.anyio
    async def test_start_nonexistent_strategy(self, api_client):
        resp = await api_client.post("/api/v1/strategies/99999/virtual/start")
        data = resp.json()
        assert data["code"] == 404
