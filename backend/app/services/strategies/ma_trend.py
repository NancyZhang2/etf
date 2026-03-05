"""
A2. 均线趋势策略
- 单均线/双均线交叉 + 大盘过滤器
- 单均线: 收盘价 > MA → 持有, < MA → 空仓
- 双均线: 快线上穿慢线 → 买入, 下穿 → 卖出
- 大盘过滤: 沪深300低于长期均线时强制空仓
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class MATrendStrategy(BaseStrategy):
    """均线趋势策略"""

    @property
    def strategy_type(self) -> str:
        return "ma_trend"

    @property
    def strategy_name(self) -> str:
        return "均线趋势策略"

    @property
    def description(self) -> str:
        return (
            "基于移动平均线的趋势跟踪策略。支持单均线模式（价格与均线比较）"
            "和双均线模式（快慢线交叉）。可启用大盘均线过滤器，"
            "当大盘低于长期均线时强制空仓避险。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "mode": "dual",              # single / dual
            "fast_period": 10,           # 快线周期
            "slow_period": 30,           # 慢线周期（单均线模式下用此值）
            "use_market_filter": True,   # 大盘过滤器
            "market_filter_etf": "510300",  # 大盘基准
            "market_filter_ma": 250,     # 大盘保护均线周期
            "hedge_etf": "511880",       # 避险ETF
        }

    def get_etf_pool(self) -> List[str]:
        return [
            "510300",  # 沪深300ETF
            "510500",  # 中证500ETF
            "159915",  # 创业板ETF
            "510050",  # 上证50ETF
        ]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        mode = self.params.get("mode", "dual")
        fast_period = self.params.get("fast_period", 10)
        slow_period = self.params.get("slow_period", 30)
        use_filter = self.params.get("use_market_filter", True)
        filter_etf = self.params.get("market_filter_etf", "510300")
        filter_ma = self.params.get("market_filter_ma", 250)
        hedge_etf = self.params.get("hedge_etf", "511880")

        # 构建收盘价矩阵
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
        etf_pool = [c for c in self.get_etf_pool() if c in close_df.columns]
        if not etf_pool:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 大盘过滤信号
        market_ok = pd.Series(True, index=close_df.index)
        if use_filter and filter_etf in close_df.columns:
            market_ma = close_df[filter_etf].rolling(filter_ma).mean()
            market_ok = close_df[filter_etf] > market_ma

        for code in etf_pool:
            if code not in close_df.columns:
                continue
            price = close_df[code]

            if mode == "single":
                ma = price.rolling(slow_period).mean()
                signal = (price > ma).astype(float)
            else:  # dual
                fast_ma = price.rolling(fast_period).mean()
                slow_ma = price.rolling(slow_period).mean()
                signal = (fast_ma > slow_ma).astype(float)

            # 应用大盘过滤
            signal = signal * market_ok.astype(float)
            weights[code] = signal

        # 归一化：等权分配给有信号的ETF
        row_sum = weights[etf_pool].sum(axis=1)
        for code in etf_pool:
            weights[code] = weights[code] / row_sum.replace(0, 1)

        # 无持仓时转避险
        no_position = row_sum == 0
        if hedge_etf in weights.columns:
            weights.loc[no_position, hedge_etf] = 1.0

        return weights
