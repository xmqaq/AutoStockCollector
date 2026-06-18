"""板块/概念分析器 — 查询股票所属概念、行业板块资金流"""
from typing import Any, Dict, List, Optional
from core.storage.mongo_storage import BlockStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class BlockAnalyzer:
    def __init__(self):
        self._storage = BlockStorage()

    def get_concepts(self, code: str) -> List[str]:
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        try:
            docs = self._storage.find_many({
                "block_type": "concept",
                "stocks.code": {"$regex": f"{bare}$"},
            })
            names = sorted(set(d.get("block_name", "") or d.get("name", "") for d in docs))
            return names[:8]
        except Exception as e:
            logger.debug(f"Get concepts for {code} failed: {e}")
            return []

    def get_sector_flow(self, code: str) -> Dict[str, Any]:
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        try:
            doc = self._storage.find_one({
                "block_type": "industry",
                "stocks.code": {"$regex": f"{bare}$"},
            })
            if not doc:
                return {}
            name = doc.get("block_name", "") or doc.get("name", "")
            return {
                "industry_name": name,
                "industry_change": float(doc.get("涨跌幅", 0) or 0),
                "industry_net_flow": float(doc.get("net_flow", 0) or 0),
                "industry_total_amount": float(doc.get("成交额", 0) or 0),
            }
        except Exception as e:
            logger.debug(f"Get sector flow for {code} failed: {e}")
            return {}

    def get_concept_details(self, code: str) -> Dict[str, Any]:
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        try:
            docs = list(self._storage.find_many({
                "block_type": "concept",
                "stocks.code": {"$regex": f"{bare}$"},
            }))
            concepts = []
            for d in docs:
                name = d.get("block_name", "") or d.get("name", "")
                change = float(d.get("涨跌幅", 0) or 0)
                net_flow = float(d.get("net_flow", 0) or 0)
                concepts.append({
                    "name": name,
                    "change_pct": round(change, 2),
                    "net_flow": round(net_flow, 2),
                })
            concepts.sort(key=lambda x: abs(x["net_flow"]), reverse=True)
            hot = [c for c in concepts if c["change_pct"] > 2 or c["net_flow"] > 1e7]
            return {
                "concepts": [c["name"] for c in concepts[:8]],
                "concept_details": concepts[:5],
                "hot_concept": bool(hot),
                "hot_count": len(hot),
            }
        except Exception as e:
            logger.debug(f"Get concept details for {code} failed: {e}")
            return {}
