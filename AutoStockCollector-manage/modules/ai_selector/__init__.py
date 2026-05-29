"""
AI量化选股模块 - 工业级架构
对标 Qlib/FinGPT/VectorBT，实现因子标准化、模型管理、策略抽象、回测验证全链路
"""
from .factors.base import FactorRegistry, FactorBase, FactorData
from .strategies.base import BaseStrategy, SelectionResult
from .api import AISelectorAPI


__all__ = [
    "FactorRegistry",
    "FactorBase", 
    "FactorData",
    "BaseStrategy",
    "SelectionResult",
    "AISelectorAPI",
]