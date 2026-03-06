"""
B7. 果仁低估值轮动
- 用价格相对历史百分位模拟PE/PB估值因子
- 用近期涨跌幅反转因子替代股息率因子
- 三因子加权评分，选最"便宜"的Top N
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class ValueRotationStrategy(BaseStrategy):
    """果仁低估值轮动"""

    @property
    def strategy_type(self) -> str:
        return "value_rotation"

    @property
    def strategy_name(self) -> str:
        return "果仁低估值轮动"

    @property
    def description(self) -> str:
        return (
            "复刻果仁网低估值轮动策略。由于缺乏实时PE/PB数据，"
            "用价格在历史区间的百分位模拟估值因子，用近期收益率反转"
            "因子替代股息率因子。三因子加权评分后选取最'便宜'的ETF持有。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "etf_pool": [
                "510300",   # 沪深300
                "510500",   # 中证500
                "510880",   # 红利ETF
                "512010",   # 医药ETF
                "159928",   # 消费ETF
                "512880",   # 证券ETF
                "512800",   # 银行ETF
                "512480",   # 半导体ETF
            ],
            "hold_count": 3,
            "rebalance_period": 15,     # 调仓周期（交易日）
            "pe_weight": 0.4,           # 价格百分位因子权重
            "pb_weight": 0.3,           # 高低价比因子权重
            "div_weight": 0.3,          # 反转因子权重
            "history_days": 1250,       # 历史回看天数（约5年）
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
        hold_count = self.params.get("hold_count", 3)
        rebalance = self.params.get("rebalance_period", 15)
        pe_w = self.params.get("pe_weight", 0.4)
        pb_w = self.params.get("pb_weight", 0.3)
        div_w = self.params.get("div_weight", 0.3)
        history_days = self.params.get("history_days", 1250)
        hedge = self.params.get("hedge_etf", "511880")

        close_dict = {}
        high_dict = {}
        low_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            temp = df.set_index("date").sort_index()
            temp.index = pd.to_datetime(temp.index)
            close_dict[code] = temp["close"]
            if "high" in temp.columns:
                high_dict[code] = temp["high"]
            if "low" in temp.columns:
                low_dict[code] = temp["low"]

        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        high_df = pd.DataFrame(high_dict).sort_index().ffill() if high_dict else None
        low_df = pd.DataFrame(low_dict).sort_index().ffill() if low_dict else None

        available = [c for c in pool_codes if c in close_df.columns]
        if not available:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        warmup = min(history_days, max(60, len(close_df) // 4))
        last_rebalance = -rebalance

        for i in range(warmup, len(close_df)):
            if i - last_rebalance < rebalance:
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            last_rebalance = i
            scores = {}

            for code in available:
                # Factor 1: PE proxy — price percentile in history window
                start_idx = max(0, i - history_days)
                hist_prices = close_df[code].iloc[start_idx:i + 1].dropna()
                if len(hist_prices) < 20:
                    continue

                current_price = float(close_df[code].iloc[i])
                hist_min = float(hist_prices.min())
                hist_max = float(hist_prices.max())

                if hist_max > hist_min:
                    pe_score = (current_price - hist_min) / (hist_max - hist_min)
                else:
                    pe_score = 0.5

                # Factor 2: PB proxy — high/low price ratio percentile
                if high_df is not None and low_df is not None and code in high_df.columns and code in low_df.columns:
                    hist_high = high_df[code].iloc[start_idx:i + 1].dropna()
                    hist_low = low_df[code].iloc[start_idx:i + 1].dropna()
                    if len(hist_high) > 20:
                        overall_high = float(hist_high.max())
                        overall_low = float(hist_low.min())
                        if overall_high > overall_low:
                            pb_score = (current_price - overall_low) / (overall_high - overall_low)
                        else:
                            pb_score = 0.5
                    else:
                        pb_score = pe_score
                else:
                    pb_score = pe_score

                # Factor 3: Dividend proxy — reversal factor (negative recent return = "cheap")
                recent_ret = float(close_df[code].pct_change(20).iloc[i]) if i >= 20 else 0
                # Lower recent return → more "undervalued" → lower score is better
                # Normalize to 0-1 range approximately
                div_score = max(0, min(1, 0.5 + recent_ret * 5))

                # Composite: lower = cheaper = better
                composite = pe_w * pe_score + pb_w * pb_score + div_w * div_score
                scores[code] = composite

            if not scores:
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                continue

            # Select cheapest (lowest composite score)
            score_series = pd.Series(scores)
            top = score_series.nsmallest(min(hold_count, len(score_series)))

            w = 1.0 / len(top)
            for code in top.index:
                weights.iloc[i, weights.columns.get_loc(code)] = w

        return weights
