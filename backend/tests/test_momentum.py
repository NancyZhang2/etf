"""
动量策略 + 回测引擎测试
"""

import pytest
import pandas as pd
import numpy as np

from backend.app.services.strategies.momentum import MomentumStrategy
from backend.app.services.backtest import BacktestEngine


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
            "volume": np.random.randint(1e6, 1e8, n_days),
        })
        data[code] = df
    return data


class TestMomentumStrategy:

    def test_default_params(self):
        s = MomentumStrategy()
        assert s.params["lookback"] == 20
        assert s.params["hold_count"] == 3
        assert s.params["rebalance_period"] == 5

    def test_etf_pool(self):
        s = MomentumStrategy()
        pool = s.get_etf_pool()
        assert len(pool) == 10
        assert "510300" in pool

    def test_strategy_type(self):
        s = MomentumStrategy()
        assert s.strategy_type == "momentum"
        assert "动量" in s.strategy_name

    def test_generate_signals(self):
        s = MomentumStrategy()
        codes = s.get_etf_pool() + [s.params["hedge_etf"]]
        data = _make_sample_data(codes, n_days=100)

        weights = s.generate_signals(data)
        assert not weights.empty
        assert weights.shape[0] == 100
        # 权重之和应为0或1（允许浮点误差）
        row_sums = weights.sum(axis=1)
        for val in row_sums:
            assert val < 1.01, f"权重和超过1: {val}"

    def test_custom_params(self):
        s = MomentumStrategy(params={"lookback": 10, "hold_count": 2,
                                      "rebalance_period": 3, "hedge_threshold": -0.03,
                                      "hedge_etf": "511880"})
        assert s.params["lookback"] == 10
        assert s.params["hold_count"] == 2


class TestBacktestEngine:

    def test_basic_backtest(self):
        engine = BacktestEngine()
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        np.random.seed(42)

        # 两个资产
        close = pd.DataFrame({
            "A": np.cumsum(np.random.randn(200) * 0.01) + 10,
            "B": np.cumsum(np.random.randn(200) * 0.01) + 10,
        }, index=dates)

        # 等权持有
        weights = pd.DataFrame({
            "A": [0.5] * 200,
            "B": [0.5] * 200,
        }, index=dates)

        result = engine.run_backtest(close, weights)

        assert "total_return" in result
        assert "annual_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert result["total_trades"] >= 0

    def test_empty_data(self):
        engine = BacktestEngine()
        close = pd.DataFrame()
        weights = pd.DataFrame()
        result = engine.run_backtest(close, weights)
        assert result["total_return"] == 0

    def test_yearly_backtest(self):
        engine = BacktestEngine()
        dates = pd.date_range("2022-01-01", periods=500, freq="B")
        np.random.seed(42)

        close = pd.DataFrame({
            "A": np.cumsum(np.random.randn(500) * 0.01) + 10,
        }, index=dates)

        weights = pd.DataFrame({
            "A": [1.0] * 500,
        }, index=dates)

        yearly = engine.run_yearly_backtest(close, weights, years=3)
        assert len(yearly) > 0
        assert all("year" in y for y in yearly)

    def test_benchmark_comparison(self):
        engine = BacktestEngine()
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        np.random.seed(42)

        close = pd.DataFrame({
            "A": np.cumsum(np.random.randn(200) * 0.01) + 10,
            "bench": np.cumsum(np.random.randn(200) * 0.01) + 10,
        }, index=dates)

        weights = pd.DataFrame({
            "A": [1.0] * 200,
            "bench": [0.0] * 200,
        }, index=dates)

        result = engine.run_backtest(close, weights, benchmark_code="bench")
        assert "benchmark_return" in result
        assert "excess_return" in result
