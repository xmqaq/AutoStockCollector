from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from core.storage.mongo_storage import MongoStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class MonitorStorage:
    """AI 监控数据存储 — 信号 + 历史轨迹 + 实时快照"""

    SIGNALS_COL = "monitor_signals"
    HISTORY_COL = "monitor_signal_history"
    REALTIME_COL = "monitor_realtime"  # 实时行情+资金流快照（独立集合，不污染 fund_flow 日级数据）

    def __init__(self):
        from config.database import DatabaseConfig
        self.db = DatabaseConfig.get_database()
        # monitor_signal_history TTL：created_at 是 isoformat 字符串无法直接做 TTL，
        # 用独立 BSON Date 字段 _expire_at 驱动 90 天自动过期，防盘中 3min 刷新膨胀。
        try:
            self.db[self.HISTORY_COL].create_index(
                "_expire_at", expireAfterSeconds=90 * 86400
            )
        except Exception:
            pass  # 索引已存在或不可用，忽略

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

    # ── 来源（生命周期）增量更新 ──

    def add_source(self, code: str, source: str) -> None:
        """在 sources 数组追加一个来源（去重）。文档不存在则不创建
        （占位创建由 MonitorLifecycle 负责，保持职责单一）。"""
        self.db[self.SIGNALS_COL].update_one(
            {"code": code}, {"$addToSet": {"sources": source}}
        )

    def remove_source(self, code: str, source: str) -> Dict[str, Any]:
        """从 sources 数组移除一个来源；移除后 sources 为空则删除整条文档。"""
        self.db[self.SIGNALS_COL].update_one(
            {"code": code}, {"$pull": {"sources": source}}
        )
        doc = self.db[self.SIGNALS_COL].find_one({"code": code}, {"sources": 1})
        remaining = (doc or {}).get("sources", []) or []
        if doc is not None and not remaining:
            self.db[self.SIGNALS_COL].delete_one({"code": code})
            return {"removed_doc": True, "remaining_sources": []}
        return {"removed_doc": False, "remaining_sources": remaining}

    def get_signals_by_source(self, source: str) -> List[Dict[str, Any]]:
        """sources 数组包含指定来源的所有记录。"""
        docs = list(self.db[self.SIGNALS_COL].find({"sources": source}))
        for d in docs:
            d.pop("_id", None)
        return docs

    # ── 信号历史 ──

    def save_history(self, code: str, snapshot: Dict[str, Any]):
        doc = dict(snapshot)
        doc["code"] = code
        now = datetime.now()
        doc["created_at"] = now.isoformat()
        doc["_expire_at"] = now  # BSON Date，驱动 TTL 索引 90 天自动过期
        if "signal_date" not in doc:
            doc["signal_date"] = now.strftime("%Y-%m-%d")
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

    # ── 实时快照（独立集合，不写 fund_flow） ──

    def upsert_realtime(self, code: str, doc: Dict[str, Any]):
        doc = dict(doc)
        doc["code"] = code
        doc["updated_at"] = datetime.now()
        self.db[self.REALTIME_COL].update_one(
            {"code": code}, {"$set": doc}, upsert=True,
        )

    def get_realtime(self, code: str) -> Optional[Dict[str, Any]]:
        d = self.db[self.REALTIME_COL].find_one({"code": code})
        if d:
            d.pop("_id", None)
        return d

    def get_realtime_many(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        if not codes:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for d in self.db[self.REALTIME_COL].find({"code": {"$in": codes}}):
            d.pop("_id", None)
            out[d.get("code", "")] = d
        return out
