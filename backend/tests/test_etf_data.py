"""
ETF 数据服务单元测试（使用真实数据库）
"""

import pytest

from backend.app.services.etf_data import get_data_status, _classify_etf, _detect_exchange


class TestClassifyEtf:

    def test_broad_base(self):
        assert _classify_etf("沪深300ETF") == "宽基"
        assert _classify_etf("中证500ETF") == "宽基"
        assert _classify_etf("创业板ETF") == "宽基"

    def test_industry(self):
        assert _classify_etf("医药ETF") == "行业"
        assert _classify_etf("证券ETF") == "行业"
        assert _classify_etf("银行ETF") == "行业"

    def test_commodity(self):
        assert _classify_etf("黄金ETF") == "商品"

    def test_bond(self):
        assert _classify_etf("国债ETF") == "债券"

    def test_currency(self):
        assert _classify_etf("货币ETF") == "货币"

    def test_cross_border(self):
        assert _classify_etf("纳指ETF") == "跨境"
        assert _classify_etf("恒生ETF") == "跨境"

    def test_theme(self):
        assert _classify_etf("人工智能ETF") == "主题"

    def test_default(self):
        assert _classify_etf("某某ETF") == "宽基"  # 无法匹配归入宽基


class TestDetectExchange:

    def test_sh(self):
        assert _detect_exchange("510300") == "SH"
        assert _detect_exchange("518880") == "SH"

    def test_sz(self):
        assert _detect_exchange("159915") == "SZ"
        assert _detect_exchange("159928") == "SZ"


@pytest.mark.asyncio
async def test_get_data_status(db_session):
    """数据状态查询"""
    status = await get_data_status(db_session)
    assert status["etf_count"] >= 20
    assert status["record_count"] > 10000
    assert status["status"] == "ok"
