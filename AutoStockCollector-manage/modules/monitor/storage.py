from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from core.storage.mongo_storage import MongoStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class MonitorStorage:
    """AI 监控数据存储 — 信号 + 历史轨迹 + 配置"""

    SIGNALS_COL = "monitor_signals"
    HISTORY_COL = "monitor_signal_history"

    def __init__(self):
        from config.database import DatabaseConfig
        self.db = DatabaseConfig.get_database()

    # ── 当前信号 ──

    def upsert_signal(self, code: str, signal_doc: Dict[str, Any]):
        doc = dict(signal_doc)
        doc["_updated_at"] = datetime.now()
        self.db[self.SIGNALS_COL].update_one(
            {"code": code},
            {"$set": doc},
            upsert=True,
        )

    def get_all_signals(self) -> List[Dict[str, Any]]:
        docs = list(self.db[self.SIGNALS_COL].find().sort("_updated_at", -1))
        for d in docs:
            d.pop("_id", None)
        return docs

    def get_signal(self, code: str) -> Optional[Dict[str, Any]]:
        d = self.db[self.SIGNALS_COL].find_one({"code": code})
        if d:
            d.pop("_id", None)
        return d

    def clear_signals(self):
        self.db[self.SIGNALS_COL].delete_many({})
        logger.info("Cleared all monitor signals")

    # ── 信号历史 ──

    def save_history(self, code: str, snapshot: Dict[str, Any]):
        doc = dict(snapshot)
        doc["code"] = code
        doc["created_at"] = datetime.now().isoformat()
        if "signal_date" not in doc:
            doc["signal_date"] = datetime.now().strftime("%Y-%m-%d")
        self.db[self.HISTORY_COL].insert_one(doc)

    def get_history(self, code: str, days: int = 30) -> List[Dict[str, Any]]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        docs = list(
            self.db[self.HISTORY_COL]
            .find({"code": code, "created_at": {"$gte": cutoff}})
            .sort("created_at", -1)
            .limit(100)
        )
        for d in docs:
            d.pop("_id", None)
        return docs
