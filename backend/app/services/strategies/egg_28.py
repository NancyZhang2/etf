"""
B1. 蛋卷二八轮动复刻版
- 300/500动量对比 → 持有动量更强者
- 两者均为负 → 转货币ETF避险
- 增强: 切换缓冲 + 250日均线保护
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class Egg28Strategy(BaseStrategy):
    """蛋卷二八轮动复刻"""

    @property
    def strategy_type(self) -> str:
        return "egg_28"

    @property
    def strategy_name(self) -> str:
        return "蛋卷二八轮动复刻"

    @property
    def description(self) -> str:
        return (
            "复刻蛋卷基金经典的二八轮动策略。比较沪深300与中证500的20日动量，"
            "持有动量更强者。两者均为负时切换至货币ETF避险。"
            "增强功能：切换缓冲（避免震荡市频繁调仓）+ 均线保护（熊市强制避险）。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "large_cap_etf": "510300",   # 大盘标的
            "small_cap_etf": "510500",   # 小盘标的
            "hedge_etf": "511880",       # 避险标的
            "lookback_days": 20,         # 动量回看天数
            "switch_buffer": 0.01,       # 切换缓冲（涨幅差<1%不切换）
            "use_ma_protection": True,   # 均线保护开关
            "ma_protection_period": 250, # 保护均线周期
        }

    def get_etf_pool(self) -> List[str]:
        return [
            self.params.get("large_cap_etf", "510300"),
            self.params.get("small_cap_etf", "510500"),
            self.params.get("hedge_etf", "511880"),
        ]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        large_cap = self.params.get("large_cap_etf", "510300")
        small_cap = self.params.get("small_cap_etf", "510500")
        hedge = self.params.get("hedge_etf", "511880")
        lookback = self.params.get("lookback_days", 20)
        buffer = self.params.get("switch_buffer", 0.01)
        use_ma = self.params.get("use_ma_protection", True)
        ma_period = self.params.get("ma_protection_period", 250)

        # 构建收盘价
        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series

        if large_cap not in close_dict or small_cap not in close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        all_codes = [large_cap, small_cap]
        if hedge in close_df.columns:
            all_codes.append(hedge)

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 计算动量
        large_mom = close_df[large_cap].pct_change(lookback)
        small_mom = close_df[small_cap].pct_change(lookback)

        # 均线保护
        ma_protection_ok = pd.Series(True, index=close_df.index)
        if use_ma and large_cap in close_df.columns:
            ma = close_df[large_cap].rolling(ma_period).mean()
            ma_protection_ok = close_df[large_cap] > ma

        current_holding = None

        for i in range(lookback, len(close_df)):
            lm = float(large_mom.iloc[i]) if pd.notna(large_mom.iloc[i]) else 0
            sm = float(small_mom.iloc[i]) if pd.notna(small_mom.iloc[i]) else 0
            ma_ok = bool(ma_protection_ok.iloc[i])

            # 均线保护：大盘低于长期均线 → 强制避险
            if not ma_ok:
                target = hedge
            elif lm > 0 and lm >= sm:
                target = large_cap
            elif sm > 0 and sm > lm:
                target = small_cap
            else:
                # 两者均为负 → 避险
                target = hedge

            # 切换缓冲：如果已有持仓且涨幅差小于buffer，不切换
            if current_holding and current_holding != target and current_holding != hedge:
                if target != hedge:
                    diff = abs(lm - sm)
                    if diff < buffer:
                        target = current_holding

            current_holding = target

            if target in weights.columns:
                weights.iloc[i, weights.columns.get_loc(target)] = 1.0

        return weights
