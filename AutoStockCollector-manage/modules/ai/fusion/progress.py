"""融合选股进度管理。独立 fusion_pick_progress 集合，与量化选股 pick_progress 互不干扰。
逻辑参考 modules/ai/engines/picker.py 的同名函数。
"""
from typing import Any, Dict, Optional
from utils.helpers import beijing_now

_COLLECTION = "fusion_pick_progress"
_PROGRESS_KEY = "current"
_STALE_MINUTES = 10  # 进度超过该时长未推进视为运行已死


def update_progress(progress: int, status: str, is_running: bool = True,
                    extra: Optional[Dict] = None) -> None:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = {
            "progress": progress,
            "status": status,
            "is_running": is_running,
            "updated_at": beijing_now(),
        }
        if extra:
            doc.update(extra)
        db[_COLLECTION].update_one(
            {"key": _PROGRESS_KEY}, {"$set": doc}, upsert=True,
        )
    except Exception:
        pass


def get_progress() -> Dict[str, Any]:
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db[_COLLECTION].find_one({"key": _PROGRESS_KEY}, {"_id": 0})
        if not doc:
            return {"is_running": False, "progress": 0, "status": ""}
        # 僵尸进度防护：运行进程被杀时文档永远停在中间态
        updated = doc.get("updated_at")
        if doc.get("is_running") and updated is not None:
            if beijing_now() - updated > timedelta(minutes=_STALE_MINUTES):
                doc["is_running"] = False
                doc["status"] = f"{doc.get('status', '')}（运行已中断，可重新发起）"
        return doc
    except Exception:
        return {"is_running": False, "progress": 0, "status": ""}


def acquire_run_lock() -> bool:
    """跨进程选股互斥：原子抢占 fusion_pick_progress 文档。
    仅当无运行中任务、或运行已超时僵死时才能拿到锁。
    DB 抖动时放行（降级为无锁，不阻塞选股）。
    """
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        now = beijing_now()
        stale_before = now - timedelta(minutes=_STALE_MINUTES)
        claimed = db[_COLLECTION].find_one_and_update(
            {"key": _PROGRESS_KEY,
             "$or": [{"is_running": {"$ne": True}},
                     {"updated_at": {"$lt": stale_before}}]},
            {"$set": {"is_running": True, "progress": 5,
                      "status": "正在加载股票池...", "updated_at": now}},
        )
        if claimed is not None:
            return True
        if db[_COLLECTION].find_one({"key": _PROGRESS_KEY}) is None:
            db[_COLLECTION].update_one(
                {"key": _PROGRESS_KEY},
                {"$set": {"is_running": True, "progress": 5,
                          "status": "正在加载股票池...", "updated_at": now}},
                upsert=True,
            )
            return True
        return False
    except Exception:
        return True
