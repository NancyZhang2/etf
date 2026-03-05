"""
Quant 模块 API 测试 — 策略/回测/信号端点
"""

import pytest


@pytest.mark.asyncio
async def test_strategy_list(api_client):
    """策略列表应返回6个策略"""
    resp = await api_client.get("/api/v1/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) == 6


@pytest.mark.asyncio
async def test_strategy_list_by_category(api_client):
    """按分类筛选策略"""
    resp = await api_client.get("/api/v1/strategies")
    data = resp.json()
    if data["data"]:
        # 找到第一个策略的分类
        first = data["data"][0]
        # 也能通过分类过滤（如果有category_id参数）
        assert "strategy_type" in first
        assert "name" in first


@pytest.mark.asyncio
async def test_strategy_detail(api_client):
    """策略详情"""
    resp = await api_client.get("/api/v1/strategies")
    strategies = resp.json()["data"]
    for s in strategies:
        detail_resp = await api_client.get(f"/api/v1/strategies/{s['id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["code"] == 0
        assert detail["data"]["strategy_type"] == s["strategy_type"]
        assert detail["data"]["params"] is not None


@pytest.mark.asyncio
async def test_strategy_detail_not_found(api_client):
    """不存在的策略"""
    resp = await api_client.get("/api/v1/strategies/9999")
    data = resp.json()
    assert data["code"] == 404


@pytest.mark.asyncio
async def test_backtest_all_strategies(api_client):
    """每个策略都有回测结果"""
    resp = await api_client.get("/api/v1/strategies")
    strategies = resp.json()["data"]

    for s in strategies:
        bt_resp = await api_client.get(f"/api/v1/strategies/{s['id']}/backtest")
        assert bt_resp.status_code == 200
        bt = bt_resp.json()
        assert bt["code"] == 0, f"策略 {s['name']} 无回测结果"
        data = bt["data"]
        assert "annual_return" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data
        assert data["year"] == 0  # 全区间


@pytest.mark.asyncio
async def test_backtest_yearly(api_client):
    """逐年回测结果"""
    resp = await api_client.get("/api/v1/strategies")
    strategies = resp.json()["data"]

    for s in strategies:
        yr_resp = await api_client.get(f"/api/v1/strategies/{s['id']}/backtest/yearly")
        assert yr_resp.status_code == 200
        yr = yr_resp.json()
        assert yr["code"] == 0, f"策略 {s['name']} 无逐年回测"
        assert len(yr["data"]) >= 1
        for item in yr["data"]:
            assert item["year"] > 0
            assert "annual_return" in item
            assert "sharpe_ratio" in item


@pytest.mark.asyncio
async def test_backtest_specific_year(api_client):
    """查询特定年份回测"""
    resp = await api_client.get("/api/v1/strategies")
    sid = resp.json()["data"][0]["id"]
    yr_resp = await api_client.get(f"/api/v1/strategies/{sid}/backtest?year=2024")
    data = yr_resp.json()
    if data["code"] == 0:
        assert data["data"]["year"] == 2024


@pytest.mark.asyncio
async def test_signals_latest(api_client):
    """最新信号"""
    resp = await api_client.get("/api/v1/signals/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) > 0
    sig = data["data"][0]
    assert "strategy_name" in sig
    assert "etf_code" in sig
    assert sig["signal"] in ("BUY", "SELL", "HOLD")


@pytest.mark.asyncio
async def test_signals_latest_filter(api_client):
    """按策略过滤信号"""
    resp = await api_client.get("/api/v1/strategies")
    sid = resp.json()["data"][0]["id"]
    resp2 = await api_client.get(f"/api/v1/signals/latest?strategy_id={sid}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_signals_history(api_client):
    """信号历史"""
    resp = await api_client.get("/api/v1/signals/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_portfolio(api_client):
    """虚拟持仓端点可访问"""
    resp = await api_client.get("/api/v1/strategies")
    sid = resp.json()["data"][0]["id"]
    resp2 = await api_client.get(f"/api/v1/strategies/{sid}/portfolio")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_custom_backtest(api_client):
    """自定义参数回测"""
    # 找到动量策略
    resp = await api_client.get("/api/v1/strategies")
    strategies = resp.json()["data"]
    momentum = next((s for s in strategies if s["strategy_type"] == "momentum"), None)
    if not momentum:
        pytest.skip("No momentum strategy found")

    resp2 = await api_client.post(
        f"/api/v1/strategies/{momentum['id']}/backtest",
        json={"params": {"lookback": 10, "hold_count": 2}},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["code"] == 0
    assert "annual_return" in data["data"]
    assert "sharpe_ratio" in data["data"]


@pytest.mark.asyncio
async def test_signals_calendar_not_impl(api_client):
    """信号日历尚未实现"""
    resp = await api_client.get("/api/v1/signals/calendar")
    data = resp.json()
    assert data["code"] == 501


@pytest.mark.asyncio
async def test_optimize_not_impl(api_client):
    """参数优化尚未实现"""
    resp = await api_client.post("/api/v1/strategies/1/optimize")
    data = resp.json()
    assert data["code"] == 501
