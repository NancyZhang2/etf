"""
B10. ETF组合宝多因子行业轮动
- 四因子行业排名：动量 + 成交量变化 + 资金流(量价替代) + 波动率(低波优先)
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class MultiFactorStrategy(BaseStrategy):
    """ETF组合宝多因子行业轮动"""

    @property
    def strategy_type(self) -> str:
        return "multi_factor"

    @property
    def strategy_name(self) -> str:
        return "ETF组合宝多因子轮动"

    @property
    def description(self) -> str:
        return (
            "复刻ETF组合宝的多因子行业轮动策略。综合动量、成交量变化、"
            "资金流（用量价替代）、波动率（低波优先）四个因子排名，"
            "加权评分后选取排名靠前的行业ETF等权持有。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "etf_pool": [
                "512880",   # 证券ETF
                "512010",   # 医药ETF
                "159928",   # 消费ETF
                "512690",   # 酒ETF
                "515790",   # 光伏ETF
                "516160",   # 新能源ETF
                "512800",   # 银行ETF
                "512660",   # 军工ETF
                "512480",   # 半导体ETF
                "159869",   # 游戏ETF
            ],
            "momentum_weight": 0.4,
            "volume_weight": 0.2,
            "flow_weight": 0.2,
            "volatility_weight": 0.2,
            "recommend_count": 10,
            "hold_count": 3,
            "rebalance_period": 5,
            "lookback_days": 20,
            "hedge_etf": "511880",
        }

    def get_etf_pool(self) -> List[str]:
        pool = list(self.params.get("etf_pool", []))
        hedge = self.params.get("hedge_etf", "511880")
        if hedge not in pool:
            pool.append(hedge)
        return pool

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        pool_codes = self.params.get("etf_pool", [])
        mom_w = self.params.get("momentum_weight", 0.4)
        vol_w = self.params.get("volume_weight", 0.2)
        flow_w = self.params.get("flow_weight", 0.2)
        volatility_w = self.params.get("volatility_weight", 0.2)
        hold_count = self.params.get("hold_count", 3)
        rebalance = self.params.get("rebalance_period", 5)
        lookback = self.params.get("lookback_days", 20)
        hedge = self.params.get("hedge_etf", "511880")

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

        available = [c for c in pool_codes if c in close_df.columns]
        if not available:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # Pre-compute factors
        momentum = close_df[available].pct_change(lookback)
        returns = close_df[available].pct_change()
        volatility = returns.rolling(lookback).std()

        # Volume ratio: recent short-term avg / longer-term avg
        if volume_df is not None:
            vol_avail = [c for c in available if c in volume_df.columns]
            vol_ratio = (
                volume_df[vol_avail].rolling(5).mean() /
                volume_df[vol_avail].rolling(lookback).mean().replace(0, np.nan)
            )
        else:
            vol_ratio = None

        # Flow proxy: price change × volume (positive = inflow)
        if volume_df is not None:
            flow_proxy = pd.DataFrame(index=close_df.index, columns=available)
            for c in available:
                if c in volume_df.columns:
                    flow_proxy[c] = returns[c].rolling(5).mean() * volume_df[c].rolling(5).mean()
        else:
            flow_proxy = None

        last_rebalance = -rebalance

        for i in range(lookback, len(close_df)):
            if i - last_rebalance < rebalance:
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            last_rebalance = i

            # Factor 1: Momentum (higher = better → ascending=False)
            day_mom = momentum.iloc[i][available].dropna()
            if day_mom.empty:
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                continue

            mom_rank = day_mom.rank(ascending=False)

            # Factor 2: Volume change (higher = better)
            if vol_ratio is not None:
                day_vol = vol_ratio.iloc[i][[c for c in day_mom.index if c in vol_ratio.columns]].dropna()
                if not day_vol.empty:
                    vol_rank = day_vol.rank(ascending=False)
                else:
                    vol_rank = pd.Series(dtype=float)
            else:
                vol_rank = pd.Series(dtype=float)

            # Factor 3: Flow proxy (higher = better)
            if flow_proxy is not None:
                day_flow = flow_proxy.iloc[i][[c for c in day_mom.index if c in flow_proxy.columns]]
                day_flow = pd.to_numeric(day_flow, errors="coerce").dropna()
                if not day_flow.empty:
                    flow_rank = day_flow.rank(ascending=False)
                else:
                    flow_rank = pd.Series(dtype=float)
            else:
                flow_rank = pd.Series(dtype=float)

            # Factor 4: Volatility (lower = better → ascending=True)
            day_vol_level = volatility.iloc[i][available].dropna()
            if not day_vol_level.empty:
                vola_rank = day_vol_level.rank(ascending=True)
            else:
                vola_rank = pd.Series(dtype=float)

            # Composite score
            codes_set = set(mom_rank.index)
            composite = pd.Series(0.0, index=list(codes_set))

            for code in codes_set:
                score = 0.0
                total_w = 0.0

                if code in mom_rank.index:
                    score += mom_w * mom_rank[code]
                    total_w += mom_w
                if code in vol_rank.index:
                    score += vol_w * vol_rank[code]
                    total_w += vol_w
                if code in flow_rank.index:
                    score += flow_w * flow_rank[code]
                    total_w += flow_w
                if code in vola_rank.index:
                    score += volatility_w * vola_rank[code]
                    total_w += volatility_w

                composite[code] = score / total_w if total_w > 0 else score

            # Select top (lowest rank score = best)
            top = composite.nsmallest(min(hold_count, len(composite)))
            w = 1.0 / len(top)
            for code in top.index:
                weights.iloc[i, weights.columns.get_loc(code)] = w

        return weights
