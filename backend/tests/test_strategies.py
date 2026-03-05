"""
Phase 2 策略测试 — 均线趋势/网格/资产配置/蛋卷二八/果仁轮动
"""

import pytest
import numpy as np
import pandas as pd

from backend.app.services.strategies.ma_trend import MATrendStrategy
from backend.app.services.strategies.grid import GridStrategy
from backend.app.services.strategies.asset_alloc import AssetAllocStrategy
from backend.app.services.strategies.egg_28 import Egg28Strategy
from backend.app.services.strategies.guorn_rotation import GuornRotationStrategy


def _make_sample_data(codes, n_days=200):
    """生成测试用价格数据"""
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    data = {}
    for i, code in enumerate(codes):
        np.random.seed(42 + i)
        prices = np.cumsum(np.random.randn(n_days) * 0.01) + 5
        prices = np.maximum(prices, 0.1)
        df = pd.DataFrame({
            "date": dates,
            "open": prices * (1 + np.random.randn(n_days) * 0.005),
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1_000_000, 100_000_000, n_days),
        })
        data[code] = df
    return data


# ======================== 均线趋势 A2 ========================

class TestMATrendStrategy:

    def test_default_params(self):
        s = MATrendStrategy()
        assert s.params["fast_period"] == 10
        assert s.params["slow_period"] == 30
        assert s.params["mode"] == "dual"

    def test_etf_pool(self):
        s = MATrendStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 3
        assert "510300" in pool

    def test_strategy_type(self):
        s = MATrendStrategy()
        assert s.strategy_type == "ma_trend"
        assert "均线" in s.strategy_name

    def test_generate_signals(self):
        s = MATrendStrategy()
        codes = s.get_etf_pool() + [s.params.get("hedge_etf", "511880")]
        data = _make_sample_data(codes, n_days=120)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 120
        row_sums = weights.sum(axis=1)
        assert all(v <= 1.01 for v in row_sums)

    def test_single_mode(self):
        s = MATrendStrategy(params={
            "mode": "single", "long_window": 20, "short_window": 5,
            "market_filter": True, "market_ma_window": 250,
            "hedge_etf": "511880",
        })
        codes = s.get_etf_pool() + ["511880"]
        data = _make_sample_data(codes, n_days=120)
        weights = s.generate_signals(data)
        assert not weights.empty


# ======================== 网格交易 A3 ========================

class TestGridStrategy:

    def test_default_params(self):
        s = GridStrategy()
        assert s.params["grid_count"] == 10
        assert s.params["grid_type"] == "arithmetic"

    def test_etf_pool(self):
        s = GridStrategy()
        pool = s.get_etf_pool()
        assert "510300" in pool

    def test_strategy_type(self):
        s = GridStrategy()
        assert s.strategy_type == "grid"
        assert "网格" in s.strategy_name

    def test_generate_signals(self):
        s = GridStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 200
        # 网格策略权重在0~1之间
        assert weights.min().min() >= -0.01
        assert weights.max().max() <= 1.01

    def test_geometric_grid(self):
        s = GridStrategy(params={
            "grid_count": 8, "grid_type": "geometric",
            "price_range_pct": 0.3, "target_etf": "510300",
        })
        data = _make_sample_data(["510300"], n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty


# ======================== 大类资产配置 A4 ========================

class TestAssetAllocStrategy:

    def test_default_params(self):
        s = AssetAllocStrategy()
        assert s.params["model"] == "all_weather"
        assert s.params["rebalance_period"] >= 1

    def test_etf_pool(self):
        s = AssetAllocStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 3
        assert "510300" in pool

    def test_strategy_type(self):
        s = AssetAllocStrategy()
        assert s.strategy_type == "asset_alloc"
        assert "资产" in s.strategy_name

    def test_generate_signals_all_weather(self):
        s = AssetAllocStrategy()  # use default params (includes etf_weights)
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        row_sums = weights.sum(axis=1)
        # 全天候策略权重和应接近1
        non_zero = row_sums[row_sums > 0.01]
        if len(non_zero) > 0:
            assert all(v <= 1.1 for v in non_zero)

    def test_risk_parity_model(self):
        defaults = AssetAllocStrategy().get_default_params()
        defaults["model"] = "risk_parity"
        s = AssetAllocStrategy(params=defaults)
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty

    def test_stock_bond_model(self):
        s = AssetAllocStrategy(params={
            "model": "stock_bond", "rebalance_period": 20,
            "stock_etf": "510300", "bond_etf": "511010",
            "base_stock_ratio": 0.6,
        })
        codes = ["510300", "511010"]
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty


# ======================== 蛋卷二八轮动 B1 ========================

class TestEgg28Strategy:

    def test_default_params(self):
        s = Egg28Strategy()
        assert "switch_buffer" in s.params
        assert "use_ma_protection" in s.params
        assert s.params["hedge_etf"] == "511880"

    def test_etf_pool(self):
        s = Egg28Strategy()
        pool = s.get_etf_pool()
        assert "510300" in pool
        assert "510500" in pool

    def test_strategy_type(self):
        s = Egg28Strategy()
        assert s.strategy_type == "egg_28"
        assert "蛋卷" in s.strategy_name or "二八" in s.strategy_name

    def test_generate_signals(self):
        s = Egg28Strategy()
        codes = s.get_etf_pool() + [s.params["hedge_etf"]]
        data = _make_sample_data(codes, n_days=300)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 300
        # 二八策略单只ETF全仓或空仓
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01


# ======================== 果仁行业轮动 B2 ========================

class TestGuornRotationStrategy:

    def test_default_params(self):
        s = GuornRotationStrategy()
        assert s.params["hold_count"] == 3
        assert s.params["lookback_days"] == 20
        assert s.params["momentum_weight"] + s.params["volume_weight"] == pytest.approx(1.0)

    def test_etf_pool(self):
        s = GuornRotationStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 5
        assert "512880" in pool  # 证券ETF

    def test_strategy_type(self):
        s = GuornRotationStrategy()
        assert s.strategy_type == "guorn_rotation"
        assert "果仁" in s.strategy_name

    def test_generate_signals(self):
        s = GuornRotationStrategy()
        codes = s.get_etf_pool() + [s.params["hedge_etf"]]
        data = _make_sample_data(codes, n_days=100)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 100
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01

    def test_custom_hold_count(self):
        s = GuornRotationStrategy(params={
            "hold_count": 5, "lookback_days": 10,
            "rebalance_period": 3, "momentum_weight": 0.5,
            "volume_weight": 0.5, "momentum_threshold": 0.0,
            "hedge_etf": "511880",
        })
        codes = s.get_etf_pool() + ["511880"]
        data = _make_sample_data(codes, n_days=100)
        weights = s.generate_signals(data)
        assert not weights.empty
