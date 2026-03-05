"""
Research 模块 API 测试
"""

import pytest


@pytest.mark.asyncio
async def test_research_reports_list(api_client):
    """研报列表应返回数据"""
    resp = await api_client.get("/api/v1/research/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "total" in data["data"]
    assert "items" in data["data"]
    assert data["data"]["total"] >= 30


@pytest.mark.asyncio
async def test_research_reports_pagination(api_client):
    """研报列表分页"""
    resp = await api_client.get("/api/v1/research/reports?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert len(data["data"]["items"]) <= 5


@pytest.mark.asyncio
async def test_research_reports_filter_by_etf(api_client):
    """按ETF代码筛选研报"""
    resp = await api_client.get("/api/v1/research/reports?etf_code=510300")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    for item in data["data"]["items"]:
        assert item["etf_code"] == "510300"


@pytest.mark.asyncio
async def test_research_report_detail(api_client):
    """研报详情"""
    # 先获取列表找一个id
    resp = await api_client.get("/api/v1/research/reports?page_size=1")
    items = resp.json()["data"]["items"]
    assert len(items) > 0

    report_id = items[0]["id"]
    detail_resp = await api_client.get(f"/api/v1/research/reports/{report_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["code"] == 0
    assert detail["data"]["id"] == report_id
    assert detail["data"]["title"] is not None
    assert detail["data"]["content"] is not None
    assert detail["data"]["analysis"] is not None


@pytest.mark.asyncio
async def test_research_report_detail_has_analysis(api_client):
    """研报详情包含analysis字段"""
    resp = await api_client.get("/api/v1/research/reports?page_size=1")
    report_id = resp.json()["data"]["items"][0]["id"]

    detail_resp = await api_client.get(f"/api/v1/research/reports/{report_id}")
    analysis = detail_resp.json()["data"]["analysis"]
    assert analysis is not None
    assert "summary" in analysis
    assert "etf_relevance" in analysis
    assert "macro_view" in analysis


@pytest.mark.asyncio
async def test_research_report_not_found(api_client):
    """不存在的研报返回404"""
    resp = await api_client.get("/api/v1/research/reports/99999")
    data = resp.json()
    assert data["code"] == 404


@pytest.mark.asyncio
async def test_research_framework(api_client):
    """投资框架查询"""
    resp = await api_client.get("/api/v1/research/510300/framework")
    assert resp.status_code == 200
    data = resp.json()
    # 可能有也可能无框架（取决于样本数据是否覆盖510300）
    if data["code"] == 0:
        fw = data["data"]
        assert fw["etf_code"] == "510300"
        assert fw["fundamental_score"] is not None
        assert fw["technical_score"] is not None
        assert fw["sentiment_score"] is not None
        assert fw["overall_score"] is not None


@pytest.mark.asyncio
async def test_research_framework_not_found(api_client):
    """不存在的ETF框架返回404"""
    resp = await api_client.get("/api/v1/research/999999/framework")
    data = resp.json()
    assert data["code"] == 404


@pytest.mark.asyncio
async def test_research_sentiment(api_client):
    """情绪统计查询"""
    resp = await api_client.get("/api/v1/research/510300/sentiment")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    sentiment = data["data"]
    assert "bullish_count" in sentiment
    assert "bearish_count" in sentiment
    assert "neutral_count" in sentiment
    assert "overall_sentiment" in sentiment
    assert sentiment["overall_sentiment"] in ("bullish", "bearish", "neutral")


@pytest.mark.asyncio
async def test_research_sentiment_etf_with_reports(api_client):
    """有研报的ETF应有情绪数据"""
    # 找一个有研报的ETF
    resp = await api_client.get("/api/v1/research/reports?page_size=1")
    items = resp.json()["data"]["items"]
    if items and items[0]["etf_code"]:
        etf_code = items[0]["etf_code"]
        resp2 = await api_client.get(f"/api/v1/research/{etf_code}/sentiment")
        data = resp2.json()
        assert data["code"] == 0
        total = data["data"]["bullish_count"] + data["data"]["bearish_count"] + data["data"]["neutral_count"]
        assert total >= 1


@pytest.mark.asyncio
async def test_research_macro(api_client):
    """宏观共识查询"""
    resp = await api_client.get("/api/v1/research/macro")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    macro = data["data"]
    assert "economy" in macro
    assert "liquidity" in macro
    assert "policy" in macro
    assert "key_points" in macro
    assert "risk_factors" in macro
    assert macro["economy"] in ("expanding", "stable", "contracting")
    assert macro["liquidity"] in ("loose", "neutral", "tight")
    assert macro["policy"] in ("supportive", "neutral", "restrictive")


@pytest.mark.asyncio
async def test_research_macro_has_points(api_client):
    """宏观共识应包含要点和风险"""
    resp = await api_client.get("/api/v1/research/macro")
    macro = resp.json()["data"]
    assert isinstance(macro["key_points"], list)
    assert isinstance(macro["risk_factors"], list)
    assert len(macro["key_points"]) > 0
    assert len(macro["risk_factors"]) > 0


@pytest.mark.asyncio
async def test_research_crawl_trigger(api_client):
    """POST触发爬取"""
    resp = await api_client.post("/api/v1/research/crawl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_research_framework_update_trigger(api_client):
    """POST触发框架更新"""
    resp = await api_client.post("/api/v1/research/framework/update")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
