"""
信号生成服务测试
"""

import pytest
import numpy as np
import pandas as pd

from backend.app.services.strategies.momentum import MomentumStrategy
from backend.app.services.strategies.ma_trend import MATrendStrategy
from backend.app.services.strategies.grid import GridStrategy
from backend.app.services.strategies.asset_alloc import AssetAllocStrategy
from backend.app.services.strategies.egg_28 import Egg28Strategy
from backend.app.services.strategies.guorn_rotation import GuornRotationStrategy


def _make_sample_data(codes, n_days=200):
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


class TestSignalGeneration:
    """测试各策略的信号生成能力"""

    @pytest.mark.parametrize("cls,extra_params", [
        (MomentumStrategy, {}),
        (MATrendStrategy, {}),
        (GridStrategy, {}),
        (AssetAllocStrategy, {}),
        (Egg28Strategy, {}),
        (GuornRotationStrategy, {}),
    ])
    def test_strategy_produces_signals(self, cls, extra_params):
        """所有策略都能生成非空权重矩阵"""
        s = cls(params=extra_params) if extra_params else cls()
        codes = s.get_etf_pool() + [s.params.get("hedge_etf", "511880")]
        codes = list(set(codes))
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] > 0

    @pytest.mark.parametrize("cls", [
        MomentumStrategy, MATrendStrategy, GridStrategy,
        AssetAllocStrategy, Egg28Strategy, GuornRotationStrategy,
    ])
    def test_strategy_weights_bounded(self, cls):
        """权重值在合理范围 [0, 1]"""
        s = cls()
        codes = s.get_etf_pool() + [s.params.get("hedge_etf", "511880")]
        codes = list(set(codes))
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        if weights.empty:
            pytest.skip("empty weights")
        assert weights.min().min() >= -0.01, "权重出现负值"
        assert weights.max().max() <= 1.01, "单只权重超过100%"

    @pytest.mark.parametrize("cls", [
        MomentumStrategy, MATrendStrategy, GridStrategy,
        AssetAllocStrategy, Egg28Strategy, GuornRotationStrategy,
    ])
    def test_strategy_row_sum(self, cls):
        """每行权重和不超过1（允许全空仓=0）"""
        s = cls()
        codes = s.get_etf_pool() + [s.params.get("hedge_etf", "511880")]
        codes = list(set(codes))
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)
        if weights.empty:
            pytest.skip("empty weights")
        row_sums = weights.sum(axis=1)
        assert all(v <= 1.05 for v in row_sums), f"Max row sum: {row_sums.max()}"

    def test_all_strategies_have_required_props(self):
        """所有策略都有必要属性"""
        for cls in [MomentumStrategy, MATrendStrategy, GridStrategy,
                    AssetAllocStrategy, Egg28Strategy, GuornRotationStrategy]:
            s = cls()
            assert s.strategy_type, f"{cls.__name__} missing strategy_type"
            assert s.strategy_name, f"{cls.__name__} missing strategy_name"
            assert s.description, f"{cls.__name__} missing description"
            assert s.get_default_params(), f"{cls.__name__} missing default_params"
            assert s.get_etf_pool(), f"{cls.__name__} missing etf_pool"

    def test_empty_data_handling(self):
        """空数据不应崩溃"""
        for cls in [MomentumStrategy, MATrendStrategy, GridStrategy,
                    AssetAllocStrategy, Egg28Strategy, GuornRotationStrategy]:
            s = cls()
            weights = s.generate_signals({})
            assert weights.empty

    def test_signal_direction_change(self):
        """验证信号能检测到方向变化（BUY/SELL逻辑）"""
        s = MomentumStrategy()
        codes = s.get_etf_pool() + [s.params["hedge_etf"]]
        data = _make_sample_data(codes, n_days=200)
        weights = s.generate_signals(data)

        if weights.empty or len(weights) < 2:
            pytest.skip("Not enough data")

        # 找到权重变化的点
        changes = 0
        for col in weights.columns:
            diff = weights[col].diff().abs()
            changes += (diff > 0.01).sum()

        # 至少应该有一些调仓
        assert changes > 0, "策略没有产生任何调仓"
