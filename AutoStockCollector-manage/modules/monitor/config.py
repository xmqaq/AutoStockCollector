"""AI 监控双轨道配置。复用 StrategyStorage 存储，每用户一条文档
(type="monitor_config", name="monitor_config_{user_id}")。
"""
import copy
from typing import Any, Dict, Optional

from modules.ai.strategies.storage import StrategyStorage
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "long_term": {
        "roe_min": 12,
        "revenue_growth_min": 10,
        "pe_percentile_max": 70,
        "max_positions": 5,
        "fund_ratio": 0.6,
        "weight_overrides": {"fundamental": 0.45, "technical": 0.15, "fund_flow": 0.20, "valuation": 0.20},
        "candidate_pool": 30,
    },
    "short_term": {
        "main_net_inflow_min": 50000000,
        "news_positive_min": 2,
        "max_positions": 3,
        "fund_ratio": 0.4,
        "weight_overrides": {"fundamental": 0.15, "technical": 0.35, "fund_flow": 0.35, "valuation": 0.15},
        "candidate_pool": 20,
    },
}


def _merge(partial: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """用 partial 覆盖默认值，缺失字段补默认。按轨道做浅合并
    (传入的 weight_overrides 等子 dict 会整体替换，这是有意取舍——
    部分覆盖嵌套权重属过度设计)。"""
    merged = copy.deepcopy(DEFAULT_CONFIG)
    if partial:
        for track in ("long_term", "short_term"):
            sub = partial.get(track)
            if isinstance(sub, dict):
                merged[track].update(sub)
    return merged


class MonitorConfig:
    def __init__(self):
        self._storage = StrategyStorage()

    @staticmethod
    def _name(user_id: str) -> str:
        return f"monitor_config_{user_id}"

    def get(self, user_id: str = "default") -> Dict[str, Any]:
        doc = self._storage.get_by_name(self._name(user_id))
        if doc and isinstance(doc.get("config"), dict):
            return _merge(doc["config"])
        return copy.deepcopy(DEFAULT_CONFIG)

    def save(self, user_id: str, config: Dict[str, Any]) -> None:
        merged = _merge(config)
        existing = self._storage.get_by_name(self._name(user_id))
        doc = {
            "type": "monitor_config",
            "name": self._name(user_id),
            "user_id": user_id,
            "config": merged,
        }
        if existing and existing.get("_id"):
            doc["_id"] = existing["_id"]  # 带 _id 走 update，避开 name 唯一索引冲突
        self._storage.upsert_strategy(doc)

    def merge_with_default(self, partial: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return _merge(partial)


if __name__ == "__main__":
    d = _merge({})
    assert d["long_term"]["roe_min"] == 12
    assert d["short_term"]["max_positions"] == 3
    m = _merge({"long_term": {"roe_min": 20, "max_positions": 8}})
    assert m["long_term"]["roe_min"] == 20
    assert m["long_term"]["max_positions"] == 8
    assert m["long_term"]["fund_ratio"] == 0.6        # 未传字段补默认
    assert m["short_term"]["max_positions"] == 3       # 未传轨道保持默认
    assert _merge(None)["short_term"]["fund_ratio"] == 0.4
    print("MonitorConfig merge self-check passed")
