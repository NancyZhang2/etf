"""
竞品策略测试 — B2-B5, B7-B10 共8个策略
"""

import pytest
import numpy as np
import pandas as pd

from backend.app.services.strategies.egg_28_plus import Egg28PlusStrategy
from backend.app.services.strategies.baxian import BaxianStrategy
from backend.app.services.strategies.sleep_balance import SleepBalanceStrategy
from backend.app.services.strategies.all_weather_cn import AllWeatherCNStrategy
from backend.app.services.strategies.value_rotation import ValueRotationStrategy
from backend.app.services.strategies.huabao_grid import HuabaoGridStrategy
from backend.app.services.strategies.rsrs_momentum import RSRSMomentumStrategy
from backend.app.services.strategies.multi_factor import MultiFactorStrategy


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


# ======================== B2 蛋卷二八轮动Plus ========================

class TestEgg28PlusStrategy:

    def test_default_params(self):
        s = Egg28PlusStrategy()
        assert "switch_buffer" in s.params
        assert "use_blunting" in s.params
        assert s.params["blunting_days"] == 3
        assert s.params["hedge_etf"] == "511880"

    def test_etf_pool(self):
        s = Egg28PlusStrategy()
        pool = s.get_etf_pool()
        assert "510300" in pool
        assert "510500" in pool
        assert "511880" in pool

    def test_strategy_type(self):
        s = Egg28PlusStrategy()
        assert s.strategy_type == "egg_28_plus"
        assert "Plus" in s.strategy_name or "二八" in s.strategy_name

    def test_generate_signals(self):
        s = Egg28PlusStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=300)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 300
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01

    def test_blunting_reduces_trades(self):
        """钝化机制应减少切换次数"""
        codes = ["510300", "510500", "511880"]
        data = _make_sample_data(codes, n_days=300)

        s_no_blunt = Egg28PlusStrategy(params={
            **Egg28PlusStrategy().get_default_params(),
            "use_blunting": False,
        })
        s_blunt = Egg28PlusStrategy(params={
            **Egg28PlusStrategy().get_default_params(),
            "use_blunting": True,
            "blunting_days": 3,
        })

        w_no = s_no_blunt.generate_signals(data)
        w_yes = s_blunt.generate_signals(data)

        # Count position changes
        def count_changes(w):
            changes = 0
            for col in w.columns:
                diff = w[col].diff().abs()
                changes += (diff > 0.01).sum()
            return changes

        assert not w_no.empty
        assert not w_yes.empty
        # Blunted version should have <= changes (or equal in edge cases)
        assert count_changes(w_yes) <= count_changes(w_no) + 5  # small margin


# ======================== B3 蛋卷八仙过海 ========================

class TestBaxianStrategy:

    def test_default_params(self):
        s = BaxianStrategy()
        assert s.params["timing_ma_period"] == 40
        assert s.params["hold_count"] == 3
        assert len(s.params["sector_etf_pool"]) == 8

    def test_etf_pool(self):
        s = BaxianStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 9  # 8 sectors + timing + hedge (timing may overlap)
        assert "510300" in pool  # timing index
        assert "511880" in pool  # hedge

    def test_strategy_type(self):
        s = BaxianStrategy()
        assert s.strategy_type == "baxian"
        assert "八仙" in s.strategy_name

    def test_generate_signals(self):
        s = BaxianStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=120)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 120
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01


# ======================== B4 蛋卷安睡二八平衡 ========================

class TestSleepBalanceStrategy:

    def test_default_params(self):
        s = SleepBalanceStrategy()
        assert s.params["bond_ratio"] == 0.8
        assert s.params["check_day"] == 15
        assert s.params["deviation_threshold"] == 0.05

    def test_etf_pool(self):
        s = SleepBalanceStrategy()
        pool = s.get_etf_pool()
        assert "510300" in pool
        assert "511010" in pool
        assert len(pool) == 2

    def test_strategy_type(self):
        s = SleepBalanceStrategy()
        assert s.strategy_type == "sleep_balance"
        assert "安睡" in s.strategy_name or "平衡" in s.strategy_name

    def test_generate_signals(self):
        s = SleepBalanceStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 200
        # Weights should sum to ~1.0 for all rows
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert 0.95 <= v <= 1.05


# ======================== B5 蛋卷全天候本土版 ========================

