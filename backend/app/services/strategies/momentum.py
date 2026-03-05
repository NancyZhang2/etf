"""
A1. 动量轮动策略
- ETF池动量排名 + 定期调仓 + 避险机制
- 参数: lookback=20, hold_count=3, rebalance_period=5, hedge_threshold=-5%
- 避险: 全部动量为负时切换到货币ETF (511880)
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量轮动策略"""

    @property
    def strategy_type(self) -> str:
        return "momentum"

    @property
    def strategy_name(self) -> str:
        return "动量轮动策略"

    @property
    def description(self) -> str:
        return (
            "根据ETF池中各品种的动量（过去N日涨跌幅）排名，"
            "定期调仓持有动量最强的若干只ETF。"
            "当所有ETF动量为负时，切换至货币ETF避险。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "lookback": 20,          # 动量回看期（交易日）
            "hold_count": 3,         # 持仓ETF数量
            "rebalance_period": 5,   # 调仓周期（交易日）
            "hedge_threshold": -0.05, # 避险阈值（-5%）
            "hedge_etf": "511880",   # 避险ETF（银华日利）
        }

    def get_etf_pool(self) -> List[str]:
        return [
            "510300",  # 沪深300ETF
            "510500",  # 中证500ETF
            "510050",  # 上证50ETF
            "159915",  # 创业板ETF
            "510880",  # 红利ETF
            "512010",  # 医药ETF
            "512880",  # 证券ETF
            "159928",  # 消费ETF
            "518880",  # 黄金ETF
            "511010",  # 国债ETF
        ]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成动量轮动信号

        返回: DataFrame, index=日期, columns=ETF代码, 值=目标权重(0~1)
        """
        lookback = self.params.get("lookback", 20)
        hold_count = self.params.get("hold_count", 3)
        rebalance_period = self.params.get("rebalance_period", 5)
        hedge_threshold = self.params.get("hedge_threshold", -0.05)
        hedge_etf = self.params.get("hedge_etf", "511880")

        # 构建收盘价矩阵
        all_codes = list(data.keys())
        if not all_codes:
            return pd.DataFrame()

        # 对齐日期
        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series

        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict)
        close_df = close_df.sort_index().ffill()

        # 计算动量（lookback日收益率）
        momentum = close_df.pct_change(periods=lookback)

        # 排除避险ETF参与排名
        rank_codes = [c for c in close_df.columns if c != hedge_etf]

        # 生成权重矩阵
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 逐日计算（按调仓周期）
        last_rebalance = -rebalance_period  # 确保第一天就调仓

        for i in range(lookback, len(close_df)):
            if i - last_rebalance < rebalance_period:
                # 未到调仓日，保持上一期持仓
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            last_rebalance = i
            date_idx = close_df.index[i]

            # 获取当日各ETF动量
            day_momentum = momentum.loc[date_idx, rank_codes].dropna()

            if day_momentum.empty:
                # 全切避险
                if hedge_etf in weights.columns:
                    weights.loc[date_idx, hedge_etf] = 1.0
                continue

            # 检查是否所有动量为负 → 避险
            if (day_momentum < hedge_threshold).all():
                if hedge_etf in weights.columns:
                    weights.loc[date_idx, hedge_etf] = 1.0
                continue

            # 选取动量最高的 hold_count 只
            top_codes = day_momentum.nlargest(hold_count)
            # 只选动量为正的
            top_codes = top_codes[top_codes > 0]

            if top_codes.empty:
                # 全部动量为负，避险
                if hedge_etf in weights.columns:
                    weights.loc[date_idx, hedge_etf] = 1.0
            else:
                # 等权分配
                w = 1.0 / len(top_codes)
                for code in top_codes.index:
                    weights.loc[date_idx, code] = w

        return weights
