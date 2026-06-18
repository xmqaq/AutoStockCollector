"""龙虎榜分析器 — 统计个股近期上榜次数、机构/游资动向"""
from typing import Any, Dict
from core.storage.mongo_storage import DragonTigerStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class DragonTigerAnalyzer:
    DAYS = 10

    def __init__(self):
        self._storage = DragonTigerStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        try:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=self.DAYS)).strftime("%Y-%m-%d")
            bare = code[2:] if code[:2] in ("SH", "SZ") else code
            candidates = [code, bare]
            records = list(self._storage.find_many(
                {"date": {"$gte": cutoff}, "code": {"$in": candidates}},
                sort=[("date", -1)],
            ))
            if not records:
                return {}

            appearances = len(records)
            total_net_buy = 0.0
            inst_net_buy = 0.0
            hot_unknown_buy = 0.0
            top_brokers = []

            for r in records:
                total_net_buy += float(r.get("net_buy", r.get("net_amount", 0) or 0))
                for seat in (r.get("buy_seats", r.get("details", [])) or []):
                    if "机构" in (seat.get("name", "") or ""):
                        inst_net_buy += float(seat.get("amount", seat.get("buy", 0) or 0))
                reasons = r.get("reason", r.get("cause", ""))
                top_brokers.append(r.get("broker", r.get("dept_name", "")))

            hot_unknown_buy = total_net_buy - inst_net_buy

            return {
                "appearances": appearances,
                "total_net_buy": round(total_net_buy, 2),
                "institution_net_buy": round(inst_net_buy, 2),
                "hot_unknown_net_buy": round(max(hot_unknown_buy, 0), 2),
                "top_brokers": list(set(filter(None, top_brokers)))[:3],
            }
        except Exception as e:
            logger.debug(f"DragonTiger analyze {code} failed: {e}")
            return {}
