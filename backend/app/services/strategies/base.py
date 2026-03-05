"""
策略基类 — 所有量化策略的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd


class BaseStrategy(ABC):
    """
    量化策略基类
    所有策略必须实现 generate_signals、get_default_params、get_etf_pool
    """

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or self.get_default_params()

    @abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        生成交易信号

        参数:
            data: {etf_code: DataFrame}，每个DataFrame包含 OHLCV 数据
                  列: date, open, high, low, close, volume

        返回:
            DataFrame，index=日期，columns=ETF代码
            值为目标权重（0~1），0表示空仓，>0表示持仓比例
        """
        pass

    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """返回策略默认参数"""
        pass

    @abstractmethod
    def get_etf_pool(self) -> List[str]:
        """返回策略默认ETF池"""
        pass

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """策略类型标识（如 momentum, ma_trend 等）"""
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """策略显示名称"""
        pass

    @property
    def description(self) -> str:
        """策略描述"""
        return ""
