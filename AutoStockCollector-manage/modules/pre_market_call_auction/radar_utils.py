"""盘前竞价雷达 — 共享工具函数（行业查询、时间、排序阈值等）。"""
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

_SHANGHAI_TZ = timezone(timedelta(hours=8))

# 行业数据进程级缓存（TTL 1h，行业归属几乎不变）
_industry_cache: Dict[str, str] = {}
_industry_cache_ts: float = 0
_INDUSTRY_CACHE_TTL = 3600


def now_shanghai() -> datetime:
    """返回上海/北京时间 (UTC+8) 的当前时间。"""
    return datetime.now(_SHANGHAI_TZ)


def today_str() -> str:
    return now_shanghai().strftime("%Y-%m-%d")


def tomorrow_str() -> str:
    from datetime import timedelta as td
    return (now_shanghai() + td(days=1)).strftime("%Y-%m-%d")


def _load_all_industries() -> Dict[str, str]:
    """全量加载行业归属到缓存。"""
    global _industry_cache, _industry_cache_ts
    now = time.time()
    if _industry_cache and (now - _industry_cache_ts) < _INDUSTRY_CACHE_TTL:
        return _industry_cache
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        result = {}
        for doc in db["stock_info"].find({}, {"code": 1, "所属行业": 1}):
            c = doc.get("code", "")
            ind = doc.get("所属行业", "")
            if c:
                result[c] = ind or ""
        _industry_cache = result
        _industry_cache_ts = now
        logger.info(f"[AuctionRadar] loaded {len(result)} industry mappings into cache")
        return result
    except Exception as e:
        logger.warning(f"[AuctionRadar] industry cache load error: {e}")
        return _industry_cache or {}


def batch_get_industries(codes: List[str]) -> Dict[str, str]:
    """批量查询行业归属，返回 {code: industry} 映射。

    使用进程级 TTL 缓存（1h），避免每次扫描都查 MongoDB。
    """
    if not codes:
        return {}
    all_industries = _load_all_industries()
    return {c: all_industries.get(c, "") for c in codes}


def compute_sector_gaps(
    snapshots: List[Dict],
    industry_map: Dict[str, str],
) -> Dict[str, float]:
    """计算各板块平均跳空幅度。"""
    sector_stocks: Dict[str, List[float]] = {}
    for snap in snapshots:
        code = snap.get("code", "")
        industry = industry_map.get(code, "")
        if not industry:
            continue
        gap = snap.get("gap_pct", 0.0)
        if industry not in sector_stocks:
            sector_stocks[industry] = []
        sector_stocks[industry].append(gap)

    result = {}
    for ind, gaps in sector_stocks.items():
        if gaps:
            result[ind] = sum(gaps) / len(gaps)
    return result


def compute_auction_thresholds(amounts: List[float]):
    """预计算竞价金额排名的阈值（降序排列后取分位值）。

    Returns:
        (sorted_desc, neg_sorted_desc, thresholds_dict)
        - sorted_desc: 降序列表，用于线性扫描
        - neg_sorted_desc: 负值升序列表，用于 bisect O(log N) 查找百分位
        - thresholds_dict: 预计算的分位阈值
    """
    sorted_desc = sorted(amounts, reverse=True)
    n = len(sorted_desc)
    if n == 0:
        return [], [], {"median": 0, "bottom20_pct": 0, "top20_pct": 0, "vol_min_threshold": 0}

    from .config import AuctionConfig
    vol_min_idx = int(n * (1 - AuctionConfig.TRAP_VOLUME_RATIO_MIN))

    neg_sorted_desc = [-x for x in sorted_desc]

    thresholds = {
        "median": sorted_desc[n // 2],
        "bottom20_pct": sorted_desc[max(n // 5 - 1, 0)],
        "top20_pct": sorted_desc[min(n * 4 // 5, n - 1)],
        "vol_min_threshold": sorted_desc[min(vol_min_idx, n - 1)],
    }
    return sorted_desc, neg_sorted_desc, thresholds
