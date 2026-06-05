"""因子注册中心 — 所有因子继承 Factor 基类并自动注册，支持动态调权重。"""

from typing import List, Dict, Optional, Type, Callable
from dataclasses import dataclass, field


@dataclass
class FactorMeta:
    name: str
    inverse: bool = False       # True 表示值越低越好（如波动率）
    default_weight: float = 1.0
    group: str = '其他'         # 因子分组：技术面/资金面/基本面/情绪面/衍生
    description: str = ''


class Factor:
    """因子基类。子类需定义 meta 并实现 compute。"""

    meta: FactorMeta

    def compute(self, code: str, store: 'DataStore') -> Optional[float]:
        """对单只股票计算因子值。返回 None 表示无数据。"""
        raise NotImplementedError


class FactorRegistry:
    """全局因子注册表，管理注册、查询、权重。"""

    _factors: Dict[str, Factor] = {}
    _weights: Dict[str, float] = {}

    @classmethod
    def register(cls, factor_cls: Type[Factor]):
        """装饰器或直接调用：注册因子类。"""
        instance = factor_cls()
        name = instance.meta.name
        if name in cls._factors:
            raise ValueError(f'Factor [{name}] already registered')
        cls._factors[name] = instance
        cls._weights[name] = instance.meta.default_weight
        return factor_cls

    @classmethod
    def get(cls, name: str) -> Optional[Factor]:
        return cls._factors.get(name)

    @classmethod
    def list_factors(cls) -> List[str]:
        return list(cls._factors.keys())

    @classmethod
    def list_meta(cls) -> List[FactorMeta]:
        return [f.meta for f in cls._factors.values()]

    @classmethod
    def set_weight(cls, name: str, weight: float):
        if name not in cls._factors:
            raise KeyError(f'Factor [{name}] not registered')
        cls._weights[name] = weight

    @classmethod
    def set_weights(cls, weights: Dict[str, float]):
        for name, w in weights.items():
            cls.set_weight(name, w)

    @classmethod
    def get_weight(cls, name: str) -> float:
        return cls._weights.get(name, 1.0)

    @classmethod
    def get_weights(cls) -> Dict[str, float]:
        return dict(cls._weights)

    @classmethod
    def reset_weights(cls):
        for name, f in cls._factors.items():
            cls._weights[name] = f.meta.default_weight

    @classmethod
    def normalize_weight(cls, names: List[str] = None) -> Dict[str, float]:
        """返回归一化权重（和为1）。"""
        names = names or list(cls._weights.keys())
        weights = {n: cls._weights.get(n, 1.0) for n in names}
        total = sum(weights.values())
        if total == 0:
            return {n: 1.0 / len(names) for n in names}
        return {n: n_w / total for n, n_w in weights.items()}


register = FactorRegistry.register


class DataStore:
    """对引擎暴露的统一数据接口。

    计算因子时通过此对象访问原始数据，无需直接引用 executor。
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
