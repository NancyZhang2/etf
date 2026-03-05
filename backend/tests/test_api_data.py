"""
Data 模块 API 测试
"""

import pytest


@pytest.mark.asyncio
async def test_etf_list(api_client):
    """ETF列表应返回数据"""
    resp = await api_client.get("/api/v1/etf/list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) >= 20  # 示例数据25只


@pytest.mark.asyncio
async def test_etf_list_filter(api_client):
    """按分类筛选"""
    resp = await api_client.get("/api/v1/etf/list?category=宽基")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert all(e["category"] == "宽基" for e in data["data"])


@pytest.mark.asyncio
async def test_etf_categories(api_client):
    """分类统计"""
    resp = await api_client.get("/api/v1/etf/list/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    categories = {c["category"] for c in data["data"]}
    assert "宽基" in categories
    assert "行业" in categories


@pytest.mark.asyncio
async def test_etf_info(api_client):
    """ETF详情"""
    resp = await api_client.get("/api/v1/etf/510300/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["code"] == "510300"
    assert "沪深300" in data["data"]["name"]


@pytest.mark.asyncio
async def test_etf_info_not_found(api_client):
    """不存在的ETF"""
    resp = await api_client.get("/api/v1/etf/999999/info")
    data = resp.json()
    assert data["code"] == 404


@pytest.mark.asyncio
async def test_etf_daily(api_client):
    """日行情"""
    resp = await api_client.get("/api/v1/etf/510300/daily?start_date=2026-01-01&end_date=2026-03-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) > 0
    row = data["data"][0]
    assert "trade_date" in row
    assert "close" in row


@pytest.mark.asyncio
async def test_etf_latest(api_client):
    """最新行情"""
    resp = await api_client.get("/api/v1/etf/510300/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["trade_date"] == "2026-03-03"


@pytest.mark.asyncio
async def test_etf_batch_daily(api_client):
    """批量行情"""
    resp = await api_client.get("/api/v1/etf/batch/daily?codes=510300,510500&start_date=2026-03-01&end_date=2026-03-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "510300" in data["data"]
    assert "510500" in data["data"]


@pytest.mark.asyncio
async def test_data_status(api_client):
    """数据状态"""
    resp = await api_client.get("/api/v1/data/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["etf_count"] >= 20
    assert data["data"]["record_count"] > 10000
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_data_calendar(api_client):
    """交易日历"""
    resp = await api_client.get("/api/v1/data/calendar?year=2025")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]) > 200  # 一年约244个交易日
