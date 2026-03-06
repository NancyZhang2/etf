"""
B4. 蛋卷安睡二八平衡
- 极简股债再平衡：80%债券 + 20%股票
- 每月固定日检查偏离度，超阈值触发再平衡
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class SleepBalanceStrategy(BaseStrategy):
    """蛋卷安睡二八平衡"""

    @property
    def strategy_type(self) -> str:
        return "sleep_balance"

    @property
    def strategy_name(self) -> str:
        return "蛋卷安睡二八平衡"

    @property
    def description(self) -> str:
        return (
            "复刻蛋卷基金安睡二八平衡策略。80%债券+20%股票的极简配置，"
            "每月固定日检查偏离度，超过阈值时自动再平衡恢复目标比例。"
            "适合低风险偏好的长期投资者。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "stock_etf": "510300",          # 股票标的
            "bond_etf": "511010",           # 债券标的
            "bond_ratio": 0.8,              # 债券目标比例
            "check_day": 15,                # 每月检查日（交易日序号）
            "deviation_threshold": 0.05,    # 偏离阈值
        }

    def get_etf_pool(self) -> List[str]:
        return [
            self.params.get("stock_etf", "510300"),
            self.params.get("bond_etf", "511010"),
        ]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        stock_etf = self.params.get("stock_etf", "510300")
        bond_etf = self.params.get("bond_etf", "511010")
        bond_ratio = self.params.get("bond_ratio", 0.8)
        check_day = self.params.get("check_day", 15)
        threshold = self.params.get("deviation_threshold", 0.05)
        stock_ratio = 1.0 - bond_ratio

        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series

        if stock_etf not in close_dict or bond_etf not in close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        stock_ret = close_df[stock_etf].pct_change().fillna(0)
        bond_ret = close_df[bond_etf].pct_change().fillna(0)

        # NAV tracking for deviation detection
        stock_nav = 1.0
        bond_nav = 1.0
        w_stock = stock_ratio
        w_bond = bond_ratio

        # Track month boundaries for check_day
        day_in_month = 0
        prev_month = None

        for i in range(len(close_df)):
            dt = close_df.index[i]
            curr_month = (dt.year, dt.month)

            if curr_month != prev_month:
                day_in_month = 0
                prev_month = curr_month
            day_in_month += 1

            if i > 0:
                stock_nav *= (1 + float(stock_ret.iloc[i]))
                bond_nav *= (1 + float(bond_ret.iloc[i]))

            total_val = w_stock * stock_nav + w_bond * bond_nav
            if total_val > 0:
                actual_stock = w_stock * stock_nav / total_val
            else:
                actual_stock = stock_ratio

            # Check deviation on check_day
            need_rebalance = False
            if day_in_month == check_day:
                if abs(actual_stock - stock_ratio) > threshold:
                    need_rebalance = True

            if need_rebalance or i == 0:
                w_stock = stock_ratio
                w_bond = bond_ratio
                stock_nav = 1.0
                bond_nav = 1.0
                actual_stock = stock_ratio

            weights.iloc[i, weights.columns.get_loc(stock_etf)] = actual_stock
            weights.iloc[i, weights.columns.get_loc(bond_etf)] = 1.0 - actual_stock

        return weights
