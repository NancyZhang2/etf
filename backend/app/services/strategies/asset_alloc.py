"""
A4. 大类资产配置策略
- 全天候 (All Weather): 固定权重，定期再平衡
- 风险平价 (Risk Parity): 按波动率反比配权
- 股债动态平衡: 固定股债比，偏离阈值触发再平衡
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class AssetAllocStrategy(BaseStrategy):
    """大类资产配置策略"""

    @property
    def strategy_type(self) -> str:
        return "asset_alloc"

    @property
    def strategy_name(self) -> str:
        return "大类资产配置策略"

    @property
    def description(self) -> str:
        return (
            "提供三种经典资产配置模型：全天候（固定权重定期再平衡）、"
            "风险平价（按波动率反比配权）、股债动态平衡（偏离阈值触发再平衡）。"
            "适合长期持有、追求稳健收益的投资者。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "model": "all_weather",      # all_weather / risk_parity / stock_bond
            # 全天候权重
            "etf_weights": {
                "510300": 0.30,  # A股宽基
                "511010": 0.40,  # 长期国债
                "511020": 0.15,  # 中期国债
                "518880": 0.075, # 黄金
                "510880": 0.075, # 红利（替代商品）
            },
            "rebalance_period": 60,      # 再平衡周期（交易日）
            "deviation_threshold": 0.05, # 偏离阈值
            # 股债平衡专用
            "stock_ratio": 0.2,          # 股票目标比例
            "stock_etf": "510300",
            "bond_etf": "511010",
            # 风险平价专用
            "vol_lookback": 60,          # 波动率回看期
        }

    def get_etf_pool(self) -> List[str]:
        model = self.params.get("model", "all_weather")
        if model == "stock_bond":
            return [self.params.get("stock_etf", "510300"),
                    self.params.get("bond_etf", "511010")]
        weights = self.params.get("etf_weights", {})
        return list(weights.keys())

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        model = self.params.get("model", "all_weather")

        if model == "all_weather":
            return self._all_weather(data)
        elif model == "risk_parity":
            return self._risk_parity(data)
        elif model == "stock_bond":
            return self._stock_bond(data)
        else:
            return self._all_weather(data)

    def _all_weather(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """全天候：固定权重 + 定期再平衡"""
        etf_weights = self.params.get("etf_weights", {})
        rebalance_period = self.params.get("rebalance_period", 60)

        close_dict = self._build_close_dict(data)
        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 每隔 rebalance_period 天恢复目标权重
        for i in range(len(close_df)):
            if i % rebalance_period == 0:
                for code, w in etf_weights.items():
                    if code in weights.columns:
                        weights.iloc[i, weights.columns.get_loc(code)] = w
            else:
                # 非调仓日保持上期权重
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]

        return weights

    def _risk_parity(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """风险平价：按波动率反比配权"""
        vol_lookback = self.params.get("vol_lookback", 60)
        rebalance_period = self.params.get("rebalance_period", 60)
        etf_weights = self.params.get("etf_weights", {})
        target_codes = list(etf_weights.keys())

        close_dict = self._build_close_dict(data)
        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        available = [c for c in target_codes if c in close_df.columns]
        if not available:
            return pd.DataFrame()

        returns = close_df[available].pct_change()
        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        for i in range(vol_lookback, len(close_df)):
            if (i - vol_lookback) % rebalance_period != 0:
                if i > 0:
                    weights.iloc[i] = weights.iloc[i - 1]
                continue

            # 计算各资产波动率
            window_returns = returns.iloc[i - vol_lookback:i][available]
            vols = window_returns.std()
            vols = vols.replace(0, np.nan).dropna()

            if vols.empty:
                continue

            # 权重 = 1/vol 归一化
            inv_vols = 1.0 / vols
            norm_weights = inv_vols / inv_vols.sum()

            for code in norm_weights.index:
                weights.iloc[i, weights.columns.get_loc(code)] = norm_weights[code]

        return weights

    def _stock_bond(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """股债动态平衡：偏离阈值触发再平衡"""
        stock_etf = self.params.get("stock_etf", "510300")
        bond_etf = self.params.get("bond_etf", "511010")
        stock_ratio = self.params.get("stock_ratio", 0.2)
        threshold = self.params.get("deviation_threshold", 0.05)

        close_dict = self._build_close_dict(data)
        if not close_dict:
            return pd.DataFrame()

        close_df = pd.DataFrame(close_dict).sort_index().ffill()
        if stock_etf not in close_df.columns or bond_etf not in close_df.columns:
            return pd.DataFrame()

        weights = pd.DataFrame(0.0, index=close_df.index, columns=close_df.columns)

        # 初始配置
        w_stock = stock_ratio
        w_bond = 1.0 - stock_ratio

        stock_nav = 1.0
        bond_nav = 1.0

        stock_ret = close_df[stock_etf].pct_change().fillna(0)
        bond_ret = close_df[bond_etf].pct_change().fillna(0)

        for i in range(len(close_df)):
            if i > 0:
                stock_nav *= (1 + float(stock_ret.iloc[i]))
                bond_nav *= (1 + float(bond_ret.iloc[i]))

                # 计算当前实际权重
                total_val = w_stock * stock_nav + w_bond * bond_nav
                if total_val > 0:
                    actual_stock_ratio = w_stock * stock_nav / total_val
                else:
                    actual_stock_ratio = stock_ratio

                # 偏离检测
                if abs(actual_stock_ratio - stock_ratio) > threshold:
                    # 触发再平衡
                    w_stock = stock_ratio
                    w_bond = 1.0 - stock_ratio
                    stock_nav = 1.0
                    bond_nav = 1.0

            stock_col = weights.columns.get_loc(stock_etf)
            bond_col = weights.columns.get_loc(bond_etf)
            weights.iloc[i, stock_col] = w_stock if i == 0 else stock_ratio if abs(
                (w_stock * stock_nav) / max(w_stock * stock_nav + w_bond * bond_nav, 1e-10) - stock_ratio
            ) > threshold else w_stock * stock_nav / max(w_stock * stock_nav + w_bond * bond_nav, 1e-10)
            weights.iloc[i, bond_col] = 1.0 - weights.iloc[i, stock_col]

        return weights

    def _build_close_dict(self, data: Dict[str, pd.DataFrame]) -> Dict:
        close_dict = {}
        for code, df in data.items():
            if df.empty:
                continue
            series = df.set_index("date")["close"].sort_index()
            series.index = pd.to_datetime(series.index)
            close_dict[code] = series
        return close_dict
