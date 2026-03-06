"""
B5. 蛋卷全天候本土版
- 桥水全天候A股本土化：固定权重配置 + 年度/季度/月度再平衡
- 偏离阈值触发再平衡
- 与A4 all_weather区别：不同默认ETF池、支持多种再平衡周期
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


REBALANCE_PERIODS = {
    "yearly": 252,
    "quarterly": 63,
    "monthly": 21,
}


class AllWeatherCNStrategy(BaseStrategy):
    """蛋卷全天候本土版"""

    @property
    def strategy_type(self) -> str:
        return "all_weather_cn"

    @property
    def strategy_name(self) -> str:
        return "蛋卷全天候本土版"

    @property
    def description(self) -> str:
        return (
            "桥水全天候策略的A股本土化版本。采用固定权重配置股票、国债、"
            "黄金、红利等资产，支持年度/季度/月度再平衡周期。"
            "当任一资产偏离目标权重超过阈值时自动触发再平衡。"
            "与经典策略A4(大类资产配置)逻辑相似。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "etf_weights": {
                "510300": 0.30,     # 沪深300
                "511010": 0.40,     # 国债ETF
                "511020": 0.15,     # 中期国债
                "518880": 0.075,    # 黄金ETF
                "510880": 0.075,    # 红利ETF
            },
            "rebalance_period": "quarterly",    # yearly / quarterly / monthly
            "deviation_threshold": 0.05,        # 偏离阈值
        }

    def get_etf_pool(self) -> List[str]:
        weights = self.params.get("etf_weights", {})
        return list(weights.keys())

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        etf_weights = self.params.get("etf_weights", {})
        period_name = self.params.get("rebalance_period", "quarterly")
        threshold = self.params.get("deviation_threshold", 0.05)

        rebalance_days = REBALANCE_PERIODS.get(period_name, 63)

        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series

        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        available = [c for c in etf_weights if c in close_df.columns]
        if not available:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # Normalize target weights to available assets
        total_target = sum(etf_weights.get(c, 0) for c in available)
        target = {c: etf_weights[c] / total_target for c in available} if total_target > 0 else {}

        # Track NAV per asset for drift detection
        navs = {c: 1.0 for c in available}
        returns = {c: close_df[c].pct_change().fillna(0) for c in available}
        current_weights = dict(target)

        for i in range(len(close_df)):
            if i > 0:
                # Update NAVs
                for c in available:
                    navs[c] *= (1 + float(returns[c].iloc[i]))

                # Calculate actual weights from drifted NAVs
                total_val = sum(current_weights[c] * navs[c] for c in available)
                if total_val > 0:
                    actual = {c: current_weights[c] * navs[c] / total_val for c in available}
                else:
                    actual = dict(target)
            else:
                actual = dict(target)

            # Check if rebalance needed
            need_rebalance = (i == 0) or (i % rebalance_days == 0)

            # Also rebalance on threshold breach
            if not need_rebalance and i > 0:
                for c in available:
                    if abs(actual.get(c, 0) - target.get(c, 0)) > threshold:
                        need_rebalance = True
                        break

            if need_rebalance:
                for c in available:
                    navs[c] = 1.0
                current_weights = dict(target)
                actual = dict(target)

            for c in available:
                weights.iloc[i, weights.columns.get_loc(c)] = actual.get(c, 0)

        return weights
