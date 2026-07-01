"""盘前竞价雷达 — 扫描结果追踪 & 历史表现统计。"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import RadarResult, RadarStock
from .radar_utils import now_shanghai

logger = get_logger(__name__)

COLLECTION = "auction_performance"


def record_scan_result(result: RadarResult):
    """将本次扫描结果存入表现追踪集合（upsert 去重，防止重复扫描产生重复记录）。"""
    if not result or not result.top_stocks:
        return
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]

        now_iso = now_shanghai().isoformat()
        operations = []
        for s in result.top_stocks:
            key = {"code": s.symbol, "date": result.date}
            operations.append(
                UpdateOne(
                    key,
                    {"$set": {
                        "code": s.symbol,
                        "name": s.name,
                        "date": result.date,
                        "scan_time": result.scan_time,
                        "strategy": "auction_radar",
                        "strength_score": s.strength_score,
                        "gap_pct": s.gap_pct,
                        "auction_amount": s.auction_amount,
                        "industry": s.industry,
                        "is_trap": s.trap_warning is not None,
                        "trap_type": s.trap_warning.trap_type if s.trap_warning else "",
                        "result": "pending",
                        "return_pct": None,
                        "exit_reason": "",
                        "updated_at": now_iso,
                        "created_at": now_iso,
                    }},
                    upsert=True,
                )
            )

        if operations:
            col.bulk_write(operations, ordered=False)
            logger.info(f"[AuctionPerformance] recorded/upserted {len(operations)} records")
    except Exception as e:
        logger.warning(f"[AuctionPerformance] record error: {e}")


def update_result(code: str, date: str, return_pct: float, exit_reason: str = ""):
    """更新单只股票扫描后的实际表现。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]
        result = "win" if return_pct > 0 else "loss"
        col.update_one(
            {"code": code, "date": date},
            {"$set": {
                "result": result,
                "return_pct": round(return_pct, 4),
                "exit_reason": exit_reason,
                "updated_at": now_shanghai().isoformat(),
            }},
        )
    except Exception as e:
        logger.warning(f"[AuctionPerformance] update error: {e}")


def get_performance_stats(
    days: int = 30,
    min_score: int = 0,
) -> Dict[str, Any]:
    """按强度分组统计历史表现。使用 numeric min_score 排序而非字符串。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]

        cutoff = (now_shanghai() - timedelta(days=days)).strftime("%Y-%m-%d")
        match: Dict = {"date": {"$gte": cutoff}, "result": {"$ne": "pending"}}
        if min_score > 0:
            match["strength_score"] = {"$gte": min_score}

        pipeline = [
            {"$match": match},
            {
                "$bucket": {
                    "groupBy": "$strength_score",
                    "boundaries": [0, 40, 60, 80, 101],
                    "default": "unknown",
                    "output": {
                        "count": {"$sum": 1},
                        "wins": {"$sum": {"$cond": [{"$eq": ["$result", "win"]}, 1, 0]}},
                        "avg_return": {"$avg": "$return_pct"},
                        "total_return": {"$sum": "$return_pct"},
                    },
                }
            },
            {"$sort": {"_id": -1}},
        ]

        stats = list(col.aggregate(pipeline))
        # 将 bucket _id 转为可读标签
        buckets = []
        for s in stats:
            _id = s.pop("_id", 0)
            labels = {0: "0-39", 40: "40-59", 60: "60-79", 80: "80-100"}
            s["score_bracket"] = labels.get(_id, str(_id))
            buckets.append(s)

        return {"buckets": buckets, "days": days}
    except Exception as e:
        logger.warning(f"[AuctionPerformance] stats error: {e}")
        return {"buckets": [], "days": days, "error": str(e)}


def get_recent_results(days: int = 7, limit: int = 50) -> List[Dict]:
    """最近 N 天内的扫描记录。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]
        cutoff = (now_shanghai() - timedelta(days=days)).strftime("%Y-%m-%d")
        docs = list(
            col.find({"date": {"$gte": cutoff}}, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        return docs
    except Exception as e:
        logger.warning(f"[AuctionPerformance] recent results error: {e}")
        return []
