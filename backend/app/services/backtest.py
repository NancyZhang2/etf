"""
回测引擎 — 基于 vectorbt 的策略回测
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import vectorbt as vbt

logger = logging.getLogger(__name__)

# vectorbt 全局设置
vbt.settings.array_wrapper['freq'] = 'D'


class BacktestEngine:
    """
    vectorbt 回测引擎封装
    fees=0.0001 (万分之一), slippage=0.001 (千分之一)
    """

    DEFAULT_FEES = 0.0001
    DEFAULT_SLIPPAGE = 0.001
    DEFAULT_INIT_CASH = 1_000_000

    def __init__(
        self,
        fees: float = DEFAULT_FEES,
        slippage: float = DEFAULT_SLIPPAGE,
        init_cash: float = DEFAULT_INIT_CASH,
    ):
        self.fees = fees
        self.slippage = slippage
        self.init_cash = init_cash

    def run_backtest(
        self,
        close_prices: pd.DataFrame,
        target_weights: pd.DataFrame,
        benchmark_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行全区间回测

        参数:
            close_prices: 收盘价DataFrame, index=日期, columns=ETF代码
            target_weights: 目标权重DataFrame, 同上结构，值0~1
            benchmark_code: 基准ETF代码（用于计算超额收益）

        返回: 回测指标字典
        """
        # 对齐索引
        common_idx = close_prices.index.intersection(target_weights.index)
        if len(common_idx) < 10:
            logger.warning("回测数据不足: 仅 %d 个交易日", len(common_idx))
            return self._empty_result()

        close = close_prices.loc[common_idx]
        weights = target_weights.loc[common_idx]

        # 确保列对齐
        common_cols = close.columns.intersection(weights.columns)
        if len(common_cols) == 0:
            return self._empty_result()

        close = close[common_cols]
        weights = weights[common_cols]

        # 构建组合净值
        try:
            daily_returns, nav = self._build_nav_series(close, weights)
        except Exception as e:
            logger.error("回测计算失败: %s", e)
            return self._empty_result()

        # 计算指标
        result = self._compute_metrics(daily_returns, nav, close, weights)

        # 基准对比
        if benchmark_code and benchmark_code in close_prices.columns:
            bench_series = close_prices[benchmark_code].loc[common_idx]
            bench_return = (bench_series.iloc[-1] / bench_series.iloc[0] - 1) if bench_series.iloc[0] != 0 else 0
            result["benchmark_return"] = round(float(bench_return), 4)
            result["excess_return"] = round(result["total_return"] - float(bench_return), 4)

        return result

    def run_yearly_backtest(
        self,
        close_prices: pd.DataFrame,
        target_weights: pd.DataFrame,
        years: int = 5,
        benchmark_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        逐年回测（近N年）
        返回: [{year, ...metrics}]
        """
        current_year = datetime.now().year
        results = []

        for year in range(current_year - years, current_year + 1):
            start = pd.Timestamp(f"{year}-01-01")
            end = pd.Timestamp(f"{year}-12-31")

            year_close = close_prices[(close_prices.index >= start) & (close_prices.index <= end)]
            year_weights = target_weights[(target_weights.index >= start) & (target_weights.index <= end)]

            if len(year_close) < 10:
                continue

            metrics = self.run_backtest(year_close, year_weights, benchmark_code)
            metrics["year"] = year
            results.append(metrics)

        return results

    def _build_nav_series(self, close: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
        """
        根据目标权重和收盘价计算组合净值序列
        考虑调仓时的交易费用
        """
        returns = close.pct_change().fillna(0)
        # 组合日收益 = 加权收益
        portfolio_returns = (returns * weights).sum(axis=1)

        # 扣除调仓费用：权重变化部分收取费用+滑点
        weight_changes = weights.diff().abs().sum(axis=1).fillna(0)
        trade_cost = weight_changes * (self.fees + self.slippage)
        portfolio_returns = portfolio_returns - trade_cost

        # 累积为净值
        nav = (1 + portfolio_returns).cumprod() * self.init_cash
        return portfolio_returns, nav

    def _compute_metrics(
        self, daily_returns: pd.Series, nav: pd.Series,
        close: pd.DataFrame, weights: pd.DataFrame,
    ) -> Dict[str, Any]:
        """从收益率序列直接计算回测指标"""
        n_days = len(daily_returns)
        n_years = n_days / 252 if n_days > 0 else 1

        # 总收益
        total_return = float(nav.iloc[-1] / nav.iloc[0] - 1) if nav.iloc[0] != 0 else 0

        # 年化收益
        if total_return > -1 and n_years > 0:
            annual_return = (1 + total_return) ** (1 / n_years) - 1
        else:
            annual_return = 0

        # 最大回撤（使用vectorbt计算）
        try:
            pf = vbt.Portfolio.from_holding(nav, init_cash=self.init_cash)
            max_dd = float(pf.max_drawdown())
        except Exception:
            # fallback: 手动计算
            cummax = nav.cummax()
            drawdown = (nav - cummax) / cummax
            max_dd = float(drawdown.min())

        # 年化波动率
        annual_vol = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0

        # 夏普比率 (无风险利率按2%计)
        rf_daily = 0.02 / 252
        excess_daily = daily_returns - rf_daily
        sharpe = float(excess_daily.mean() / excess_daily.std() * np.sqrt(252)) if excess_daily.std() > 0 else 0

        # 索提诺比率
        downside = daily_returns[daily_returns < 0]
        downside_std = float(downside.std()) * np.sqrt(252) if len(downside) > 1 else 1
        sortino = float((annual_return - 0.02) / downside_std) if downside_std > 0 else 0

        # 卡尔玛比率
        calmar = float(annual_return / abs(max_dd)) if abs(max_dd) > 0.001 else 0

        # 胜率与盈亏比
        win_rate, profit_loss = self._calc_win_rate(daily_returns)

        # 换手率估算
        weight_changes = weights.diff().abs().sum(axis=1)
        turnover = float(weight_changes.sum() / 2 / n_years) if n_years > 0 else 0

        # 交易次数估算（权重变化超过阈值的次数）
        trades = int((weight_changes > 0.01).sum())

        return {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(max_dd, 4),
            "annual_volatility": round(annual_vol, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            "win_rate": round(win_rate, 4),
            "profit_loss_ratio": round(profit_loss, 4),
            "total_trades": trades,
            "avg_holding_days": 0,
            "turnover_rate": round(turnover, 4),
            "benchmark_return": 0,
            "excess_return": 0,
        }

    def _calc_win_rate(self, daily_returns: pd.Series) -> Tuple[float, float]:
        """计算胜率和盈亏比"""
        positive = daily_returns[daily_returns > 0]
        negative = daily_returns[daily_returns < 0]

        if len(positive) + len(negative) == 0:
            return 0.0, 0.0

        win_rate = len(positive) / (len(positive) + len(negative))

        avg_win = float(positive.mean()) if len(positive) > 0 else 0
        avg_loss = abs(float(negative.mean())) if len(negative) > 0 else 1
        profit_loss = avg_win / avg_loss if avg_loss > 0 else 0

        return win_rate, profit_loss

    def _empty_result(self) -> Dict[str, Any]:
        """空回测结果"""
        return {
            "total_return": 0, "annual_return": 0, "max_drawdown": 0,
            "annual_volatility": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
            "calmar_ratio": 0, "win_rate": 0, "profit_loss_ratio": 0,
            "total_trades": 0, "avg_holding_days": 0, "turnover_rate": 0,
            "benchmark_return": 0, "excess_return": 0,
        }
