"""行业主题聚合 — 从研报标题中提取热点主题和关注标的。"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import Counter

from utils.logger import get_logger
from .extractor import ReportSignal

logger = get_logger(__name__)


def _load_chain_templates() -> Dict[str, Any]:
    """加载预置行业板块模板。"""
    path = Path(__file__).parent / "chain_templates.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load chain_templates.json: {e}")
    return {}


class SupplyChainAggregator:
    """行业信号聚合器 — 整理 LLM 分析出的热点主题和关注标的。"""

    def __init__(self):
        self._sectors_cache = None

    def list_sectors(self) -> List[Dict[str, Any]]:
        """返回支持分析的行业列表及其描述。"""
        if self._sectors_cache is not None:
            return self._sectors_cache
        templates = _load_chain_templates()
        result = []
        for name, info in templates.items():
            desc = info.get("description", "")
            stock_count = len(info.get("representative_stocks", []))
            link_count = len(info.get("links", []))
            result.append({
                "name": name,
                "description": desc,
                "stock_count": stock_count,
                "link_count": link_count,
            })
        self._sectors_cache = result
        return result

    def aggregate(
        self, sector: str, signals: List[ReportSignal],
    ) -> Dict[str, Any]:
        """聚合一个行业的 LLM 分析结果。"""
        if not signals:
            return {"sector": sector, "themes": [], "total_signals": 0, "sentiment": "neutral"}

        sig = signals[0]
        themes = sig.themes if hasattr(sig, 'themes') else []
        hot_count = sum(1 for t in themes if t.get("hot"))
        sentiment = sig.sentiment if hasattr(sig, 'sentiment') else "neutral"
        rating_momentum = getattr(sig, 'rating_momentum', 'neutral')
        rating_up = getattr(sig, 'rating_up', 0)
        rating_down = getattr(sig, 'rating_down', 0)
        rating_hold = getattr(sig, 'rating_hold', 0)
        avg_target = getattr(sig, 'avg_target_price', None)

        return {
            "sector": sector,
            "themes": themes,
            "total_signals": 1,
            "sentiment": sentiment,
            "rating_momentum": rating_momentum,
            "rating_up": rating_up,
            "rating_down": rating_down,
            "rating_hold": rating_hold,
            "avg_target_price": avg_target,
            "hot_theme_count": hot_count,
            "summary": getattr(sig, 'summary', ''),
            "theme_summary": getattr(sig, 'theme_summary', ''),
        }

    def extract_candidates(
        self, sector: str, signals: List[ReportSignal],
    ) -> List[Dict[str, Any]]:
        """从分析结果中提取候选标的。"""
        if not signals:
            return []

        sig = signals[0]
        stocks = getattr(sig, 'key_stocks', [])
        rating_positive = getattr(sig, 'rating_up', 0)
        rating_negative = getattr(sig, 'rating_down', 0)
        seen = {}
        for stock in stocks:
            code = stock.get("code", "")
            if not code:
                continue
            if code not in seen:
                seen[code] = {
                    "code": code,
                    "name": stock.get("name", ""),
                    "reason": stock.get("reason", ""),
                    "mention_count": 1,
                    "confidence": getattr(sig, 'confidence', 3),
                    "sectors": [sector],
                    "rating_up": rating_positive,
                    "rating_down": rating_negative,
                }
            else:
                seen[code]["mention_count"] += 1

        candidates = list(seen.values())
        candidates.sort(key=lambda x: x.get("mention_count", 0), reverse=True)
        return candidates
