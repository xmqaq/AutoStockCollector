"""Detect rating changes in research reports and emit signal events."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from config.database import DatabaseConfig
from core.storage.mongo_storage import ResearchReportStorage
from utils.logger import get_logger
from utils.helpers import beijing_now

logger = get_logger(__name__)

_RATING_ORDER = {
    "买入": 5, "Buy": 5,
    "增持": 4, "推荐": 4, "Outperform": 4, "Overweight": 4,
    "持有": 3, "中性": 3, "Hold": 3, "Neutral": 3, "Market Perform": 3,
    "减持": 2, "Underperform": 2, "Underweight": 2,
    "卖出": 1, "Sell": 1, "Reduce": 1,
}
_SIGNALS_COLLECTION = "research_report_signals"


def _rating_score(rating: str) -> int:
    for k, v in _RATING_ORDER.items():
        if k in rating:
            return v
    return 3


def detect_rating_changes(code: str = "", days: int = 365) -> List[Dict[str, Any]]:
    """Detect rating changes for a stock (or all stocks) within the time window.
    Returns list of change events.
    """
    storage = ResearchReportStorage()
    cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).strftime("%Y-%m-%d")

    query: Dict[str, Any] = {"date": {"$gte": cutoff}}
    if code:
        query["code"] = code

    reports = list(storage.collection.find(
        query,
        {"code": 1, "name": 1, "title": 1, "date": 1, "org": 1, "rating": 1, "report_id": 1},
        sort=[("code", 1), ("date", 1)],
    ))

    changes = []
    # Filter out reports without ratings
    reports = [r for r in reports if r.get("rating")]
    # Group by code
    by_code: Dict[str, List[Dict]] = {}
    for r in reports:
        by_code.setdefault(r["code"], []).append(r)

    for c, rs in by_code.items():
        if len(rs) < 2:
            continue
        prev = rs[0]
        for curr in rs[1:]:
            prev_score = _rating_score(prev.get("rating", ""))
            curr_score = _rating_score(curr.get("rating", ""))
            if prev_score != curr_score:
                direction = "upgrade" if curr_score > prev_score else "downgrade"
                changes.append({
                    "code": c,
                    "name": curr.get("name", ""),
                    "from_rating": prev.get("rating", ""),
                    "to_rating": curr.get("rating", ""),
                    "direction": direction,
                    "org": curr.get("org", ""),
                    "date": curr.get("date", ""),
                    "title": curr.get("title", ""),
                    "prev_report_id": prev.get("report_id", ""),
                    "report_id": curr.get("report_id", ""),
                    "detected_at": beijing_now().isoformat(),
                })
            prev = curr

    return changes


def save_rating_changes(changes: List[Dict]) -> int:
    """Deduplicate and persist rating change events."""
    if not changes:
        return 0
    col = DatabaseConfig.get_database()[_SIGNALS_COLLECTION]
    col.create_index([("code", 1), ("date", -1)])
    col.create_index([("direction", 1), ("detected_at", -1)])

    saved = 0
    for c in changes:
        key = {"code": c["code"], "report_id": c["report_id"]}
        try:
            col.update_one(key, {"$set": c}, upsert=True)
            saved += 1
        except Exception as e:
            logger.warning(f"[RatingChange] upsert error: {e}")
    logger.info(f"[RatingChange] Saved {saved}/{len(changes)} rating change events")
    return saved


def run_rating_change_detection(code: str = "", days: int = 365) -> Dict[str, Any]:
    """Full pipeline: detect → save → return stats."""
    changes = detect_rating_changes(code=code, days=days)
    saved = save_rating_changes(changes)
    return {
        "success": True,
        "total_detected": len(changes),
        "saved": saved,
    }


def get_stock_rating_timeline(code: str, days: int = 365) -> List[Dict]:
    """Get rating timeline for a specific stock from research reports."""
    storage = ResearchReportStorage()
    cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).strftime("%Y-%m-%d")
    reports = list(storage.collection.find(
        {"code": code, "date": {"$gte": cutoff}},
        {"title": 1, "date": 1, "org": 1, "rating": 1, "target_price_high": 1, "target_price_low": 1, "report_id": 1, "generated_abstract": 1},
        sort=[("date", -1)],
    ))
    for r in reports:
        r.pop("_id", None)
    return reports


def get_recent_signals(days: int = 7, limit: int = 50) -> List[Dict]:
    """Get recent rating upgrade/downgrade signals."""
    col = DatabaseConfig.get_database()[_SIGNALS_COLLECTION]
    cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).isoformat()
    results = list(col.find(
        {"detected_at": {"$gte": cutoff}},
        sort=[("detected_at", -1)],
        limit=limit,
    ))
    for r in results:
        r.pop("_id", None)
    return results
