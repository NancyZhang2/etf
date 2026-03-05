"""
Research 服务层单元测试
"""

import pytest

from backend.app.services.research import (
    _extract_etf_codes_from_text,
    _majority_vote,
    _sentiment_to_score,
    generate_mock_analysis,
    generate_mock_reports,
)


class TestExtractEtfCodes:
    def test_extract_single_code(self):
        text = "沪深300ETF(510300)投资策略"
        codes = _extract_etf_codes_from_text(text)
        assert "510300" in codes

    def test_extract_multiple_codes(self):
        text = "510300和510500的动量对比分析，以及159915的表现"
        codes = _extract_etf_codes_from_text(text)
        assert "510300" in codes
        assert "510500" in codes
        assert "159915" in codes

    def test_extract_no_codes(self):
        text = "市场走势分析报告"
        codes = _extract_etf_codes_from_text(text)
        assert codes == []

    def test_extract_dedup(self):
        text = "510300对比510300"
        codes = _extract_etf_codes_from_text(text)
        assert codes == ["510300"]

    def test_extract_sz_codes(self):
        text = "159919和159920"
        codes = _extract_etf_codes_from_text(text)
        assert "159919" in codes
        assert "159920" in codes


class TestMajorityVote:
    def test_single_item(self):
        assert _majority_vote(["expanding"]) == "expanding"

    def test_majority(self):
        items = ["expanding", "stable", "expanding", "contracting", "expanding"]
        assert _majority_vote(items) == "expanding"

    def test_empty(self):
        assert _majority_vote([]) == ""

    def test_tie_returns_one(self):
        items = ["expanding", "stable"]
        result = _majority_vote(items)
        assert result in ("expanding", "stable")


class TestSentimentToScore:
    def test_all_bullish(self):
        score = _sentiment_to_score(["bullish", "bullish", "bullish"])
        assert score == 8.0

    def test_all_bearish(self):
        score = _sentiment_to_score(["bearish", "bearish", "bearish"])
        assert score == 2.0

    def test_all_neutral(self):
        score = _sentiment_to_score(["neutral", "neutral"])
        assert score == 5.0

    def test_mixed(self):
        score = _sentiment_to_score(["bullish", "bearish"])
        assert score == 5.0  # (8+2)/2

    def test_empty(self):
        score = _sentiment_to_score([])
        assert score == 5.0


class TestMockAnalysis:
    def test_schema_fields(self):
        analysis = generate_mock_analysis("510300", "沪深300ETF", "宽基")
        assert "summary" in analysis
        assert "etf_relevance" in analysis
        assert "macro_view" in analysis
        assert "risk_factors" in analysis
        assert "key_points" in analysis
        assert "confidence" in analysis

    def test_etf_relevance_fields(self):
        analysis = generate_mock_analysis("510300", "沪深300ETF", "宽基")
        rel = analysis["etf_relevance"]
        assert rel["code"] == "510300"
        assert rel["sentiment"] in ("bullish", "bearish", "neutral")
        assert 0 <= rel["confidence"] <= 1

    def test_macro_view_fields(self):
        analysis = generate_mock_analysis("510300", "沪深300ETF", "宽基")
        macro = analysis["macro_view"]
        assert macro["economy"] in ("expanding", "stable", "contracting")
        assert macro["liquidity"] in ("loose", "neutral", "tight")
        assert macro["policy"] in ("supportive", "neutral", "restrictive")

    def test_deterministic_with_seed(self):
        a1 = generate_mock_analysis("510300", "沪深300ETF", "宽基", seed=100)
        a2 = generate_mock_analysis("510300", "沪深300ETF", "宽基", seed=100)
        assert a1 == a2

    def test_different_seeds(self):
        a1 = generate_mock_analysis("510300", "沪深300ETF", "宽基", seed=100)
        a2 = generate_mock_analysis("510300", "沪深300ETF", "宽基", seed=200)
        # 不同seed可能产生不同结果（不保证一定不同，但结构一致）
        assert "summary" in a1
        assert "summary" in a2


class TestMockReports:
    def test_generates_correct_count(self):
        etf_list = [
            {"code": "510300", "name": "沪深300ETF", "category": "宽基"},
            {"code": "510500", "name": "中证500ETF", "category": "宽基"},
        ]
        reports = generate_mock_reports(etf_list, count=10, seed=42)
        assert len(reports) == 10

    def test_report_fields(self):
        etf_list = [{"code": "510300", "name": "沪深300ETF", "category": "宽基"}]
        reports = generate_mock_reports(etf_list, count=1, seed=42)
        r = reports[0]
        assert "title" in r
        assert "source" in r
        assert "content" in r
        assert "etf_code" in r
        assert "report_date" in r
        assert "analysis" in r

    def test_deterministic(self):
        etf_list = [{"code": "510300", "name": "沪深300ETF", "category": "宽基"}]
        r1 = generate_mock_reports(etf_list, count=5, seed=42)
        r2 = generate_mock_reports(etf_list, count=5, seed=42)
        assert [r["title"] for r in r1] == [r["title"] for r in r2]
