"""
A3. 网格交易策略
- 等差/等比网格 + 价格触发
- 在设定的价格区间内，价格每穿越一条网格线就执行对应买卖
- 适合震荡市，与趋势策略互补
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class GridStrategy(BaseStrategy):
    """网格交易策略"""

    @property
    def strategy_type(self) -> str:
        return "grid"

    @property
    def strategy_name(self) -> str:
        return "网格交易策略"

    @property
    def description(self) -> str:
        return (
            "在预设价格区间内设置等差或等比网格线，"
            "价格下穿网格线时买入、上穿时卖出，实现高抛低吸。"
            "适合震荡市或底部区间的ETF。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "target_etf": "510300",      # 交易标的
            "grid_type": "arithmetic",   # arithmetic / geometric
            "grid_count": 10,            # 网格数量
            "price_upper_pct": 1.3,      # 上界=初始价×此值
            "price_lower_pct": 0.7,      # 下界=初始价×此值
            "base_position": 0.5,        # 初始底仓比例
            "max_position": 0.9,         # 最大仓位
            "min_position": 0.1,         # 最小仓位
        }

    def get_etf_pool(self) -> List[str]:
        return [self.params.get("target_etf", "510300")]

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        target = self.params.get("target_etf", "510300")
        grid_type = self.params.get("grid_type", "arithmetic")
        grid_count = self.params.get("grid_count", 10)
        upper_pct = self.params.get("price_upper_pct", 1.3)
        lower_pct = self.params.get("price_lower_pct", 0.7)
        base_pos = self.params.get("base_position", 0.5)
        max_pos = self.params.get("max_position", 0.9)
        min_pos = self.params.get("min_position", 0.1)

        if target not in data or data[target].empty:
            return pd.DataFrame()

        df = data[target]
        series = df.set_index("date")["close"].sort_index()
        series.index = pd.to_datetime(series.index)

        # 初始价格（第一个有效收盘价）
        init_price = float(series.iloc[0])
        price_upper = init_price * upper_pct
        price_lower = init_price * lower_pct

        # 生成网格线
        if grid_type == "geometric":
            ratio = (price_upper / price_lower) ** (1.0 / grid_count)
            grid_lines = [price_lower * (ratio ** i) for i in range(grid_count + 1)]
        else:  # arithmetic
            step = (price_upper - price_lower) / grid_count
            grid_lines = [price_lower + step * i for i in range(grid_count + 1)]

        grid_lines = sorted(grid_lines)

        # 模拟网格交易
        weights = pd.DataFrame(0.0, index=series.index, columns=[target])
        position = base_pos
        pos_per_grid = (max_pos - min_pos) / grid_count

        # 初始化：确定当前价格在哪个网格
        prev_grid_idx = self._find_grid_index(float(series.iloc[0]), grid_lines)

        for i, (date_idx, price) in enumerate(series.items()):
            price_f = float(price)
            curr_grid_idx = self._find_grid_index(price_f, grid_lines)

            # 网格穿越检测
            if curr_grid_idx < prev_grid_idx:
                # 价格下穿 → 买入（增加仓位）
                grids_crossed = prev_grid_idx - curr_grid_idx
                position = min(position + grids_crossed * pos_per_grid, max_pos)
            elif curr_grid_idx > prev_grid_idx:
                # 价格上穿 → 卖出（减少仓位）
                grids_crossed = curr_grid_idx - prev_grid_idx
                position = max(position - grids_crossed * pos_per_grid, min_pos)

            # 价格越界处理
            if price_f > price_upper or price_f < price_lower:
                pass  # 维持当前仓位

            weights.loc[date_idx, target] = position
            prev_grid_idx = curr_grid_idx

        return weights

    def _find_grid_index(self, price: float, grid_lines: list) -> int:
        """找到价格所在的网格层级（0=最低格）"""
        for i, line in enumerate(grid_lines):
            if price < line:
                return max(0, i - 1)
        return len(grid_lines) - 1
