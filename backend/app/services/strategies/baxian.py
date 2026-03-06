"""
B3. 蛋卷八仙过海
- 两层决策：
  第一层：沪深300 vs SMA(40) 择时，低于均线→全仓货币ETF
  第二层：入场后从8只行业ETF中选10日动量Top3等权买入
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class BaxianStrategy(BaseStrategy):
    """蛋卷八仙过海"""

    @property
    def strategy_type(self) -> str:
        return "baxian"

    @property
    def strategy_name(self) -> str:
        return "蛋卷八仙过海"

    @property
    def description(self) -> str:
        return (
            "复刻蛋卷基金八仙过海策略。两层决策机制：第一层用沪深300均线"
            "择时，低于均线时全仓货币ETF避险；第二层从8只行业ETF中选取"
            "10日动量排名前3的等权买入，定期重排行业。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "timing_index": "510300",           # 择时指标ETF
            "timing_ma_period": 40,             # 择时均线周期
            "sector_etf_pool": [
                "512800",   # 银行ETF
                "512880",   # 证券ETF
                "512660",   # 军工ETF
                "512010",   # 医药ETF
                "159928",   # 消费ETF
                "512480",   # 半导体ETF
                "515030",   # 新能源ETF
                "515790",   # 光伏ETF
            ],
            "momentum_days": 10,                # 动量回看天数
            "hold_count": 3,                    # 持仓行业数
            "hedge_etf": "511880",              # 避险标的
            "sector_rebalance_days": 10,        # 行业重排周期
        }

    def get_etf_pool(self) -> List[str]:
        pool = list(self.params.get("sector_etf_pool", []))
        timing = self.params.get("timing_index", "510300")
        hedge = self.params.get("hedge_etf", "511880")
        for code in [timing, hedge]:
            if code not in pool:
                pool.append(code)
        return pool

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        timing_index = self.params.get("timing_index", "510300")
        timing_ma = self.params.get("timing_ma_period", 40)
        sector_pool = self.params.get("sector_etf_pool", [])
        momentum_days = self.params.get("momentum_days", 10)
        hold_count = self.params.get("hold_count", 3)
        hedge = self.params.get("hedge_etf", "511880")
        rebalance_days = self.params.get("sector_rebalance_days", 10)

        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series

        if timing_index not in close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        available_sectors = [c for c in sector_pool if c in close_df.columns]
        if not available_sectors:
            return pd.DataFrame()

        # Layer 1: timing — index vs SMA
        timing_series = close_df[timing_index]
        timing_sma = timing_series.rolling(timing_ma).mean()

        # Layer 2: sector momentum
        sector_momentum = close_df[available_sectors].pct_change(momentum_days)

        warmup = max(timing_ma, momentum_days)
        last_rebalance = -rebalance_days

        for i in range(warmup, len(close_df)):
            price = float(timing_series.iloc[i])
            ma_val = float(timing_sma.iloc[i]) if pd.notna(timing_sma.iloc[i]) else price

            if price < ma_val:
                # Below MA → hedge
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                continue

            # Above MA → select top sectors
            if i - last_rebalance >= rebalance_days:
                last_rebalance = i

                mom = sector_momentum.iloc[i][available_sectors].dropna()
                if mom.empty:
                    if hedge in weights.columns:
                        weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                    continue

                top = mom.nlargest(min(hold_count, len(mom)))
                w = 1.0 / len(top)
                for code in top.index:
                    weights.iloc[i, weights.columns.get_loc(code)] = w
            else:
                # Hold previous allocation
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]

        return weights
