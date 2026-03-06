"""
B2. 蛋卷二八轮动Plus
- 在B1基础上增加钝化机制：信号方向变化时，
  需连续N天信号一致才执行调仓
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class Egg28PlusStrategy(BaseStrategy):
    """蛋卷二八轮动Plus"""

    @property
    def strategy_type(self) -> str:
        return "egg_28_plus"

    @property
    def strategy_name(self) -> str:
        return "蛋卷二八轮动Plus"

    @property
    def description(self) -> str:
        return (
            "在蛋卷二八轮动基础上增加信号钝化机制。信号方向变化时，"
            "需连续N天信号一致才实际切换持仓，有效减少震荡市中的频繁调仓。"
            "保留均线保护和切换缓冲等原有增强功能。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "large_cap_etf": "510300",
            "small_cap_etf": "510500",
            "hedge_etf": "511880",
            "lookback_days": 20,
            "switch_buffer": 0.01,
            "use_ma_protection": True,
            "ma_protection_period": 250,
            "use_blunting": True,
            "blunting_days": 3,
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
        use_blunting = self.params.get("use_blunting", True)
        blunting_days = self.params.get("blunting_days", 3)

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
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        large_mom = close_df[large_cap].pct_change(lookback)
        small_mom = close_df[small_cap].pct_change(lookback)

        ma_protection_ok = pd.Series(True, index=close_df.index)
        if use_ma and large_cap in close_df.columns:
            ma = close_df[large_cap].rolling(ma_period).mean()
            ma_protection_ok = close_df[large_cap] > ma

        current_holding = None
        pending_target = None
        confirm_count = 0

        for i in range(lookback, len(close_df)):
            lm = float(large_mom.iloc[i]) if pd.notna(large_mom.iloc[i]) else 0
            sm = float(small_mom.iloc[i]) if pd.notna(small_mom.iloc[i]) else 0
            ma_ok = bool(ma_protection_ok.iloc[i])

            # Raw signal determination (same logic as B1)
            if not ma_ok:
                raw_target = hedge
            elif lm > 0 and lm >= sm:
                raw_target = large_cap
            elif sm > 0 and sm > lm:
                raw_target = small_cap
            else:
                raw_target = hedge

            # Switch buffer
            if current_holding and current_holding != raw_target and current_holding != hedge:
                if raw_target != hedge:
                    diff = abs(lm - sm)
                    if diff < buffer:
                        raw_target = current_holding

            # Blunting mechanism
            if use_blunting and current_holding is not None:
                if raw_target != current_holding:
                    if raw_target == pending_target:
                        confirm_count += 1
                    else:
                        pending_target = raw_target
                        confirm_count = 1

                    if confirm_count >= blunting_days:
                        current_holding = raw_target
                        pending_target = None
                        confirm_count = 0
                    # else keep current holding
                else:
                    pending_target = None
                    confirm_count = 0
            else:
                current_holding = raw_target
                pending_target = None
                confirm_count = 0

            if current_holding and current_holding in weights.columns:
                weights.iloc[i, weights.columns.get_loc(current_holding)] = 1.0

        return weights
