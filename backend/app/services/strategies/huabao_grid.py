"""
B8. 华宝网格交易
- 在A3基础上增加回落确认机制：
  触格后不立即成交，等价格回落/反弹确认后再执行
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.app.services.strategies.base import BaseStrategy


class HuabaoGridStrategy(BaseStrategy):
    """华宝网格交易"""

    @property
    def strategy_type(self) -> str:
        return "huabao_grid"

    @property
    def strategy_name(self) -> str:
        return "华宝网格交易"

    @property
    def description(self) -> str:
        return (
            "复刻华宝智投的网格交易策略。在经典网格交易基础上增加回落确认"
            "机制：价格触碰网格线后不立即执行，等价格回落/反弹一定幅度后才"
            "确认成交，有效减少假突破导致的无效交易。"
            "与经典策略A3(网格交易)逻辑相似。"
        )

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "target_etf": "510300",
            "grid_type": "arithmetic",
            "grid_count": 10,
            "price_upper_pct": 1.3,
            "price_lower_pct": 0.7,
            "base_position": 0.5,
            "max_position": 0.9,
            "min_position": 0.1,
            "use_rebound_confirm": True,
            "rebound_pct": 0.005,   # 0.5% rebound confirmation
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
        use_confirm = self.params.get("use_rebound_confirm", True)
        rebound_pct = self.params.get("rebound_pct", 0.005)

        if target not in data or data[target].empty:
            return pd.DataFrame()

        df = data[target]
        series = df.set_index("date")["close"].sort_index()
        series.index = pd.to_datetime(series.index)

        init_price = float(series.iloc[0])
        price_upper = init_price * upper_pct
        price_lower = init_price * lower_pct

        # Build grid lines
        if grid_type == "geometric":
            ratio = (price_upper / price_lower) ** (1.0 / grid_count)
            grid_lines = [price_lower * (ratio ** i) for i in range(grid_count + 1)]
        else:
            step = (price_upper - price_lower) / grid_count
            grid_lines = [price_lower + step * i for i in range(grid_count + 1)]

        grid_lines = sorted(grid_lines)

        weights = pd.DataFrame(0.0, index=series.index, columns=[target])
        position = base_pos
        pos_per_grid = (max_pos - min_pos) / grid_count

        prev_grid_idx = self._find_grid_index(float(series.iloc[0]), grid_lines)

        # Rebound confirmation state
        pending_direction = None   # "buy" or "sell"
        pending_grids = 0
        trigger_price = None

        for i, (date_idx, price) in enumerate(series.items()):
            price_f = float(price)
            curr_grid_idx = self._find_grid_index(price_f, grid_lines)

            if curr_grid_idx < prev_grid_idx:
                direction = "buy"
                grids = prev_grid_idx - curr_grid_idx
            elif curr_grid_idx > prev_grid_idx:
                direction = "sell"
                grids = curr_grid_idx - prev_grid_idx
            else:
                direction = None
                grids = 0

            if direction and use_confirm:
                # Record pending signal, wait for confirmation
                pending_direction = direction
                pending_grids = grids
                trigger_price = price_f
            elif direction and not use_confirm:
                # Immediate execution
                if direction == "buy":
                    position = min(position + grids * pos_per_grid, max_pos)
                else:
                    position = max(position - grids * pos_per_grid, min_pos)

            # Check rebound confirmation
            if pending_direction and trigger_price is not None:
                if pending_direction == "buy":
                    # Price dropped through grid → wait for rebound (price goes up)
                    if price_f >= trigger_price * (1 + rebound_pct):
                        position = min(position + pending_grids * pos_per_grid, max_pos)
                        pending_direction = None
                        trigger_price = None
                elif pending_direction == "sell":
                    # Price rose through grid → wait for pullback (price goes down)
                    if price_f <= trigger_price * (1 - rebound_pct):
                        position = max(position - pending_grids * pos_per_grid, min_pos)
                        pending_direction = None
                        trigger_price = None

            weights.loc[date_idx, target] = position
            prev_grid_idx = curr_grid_idx

        return weights

    def _find_grid_index(self, price: float, grid_lines: list) -> int:
        """找到价格所在的网格层级"""
        for i, line in enumerate(grid_lines):
            if price < line:
                return max(0, i - 1)
        return len(grid_lines) - 1
