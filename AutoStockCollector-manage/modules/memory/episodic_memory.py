"""情境记忆 - 用户中期行为历史"""
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from typing import Any, Dict, List, Optional
from config.database import DatabaseConfig
from modules.memory.models import (
    HoldingRecord, AnalysisHistory, UserProfile, MemoryConfig,
)


class EpisodicMemory:
    """情境记忆：用户历史行为，存于 MongoDB，保留可配置的天数"""

    COLLECTION_USER = "memory_user"
    COLLECTION_HOLDINGS = "memory_holdings"
    COLLECTION_ANALYSES = "memory_analyses"

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = DatabaseConfig.get_database()
        return self._db

    # ==================== 用户画像 ====================

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        doc = self.db[self.COLLECTION_USER].find_one({"user_id": user_id})
        return UserProfile.from_dict(doc) if doc else None

    def save_profile(self, profile: UserProfile):
        doc = profile.to_dict()
        doc["updated_at"] = beijing_now().isoformat()
        if not doc.get("created_at"):
            doc["created_at"] = beijing_now().isoformat()
        self.db[self.COLLECTION_USER].update_one(
            {"user_id": profile.user_id},
            {"$set": doc},
            upsert=True,
        )

    def update_profile(self, user_id: str, updates: Dict[str, Any]):
        updates["updated_at"] = beijing_now().isoformat()
        self.db[self.COLLECTION_USER].update_one(
            {"user_id": user_id},
            {"$set": updates},
            upsert=True,
        )

    # ==================== 持仓记录 ====================

    def record_holding(self, record: HoldingRecord):
        self.db[self.COLLECTION_HOLDINGS].insert_one(record.to_dict())

    def get_current_holdings(self, user_id: str) -> List[HoldingRecord]:
        docs = self.db[self.COLLECTION_HOLDINGS].find({
            "user_id": user_id, "sell_date": None,
        })
        return [HoldingRecord.from_dict(d) for d in docs]

    def get_holding_summary(self, user_id: str) -> Dict[str, Any]:
        holdings = self.get_current_holdings(user_id)
        if not holdings:
            return {"count": 0, "codes": [], "total_invested": 0}

        sector_counts: Dict[str, int] = {}
        for h in holdings:
            sector = self._get_stock_sector(h.code)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        return {
            "count": len(holdings),
            "codes": [h.code for h in holdings],
            "total_invested": sum(h.buy_price * h.shares for h in holdings),
            "sectors": sector_counts,
        }

    def get_trade_history(self, user_id: str, limit: int = 50) -> List[HoldingRecord]:
        docs = self.db[self.COLLECTION_HOLDINGS].find(
            {"user_id": user_id},
            sort=[("buy_date", -1)],
            limit=limit,
        )
        return [HoldingRecord.from_dict(d) for d in docs]

    def _get_stock_sector(self, code: str) -> str:
        try:
            from core.storage.mongo_storage import StockInfoStorage
            info = StockInfoStorage().get_by_code(code)
            return (info or {}).get("industry", "未知")
        except Exception:
            return "未知"

    # ==================== 分析历史 ====================

    def record_analysis(self, history: AnalysisHistory):
        self.db[self.COLLECTION_ANALYSES].insert_one(history.to_dict())

    def get_stock_analyses(self, user_id: str, code: str,
                            limit: int = 5) -> List[Dict]:
        docs = self.db[self.COLLECTION_ANALYSES].find(
            {"user_id": user_id, "code": code},
            sort=[("analysis_date", -1)],
            limit=limit,
        )
        result = []
        for d in docs:
            d.pop("_id", None)
            result.append(d)
        return result

    def get_recent_analyses(self, user_id: str, limit: int = 20) -> List[Dict]:
        docs = self.db[self.COLLECTION_ANALYSES].find(
            {"user_id": user_id},
            sort=[("analysis_date", -1)],
            limit=limit,
        )
        result = []
        for d in docs:
            d.pop("_id", None)
            result.append(d)
        return result

    def get_recent_views(self, user_id: str, limit: int = 10) -> List[str]:
        docs = self.db[self.COLLECTION_ANALYSES].find(
            {"user_id": user_id},
            sort=[("analysis_date", -1)],
            limit=limit,
        )
        seen = set()
        codes = []
        for d in docs:
            code = d.get("code")
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        return codes[:limit]

    def record_feedback(self, user_id: str, analysis_id: str,
                        feedback: str):
        self.db[self.COLLECTION_ANALYSES].update_one(
            {"_id": analysis_id, "user_id": user_id},
            {"$set": {"user_feedback": feedback}},
        )

    # ==================== 清理 ====================

    def cleanup_expired(self):
        cutoff = (beijing_now() - timedelta(
            days=self.config.episodic_retention_days
        )).isoformat()
        for coll in [self.COLLECTION_HOLDINGS, self.COLLECTION_ANALYSES]:
            self.db[coll].delete_many({"analysis_date": {"$lt": cutoff}})
