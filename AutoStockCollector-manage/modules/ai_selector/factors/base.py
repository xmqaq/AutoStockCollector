"""
因子基类与注册表
提供标准化因子接口，支持向量化计算与缓存
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
import pandas as pd
import numpy as np
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class FactorData:
    code: str
    name: str
    date: str
    values: Dict[str, float]
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FactorBase(ABC):
    def __init__(self, name: str, category: str = "technical"):
        self.name = name
        self.category = category
        self._cache: Dict[str, FactorData] = {}
        self._cache_enabled = True
        self._cache_ttl = 3600

    def enable_cache(self, ttl: int = 3600):
        self._cache_enabled = True
        self._cache_ttl = ttl

    def disable_cache(self):
        self._cache_enabled = False
        self._cache.clear()

    def _get_cache_key(self, code: str, date: str) -> str:
        return f"{self.name}_{code}_{date}"

    def _get_from_cache(self, code: str, date: str) -> Optional[FactorData]:
        if not self._cache_enabled:
            return None
        key = self._get_cache_key(code, date)
        cached = self._cache.get(key)
        if cached:
            return cached
        return None

    def _save_to_cache(self, data: FactorData):
        if not self._cache_enabled:
            return
        key = self._get_cache_key(data.code, data.date)
        self._cache[key] = data

    @abstractmethod
    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        pass

    def calculate_batch(
        self,
        codes: List[str],
        kline_data_map: Dict[str, List[Dict[str, Any]]],
        **kwargs
    ) -> List[FactorData]:
        results = []
        for code in codes:
            data = kline_data_map.get(code, [])
            try:
                result = self.calculate(code, data, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Factor {self.name} calculation failed for {code}: {e}")
        return results

    def to_dataframe(self, factors: List[FactorData]) -> pd.DataFrame:
        if not factors:
            return pd.DataFrame()
        records = []
        for f in factors:
            record = {"code": f.code, "name": f.name, "date": f.date, "score": f.score}
            record.update(f.values)
            records.append(record)
        return pd.DataFrame(records)


class FactorRegistry:
    _instance = None
    _lock = __import__("threading").Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._factors: Dict[str, FactorBase] = {}
            self._categories: Dict[str, List[str]] = {}

    def register(self, factor: FactorBase, category: Optional[str] = None) -> None:
        self._factors[factor.name] = factor
        cat = category or factor.category
        if cat not in self._categories:
            self._categories[cat] = []
        if factor.name not in self._categories[cat]:
            self._categories[cat].append(factor.name)
        logger.info(f"Registered factor: {factor.name} (category: {cat})")

    def get(self, name: str) -> Optional[FactorBase]:
        return self._factors.get(name)

    def list_by_category(self, category: str) -> List[str]:
        return self._categories.get(category, [])

    def list_all(self) -> Dict[str, List[str]]:
        return self._categories.copy()

    def calculate_composite(
        self,
        codes: List[str],
        factor_names: List[str],
        kline_data_map: Dict[str, List[Dict[str, Any]]],
        weights: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> List[FactorData]:
        if weights is None:
            weights = {name: 1.0 / len(factor_names) for name in factor_names}

        factor_results: Dict[str, List[FactorData]] = {}
        for name in factor_names:
            factor = self.get(name)
            if factor:
                factor_results[name] = factor.calculate_batch(codes, kline_data_map, **kwargs)

        composite_results: Dict[str, FactorData] = {}
        for code in codes:
            total_score = 0.0
            total_weight = 0.0
            values: Dict[str, float] = {}

            for name in factor_names:
                factor_data_list = factor_results.get(name, [])
                for fd in factor_data_list:
                    if fd.code == code:
                        weight = weights.get(name, 1.0)
                        total_score += fd.score * weight
                        total_weight += weight
                        values[f"{name}_score"] = fd.score
                        values.update({f"{name}_{k}": v for k, v in fd.values.items()})
                        break

            if total_weight > 0:
                composite_results[code] = FactorData(
                    code=code,
                    name="",
                    date="",
                    values=values,
                    score=total_score / total_weight
                )

        return list(composite_results.values())


factor_registry = FactorRegistry()