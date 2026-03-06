"""
B9. 集思录动量+RSRS择时
- 动量评分：log收益率线性回归斜率 × R² + 长期反转修正
- RSRS择时：高低价OLS回归斜率的标准化Z-score × R²
- 综合：选动量最高ETF，RSRS确认则持有，否则避险
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class RSRSMomentumStrategy(BaseStrategy):
    """集思录动量+RSRS择时"""

    @property
    def strategy_type(self) -> str:
        return "rsrs_momentum"

    @property
    def strategy_name(self) -> str:
        return "集思录动量+RSRS择时"

    @property
    def description(self) -> str:
        return (
            "复刻集思录经典的动量+RSRS双层策略。动量层用log收益率的"
            "线性回归斜率（经R²修正）加长期反转修正来评分；RSRS层"
            "用高低价OLS回归斜率的标准化Z-score确认择时。"
            "选动量最高的ETF，RSRS确认后持有，否则切换至避险标的。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "etf_pool": [
                "518880",   # 黄金ETF
                "513100",   # 纳指ETF
                "159915",   # 创业板ETF
                "510300",   # 沪深300
                "511010",   # 国债ETF
            ],
            "momentum_days": 25,
            "reversal_days": 200,
            "reversal_weight": 0.5,
            "rsrs_regression_days": 18,
            "rsrs_zscore_days": 600,
            "rsrs_threshold": 0.7,
            "hedge_etf": "511880",
            "rebalance_period": 5,
        }

    def get_etf_pool(self) -> List[str]:
        pool = list(self.params.get("etf_pool", []))
        hedge = self.params.get("hedge_etf", "511880")
        if hedge not in pool:
            pool.append(hedge)
        return pool

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        pool_codes = self.params.get("etf_pool", [])
        momentum_days = self.params.get("momentum_days", 25)
        reversal_days = self.params.get("reversal_days", 200)
        reversal_weight = self.params.get("reversal_weight", 0.5)
        rsrs_reg_days = self.params.get("rsrs_regression_days", 18)
        rsrs_zscore_days = self.params.get("rsrs_zscore_days", 600)
        rsrs_threshold = self.params.get("rsrs_threshold", 0.7)
        hedge = self.params.get("hedge_etf", "511880")
        rebalance = self.params.get("rebalance_period", 5)

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

        # Pre-compute log returns
        log_returns = np.log(close_df[available] / close_df[available].shift(1))

        warmup = max(momentum_days, reversal_days, rsrs_reg_days + rsrs_zscore_days)
        # Cap warmup to prevent issues with short test data
        warmup = min(warmup, len(close_df) - 1)

        last_rebalance = -rebalance

        for i in range(warmup, len(close_df)):
            if i - last_rebalance < rebalance:
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            last_rebalance = i

            # === Layer 1: Momentum scoring ===
            mom_scores = {}
            for code in available:
                # Short-term momentum: linear regression slope of log returns × R²
                if i >= momentum_days:
                    window = log_returns[code].iloc[i - momentum_days + 1:i + 1].dropna()
                    if len(window) >= 5:
                        x = np.arange(len(window))
                        coeffs = np.polyfit(x, window.values, 1)
                        slope = coeffs[0]
                        # R²
                        y_hat = np.polyval(coeffs, x)
                        ss_res = np.sum((window.values - y_hat) ** 2)
                        ss_tot = np.sum((window.values - window.values.mean()) ** 2)
                        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                        r2 = max(0, r2)
                        short_score = slope * r2
                    else:
                        short_score = 0
                else:
                    short_score = 0

                # Long-term reversal correction
                if i >= reversal_days:
                    long_ret = float(close_df[code].iloc[i] / close_df[code].iloc[i - reversal_days] - 1)
                    reversal_score = -long_ret  # Negative = reversal (mean reversion)
                else:
                    reversal_score = 0

                mom_scores[code] = short_score + reversal_weight * reversal_score

            if not mom_scores:
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0
                continue

            # Select best momentum ETF
            best_code = max(mom_scores, key=mom_scores.get)

            # === Layer 2: RSRS timing ===
            rsrs_ok = True
            if high_df is not None and low_df is not None and best_code in high_df.columns and best_code in low_df.columns:
                rsrs_ok = self._check_rsrs(
                    high_df[best_code], low_df[best_code],
                    i, rsrs_reg_days, rsrs_zscore_days, rsrs_threshold,
                )

            if rsrs_ok:
                weights.iloc[i, weights.columns.get_loc(best_code)] = 1.0
            else:
                if hedge in weights.columns:
                    weights.iloc[i, weights.columns.get_loc(hedge)] = 1.0

        return weights

    def _check_rsrs(
        self,
        high_series: pd.Series,
        low_series: pd.Series,
        current_idx: int,
        reg_days: int,
        zscore_days: int,
        threshold: float,
    ) -> bool:
        """
        RSRS (Resistance Support Relative Strength) check.
        Returns True if market timing is favorable.
        """
        # Need enough history for z-score calculation
        start_idx = max(0, current_idx - zscore_days)
        if current_idx - start_idx < reg_days + 1:
            return True  # Not enough data, assume OK

        # Calculate RSRS slopes over the history window
        slopes = []
        r2s = []
        for j in range(start_idx + reg_days, current_idx + 1):
            h = high_series.iloc[j - reg_days:j].values.astype(float)
            l = low_series.iloc[j - reg_days:j].values.astype(float)

            if len(h) < reg_days or np.std(l) < 1e-10:
                slopes.append(np.nan)
                r2s.append(np.nan)
                continue

            # OLS: high = alpha + beta * low
            coeffs = np.polyfit(l, h, 1)
            beta = coeffs[0]
            y_hat = np.polyval(coeffs, l)
            ss_res = np.sum((h - y_hat) ** 2)
            ss_tot = np.sum((h - h.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            r2 = max(0, r2)

            slopes.append(beta)
            r2s.append(r2)

        slopes = np.array(slopes, dtype=float)
        r2s = np.array(r2s, dtype=float)
        valid = ~np.isnan(slopes) & ~np.isnan(r2s)

        if valid.sum() < 10:
            return True

        slopes_valid = slopes[valid]
        r2s_valid = r2s[valid]

        # Standardized RSRS: z-score of current slope × R²
        current_slope = slopes_valid[-1]
        current_r2 = r2s_valid[-1]
        mean_slope = np.mean(slopes_valid)
        std_slope = np.std(slopes_valid)

        if std_slope < 1e-10:
            return True

        zscore = (current_slope - mean_slope) / std_slope
        rsrs_score = zscore * current_r2

        return rsrs_score > threshold