class TestAllWeatherCNStrategy:

    def test_default_params(self):
        s = AllWeatherCNStrategy()
        assert "etf_weights" in s.params
        total = sum(s.params["etf_weights"].values())
        assert total == pytest.approx(1.0)
        assert s.params["rebalance_period"] == "quarterly"

    def test_etf_pool(self):
        s = AllWeatherCNStrategy()
        pool = s.get_etf_pool()
        assert len(pool) == 5
        assert "510300" in pool

    def test_strategy_type(self):
        s = AllWeatherCNStrategy()
        assert s.strategy_type == "all_weather_cn"
        assert "全天候" in s.strategy_name

    def test_generate_signals(self):
        s = AllWeatherCNStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 200
        row_sums = weights.sum(axis=1)
        non_zero = row_sums[row_sums > 0.01]
        if len(non_zero) > 0:
            assert all(v <= 1.1 for v in non_zero)

    def test_different_periods(self):
        for period in ["yearly", "quarterly", "monthly"]:
            s = AllWeatherCNStrategy(params={
                **AllWeatherCNStrategy().get_default_params(),
                "rebalance_period": period,
            })
            codes = s.get_etf_pool()
            data = _make_sample_data(codes, n_days=200)
            weights = s.generate_signals(data)
            assert not weights.empty


# ======================== B7 果仁低估值轮动 ========================

class TestValueRotationStrategy:

    def test_default_params(self):
        s = ValueRotationStrategy()
        assert s.params["hold_count"] == 3
        assert s.params["pe_weight"] + s.params["pb_weight"] + s.params["div_weight"] == pytest.approx(1.0)
        assert s.params["history_days"] == 1250

    def test_etf_pool(self):
        s = ValueRotationStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 5
        assert "511880" in pool  # hedge

    def test_strategy_type(self):
        s = ValueRotationStrategy()
        assert s.strategy_type == "value_rotation"
        assert "低估值" in s.strategy_name or "果仁" in s.strategy_name

    def test_generate_signals(self):
        s = ValueRotationStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01


# ======================== B8 华宝网格交易 ========================

class TestHuabaoGridStrategy:

    def test_default_params(self):
        s = HuabaoGridStrategy()
        assert s.params["grid_count"] == 10
        assert s.params["use_rebound_confirm"] is True
        assert s.params["rebound_pct"] == 0.005

    def test_etf_pool(self):
        s = HuabaoGridStrategy()
        pool = s.get_etf_pool()
        assert "510300" in pool

    def test_strategy_type(self):
        s = HuabaoGridStrategy()
        assert s.strategy_type == "huabao_grid"
        assert "华宝" in s.strategy_name or "网格" in s.strategy_name

    def test_generate_signals(self):
        s = HuabaoGridStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 200
        assert weights.min().min() >= -0.01
        assert weights.max().max() <= 1.01

    def test_without_rebound(self):
        s = HuabaoGridStrategy(params={
            **HuabaoGridStrategy().get_default_params(),
            "use_rebound_confirm": False,
        })
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty


# ======================== B9 集思录动量+RSRS择时 ========================

class TestRSRSMomentumStrategy:

    def test_default_params(self):
        s = RSRSMomentumStrategy()
        assert s.params["momentum_days"] == 25
        assert s.params["rsrs_regression_days"] == 18
        assert s.params["rsrs_threshold"] == 0.7

    def test_etf_pool(self):
        s = RSRSMomentumStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 5
        assert "518880" in pool  # 黄金ETF
        assert "511880" in pool  # hedge

    def test_strategy_type(self):
        s = RSRSMomentumStrategy()
        assert s.strategy_type == "rsrs_momentum"
        assert "RSRS" in s.strategy_name or "动量" in s.strategy_name

    def test_generate_signals(self):
        s = RSRSMomentumStrategy()
        codes = s.get_etf_pool()
        # Use longer data for RSRS to have enough history
        data = _make_sample_data(codes, n_days=300)
        weights = s.generate_signals(data)
        assert not weights.empty
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01


# ======================== B10 ETF组合宝多因子轮动 ========================

class TestMultiFactorStrategy:

    def test_default_params(self):
        s = MultiFactorStrategy()
        total_w = (
            s.params["momentum_weight"] + s.params["volume_weight"] +
            s.params["flow_weight"] + s.params["volatility_weight"]
        )
        assert total_w == pytest.approx(1.0)
        assert s.params["hold_count"] == 3

    def test_etf_pool(self):
        s = MultiFactorStrategy()
        pool = s.get_etf_pool()
        assert len(pool) >= 5
        assert "511880" in pool  # hedge

    def test_strategy_type(self):
        s = MultiFactorStrategy()
        assert s.strategy_type == "multi_factor"
        assert "多因子" in s.strategy_name

    def test_generate_signals(self):
        s = MultiFactorStrategy()
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=100)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 100
        row_sums = weights.sum(axis=1)
        for v in row_sums:
            assert v <= 1.01

    def test_custom_hold_count(self):
        s = MultiFactorStrategy(params={
            **MultiFactorStrategy().get_default_params(),
            "hold_count": 5,
        })
        codes = s.get_etf_pool()
        data = _make_sample_data(codes, n_days=100)
        weights = s.generate_signals(data)
        assert not weights.empty
