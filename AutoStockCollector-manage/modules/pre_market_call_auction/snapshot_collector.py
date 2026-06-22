"""竞价数据快照采集 — 9:25 触发，复用 EastMoney 直连行情。"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig

logger = get_logger(__name__)

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = AuctionConfig.FETCH_TIMEOUT


def _strip_prefix(code: str) -> str:
    for p in ("SH", "SZ", "BJ"):
        if code.startswith(p):
            return code[2:]
    return code


def _market(code: str) -> str:
    c = _strip_prefix(code)
    if c.startswith(("6", "9")):
        return "1"
    return "0"


def _fetch_spot_batch() -> Optional[Dict[str, Dict]]:
    """全量拉取实时行情 — 同 PA fetcher 的 EastMoney 模式。"""
    import requests

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "6000",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18,f10,f8",
    }
    try:
        r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", {}).get("diff", [])
        if not items:
            logger.warning("[Auction] EastMoney spot returned empty")
            return None

        result = {}
        for item in items:
            code = str(item.get("f12", ""))
            result[code] = {
                "code": code,
                "name": str(item.get("f14", "")),
                "price": item.get("f2") or 0.0,
                "change_pct": item.get("f3") or 0.0,
                "change": item.get("f4") or 0.0,
                "volume": item.get("f5") or 0.0,
                "amount": item.get("f6") or 0.0,
                "high": item.get("f15") or 0.0,
                "low": item.get("f16") or 0.0,
                "open": item.get("f17") or 0.0,
                "pre_close": item.get("f18") or 0.0,
                "turnover": item.get("f8") or 0.0,
            }
        logger.info(f"[Auction] EastMoney spot fetched {len(result)} stocks")
        return result
    except Exception as e:
        logger.warning(f"[Auction] EastMoney spot error: {e}")
        return None


def collect_auction_data(symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """9:25 后一次性拉取全量行情，返回竞价快照列表。

    Args:
        symbols: 指定股票池，None 则全市场。
    Returns:
        [{code, name, open_price, pre_close, gap_pct, volume, amount, ...}]
    """
    raw = _fetch_spot_batch()
    if not raw:
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().isoformat()
    results = []

    if symbols:
        for s in symbols:
            raw_code = _strip_prefix(s)
            entry = raw.get(raw_code)
            if not entry:
                continue
            _build_snapshot(results, entry, today, now_iso)
    else:
        for entry in raw.values():
            _build_snapshot(results, entry, today, now_iso)

    # 跳过无数据或停牌
    results = [r for r in results if r["pre_close"] > 0 and r["open_price"] > 0]

    # 保存到 MongoDB
    _save_snapshots(results)

    logger.info(f"[Auction] collected {len(results)} snapshots")
    return results


def _build_snapshot(results: list, entry: Dict, today: str, now_iso: str):
    op = float(entry.get("open", 0) or 0)
    pc = float(entry.get("pre_close", 0) or 0)
    gap = (op - pc) / pc if pc > 0 else 0.0
    results.append({
        "code": entry["code"],
        "name": entry.get("name", ""),
        "date": today,
        "open_price": op,
        "pre_close": pc,
        "high": float(entry.get("high", 0) or 0),
        "low": float(entry.get("low", 0) or 0),
        "volume": float(entry.get("volume", 0) or 0),
        "amount": float(entry.get("amount", 0) or 0),
        "gap_pct": round(gap * 100, 2),
        "turnover": float(entry.get("turnover", 0) or 0),
        "collected_at": now_iso,
    })


def _save_snapshots(snapshots: List[Dict]):
    """批量 upsert 到 MongoDB。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[AuctionConfig.COLLECTION]
        for snap in snapshots:
            key = f"{snap['date']}_{snap['code']}"
            col.update_one(
                {"_key": key},
                {"$set": {**snap, "_key": key}},
                upsert=True,
            )
    except Exception as e:
        logger.warning(f"[Auction] save snapshots error: {e}")


def get_snapshots_from_db(date: str, codes: Optional[List[str]] = None) -> List[Dict]:
    """从 MongoDB 读取已存的竞价快照。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        query = {"date": date}
        if codes:
            query["code"] = {"$in": codes}
        docs = list(db[AuctionConfig.COLLECTION].find(query, {"_id": 0, "_key": 0}))
        return docs
    except Exception as e:
        logger.warning(f"[Auction] read snapshots error: {e}")
        return []
