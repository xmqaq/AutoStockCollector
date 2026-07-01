"""竞价数据快照采集 — 9:25 触发，复用 EastMoney 直连行情。"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from pymongo import UpdateOne

from utils.logger import get_logger
from .config import AuctionConfig

logger = get_logger(__name__)

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = AuctionConfig.FETCH_TIMEOUT

_CHUNK_SIZE = 500  # MongoDB bulk_write 批次大小

_MAX_RETRIES = 3
_RETRY_BACKOFF = [0.5, 1.0, 2.0]  # 指数退避秒数


def _strip_prefix(code: str) -> str:
    for p in ("SH", "SZ", "BJ"):
        if code.startswith(p):
            return code[2:]
    return code


def _fetch_spot_batch() -> Optional[Dict[str, Dict]]:
    """全量拉取实时行情 — 指数退避 + 降级回退。"""
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

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            if attempt > 0:
                backoff = _RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)]
                time.sleep(backoff)

            r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            items = data.get("data", {}).get("diff", [])
            if not items:
                logger.warning(f"[Auction] EastMoney spot returned empty (attempt {attempt + 1})")
                continue

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
                    "volume_ratio": item.get("f10") or 0.0,  # 量比（f10）
                }
            logger.info(f"[Auction] EastMoney spot fetched {len(result)} stocks")
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"[Auction] EastMoney spot error (attempt {attempt + 1}): {e}")

    # 降级回退：尝试从 pa_quotes_cache 读取昨日快照
    logger.warning(f"[Auction] EastMoney failed after {_MAX_RETRIES} attempts, trying cache fallback")
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        cached = list(
            db["pa_quotes_cache"].find(
                {"cache_key": {"$regex": "^kline_"}},
                {"code": 1, "close": 1, "high": 1, "low": 1, "volume": 1, "amount": 1, "_id": 0},
            ).limit(5000)
        )
        if cached:
            result = {}
            for c in cached:
                code = c.get("code", "")
                result[code] = {
                    "code": code,
                    "name": "",
                    "price": c.get("close", 0) or 0.0,
                    "change_pct": 0.0,
                    "change": 0.0,
                    "volume": c.get("volume", 0) or 0.0,
                    "amount": c.get("amount", 0) or 0.0,
                    "high": c.get("high", 0) or 0.0,
                    "low": c.get("low", 0) or 0.0,
                    "open": 0.0,
                    "pre_close": c.get("close", 0) or 0.0,
                    "turnover": 0.0,
                }
            logger.info(f"[Auction] fallback: loaded {len(result)} from pa_quotes_cache")
            return result
    except Exception as cache_err:
        logger.warning(f"[Auction] cache fallback also failed: {cache_err}")

    return None


def collect_auction_data(symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """9:25 后一次性拉取全量行情，返回竞价快照列表。"""
    raw = _fetch_spot_batch()
    if not raw:
        return []

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
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

    # 过滤无效数据 + ST/退市（保留新股 pre_close=0 但 open_price>0）
    results = [r for r in results if r["open_price"] > 0]

    # 标记 ST / 退市 / 次新股（前端和后端建仓时使用）
    _mark_special_stocks(results)

    _save_snapshots_bulk(results)

    logger.info(f"[Auction] collected {len(results)} snapshots")
    return results


def _build_snapshot(results: list, entry: Dict, today: str, now_iso: str):
    op = float(entry.get("open", 0) or 0)
    pc = float(entry.get("pre_close", 0) or 0)
    gap = (op - pc) / pc if pc > 0 else 0.0
    results.append({
        "code": entry.get("code", ""),
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
        "volume_ratio": float(entry.get("volume_ratio", 0) or 0),  # 量比（f10），8 维因子用
        "collected_at": now_iso,
    })


def _save_snapshots_bulk(snapshots: List[Dict]):
    """批量 upsert 到 MongoDB（使用 bulk_write 代替逐条 update_one）。"""
    if not snapshots:
        return
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[AuctionConfig.COLLECTION]

        operations = []
        for snap in snapshots:
            key = f"{snap['date']}_{snap['code']}"
            operations.append(
                UpdateOne(
                    {"_key": key},
                    {"$set": {**snap, "_key": key}},
                    upsert=True,
                )
            )

        for i in range(0, len(operations), _CHUNK_SIZE):
            chunk = operations[i:i + _CHUNK_SIZE]
            col.bulk_write(chunk, ordered=False)

        logger.info(f"[Auction] saved {len(snapshots)} snapshots in {_CHUNK_SIZE}-chunk bulk_write")
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


def _mark_special_stocks(results: List[Dict]):
    """标记 ST、退市、次新股等特殊股票。
    
    添加字段:
      - is_st: 是否 ST/*ST
      - is_delisted: 是否退市
      - is_new_ipo: 是否新股（pre_close=0 且 open>0）
    """
    for r in results:
        name = r.get("name", "")
        r["is_st"] = "ST" in name.upper() or "*ST" in name.upper()
        r["is_delisted"] = "退" in name
        r["is_new_ipo"] = r.get("pre_close", 0) == 0 and r.get("open_price", 0) > 0
