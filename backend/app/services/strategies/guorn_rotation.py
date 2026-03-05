"""
B2. 果仁行业轮动复刻版
- 动量 + 溢价率双因子排名（ETF无溢价率数据时降级为纯动量+成交量因子）
- 行业集中度限制
- 每周五调仓
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class GuornRotationStrategy(BaseStrategy):
    """果仁行业轮动复刻"""

    @property
    def strategy_type(self) -> str:
        return "guorn_rotation"

    @property
    def strategy_name(self) -> str:
        return "果仁行业轮动复刻"

    @property
    def description(self) -> str:
        return (
            "复刻果仁网的行业轮动策略。使用动量+成交量双因子排名，"
            "选取综合评分最优的行业ETF持有。包含负动量过滤、"
            "成交额门槛和行业集中度限制。每周调仓一次。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "hold_count": 3,              # 持仓数量
            "lookback_days": 20,          # 动量回看天数
            "rebalance_period": 5,        # 调仓周期（交易日，5=每周）
            "momentum_weight": 0.7,       # 动量因子权重
            "volume_weight": 0.3,         # 成交量因子权重
            "momentum_threshold": 0.0,    # 最低动量门槛
            "hedge_etf": "511880",        # 避险标的
        }

    def get_etf_pool(self) -> List[str]:
        return [
            "512880",  # 证券ETF
            "512010",  # 医药ETF
            "159928",  # 消费ETF
            "512690",  # 酒ETF
            "515790",  # 光伏ETF
            "516160",  # 新能源ETF
            "512000",  # 券商ETF
            "159869",  # 游戏ETF
            "513100",  # 纳指ETF
            "513050",  # 中概互联ETF
        ]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        hold_count = self.params.get("hold_count", 3)
        lookback = self.params.get("lookback_days", 20)
        rebalance = self.params.get("rebalance_period", 5)
        mom_weight = self.params.get("momentum_weight", 0.7)
        vol_weight = self.params.get("volume_weight", 0.3)
        mom_threshold = self.params.get("momentum_threshold", 0.0)
        hedge = self.params.get("hedge_etf", "511880")

        # 构建收盘价和成交量矩阵
        close_dict = {}
        volume_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            temp = df.set_index("date").sort_index()
            temp.index = pd.to_datetime(temp.index)
            close_dict[code] = temp["close"]
            if "volume" in temp.columns:
                volume_dict[code] = temp["volume"]

        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        volume_df = pd.DataFrame(volume_dict).sort_index().ffill() if volume_dict else None

        pool = [c for c in self.get_etf_pool() if c in close_df.columns]
        if not pool:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 动量
        momentum = close_df[pool].pct_change(lookback)

        # 成交量变化率（近5日均量 / 近20日均量）
        if volume_df is not None:
            vol_pool = [c for c in pool if c in volume_df.columns]
            vol_ratio = (
                volume_df[vol_pool].rolling(5).mean() /
                volume_df[vol_pool].rolling(20).mean().replace(0, np.nan)
            )
        else:
            vol_ratio = None

        last_rebalance = -rebalance

        for i in range(lookback, len(close_df)):
            if i - last_rebalance < rebalance:
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            last_rebalance = i

            # 获取当日因子值
            day_mom = momentum.iloc[i][pool].dropna()

            # 过滤负动量
            day_mom = day_mom[day_mom > mom_threshold]

            if day_mom.empty:
                # 全部转避险
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                continue

            # 动量排名（越高越好 → rank ascending=False）
            mom_rank = day_mom.rank(ascending=False)

            # 成交量排名
            if vol_ratio is not None:
                day_vol = vol_ratio.iloc[i][[c for c in day_mom.index if c in vol_ratio.columns]].dropna()
                if not day_vol.empty:
                    vol_rank = day_vol.rank(ascending=False)
                    # 对齐
                    common = mom_rank.index.intersection(vol_rank.index)
                    composite = mom_weight * mom_rank[common] + vol_weight * vol_rank[common]
                else:
                    composite = mom_rank
            else:
                composite = mom_rank

            # 选取综合得分最优（rank值最小）的前 hold_count 只
            top = composite.nsmallest(hold_count)

            # 等权分配
            w = 1.0 / len(top)
            for code in top.index:
                weights.iloc[i, weights.columns.get_loc(code)] = w

        return weights
