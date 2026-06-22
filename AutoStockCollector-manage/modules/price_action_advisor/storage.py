"""价格行为学 — 逐股信号历史持久化。
每次 scan 完成后为每个有信号的股票保存一条快照，支持按股票查看历史信号轨迹。"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class PaSignalHistoryStorage:
    """PA 信号历史存储 — 每只股票每次 scan 一条记录。"""

    COLLECTION = "pa_signal_history"

    def __init__(self):
        from config.database import DatabaseConfig
        self.db = DatabaseConfig.get_database()

    def save_snapshot(self, code: str, name: str, signal: Dict[str, Any], scan_id: str, scan_time: datetime):
        """保存单只股票的信号快照。"""
        doc = {
            "code": code,
            "name": name,
            "signal": signal.get("signal", ""),
            "confidence": signal.get("confidence", 0),
            "trend": signal.get("trend", ""),
            "current_price": signal.get("current_price", 0.0),
            "reasons": signal.get("reasons", []),
            "patterns": signal.get("patterns", []),
            "htf_trend": signal.get("htf_trend"),
            "htf_timeframe": signal.get("htf_timeframe"),
            "htf_structure": signal.get("htf_structure"),
            "htf_mature": signal.get("htf_mature", False),
            "trend_warning": signal.get("trend_warning"),
            "trade_plan": signal.get("trade_plan"),
            "backtest": signal.get("backtest"),
            "scan_id": scan_id,
            "created_at": scan_time,
        }
        self.db[self.COLLECTION].insert_one(doc)

    def get_history(self, code: str, days: int = 60) -> List[Dict[str, Any]]:
        """获取某只股票的历史信号轨迹。"""
        cutoff = datetime.now() - timedelta(days=days)
        docs = list(
            self.db[self.COLLECTION]
            .find({"code": code, "created_at": {"$gte": cutoff}})
            .sort("created_at", -1)
            .limit(100)
        )
        for d in docs:
            d.pop("_id", None)
        return docs

    def get_latest_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """获取某只股票的最新信号。"""
        d = self.db[self.COLLECTION].find_one(
            {"code": code}, sort=[("created_at", -1)],
        )
        if d:
            d.pop("_id", None)
        return d

    def get_codes_with_signal(self, signal: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """查询近期有信号的股票列表。"""
        cutoff = datetime.now() - timedelta(days=days)
        match = {"created_at": {"$gte": cutoff}}
        if signal:
            match["signal"] = signal
        pipeline = [
            {"$match": match},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$code",
                "code": {"$first": "$code"},
                "name": {"$first": "$name"},
                "signal": {"$first": "$signal"},
                "confidence": {"$first": "$confidence"},
                "trend": {"$first": "$trend"},
                "current_price": {"$first": "$current_price"},
                "created_at": {"$first": "$created_at"},
            }},
            {"$sort": {"confidence": -1}},
            {"$limit": 200},
        ]
        docs = list(self.db[self.COLLECTION].aggregate(pipeline))
        for d in docs:
            d.pop("_id", None)
        return docs

    def delete_old(self, days: int = 180):
        """清理过期历史记录。"""
        cutoff = datetime.now() - timedelta(days=days)
        result = self.db[self.COLLECTION].delete_many({"created_at": {"$lt": cutoff}})
        if result.deleted_count:
            logger.info(f"[PaSignalHistory] cleaned {result.deleted_count} records older than {days} days")
