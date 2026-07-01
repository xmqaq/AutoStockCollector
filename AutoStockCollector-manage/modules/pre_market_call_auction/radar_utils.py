"""盘前竞价雷达 — 共享工具函数（行业查询、时间、排序阈值、代码转换、行情、ATR）。

共享函数集中于此，供模块内各文件及 auto_trading 模块引用，避免循环依赖
（原 intraday_tracker 的 _strip_prefix_from_code/_batch_tencent_quotes/_estimate_atr
被 auto_trading 反向依赖，现统一迁到此处的 radar_utils，单向依赖）。
"""
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

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


# ── 代码转换（迁自 intraday_tracker，供 auto_trading 共享）─────────────────

def strip_prefix_from_code(code: str) -> str:
    """去掉代码的交易所前缀（sh/sz/bj，大小写不敏感）。"""
    code_lower = code.lower()
    for p in ("sh", "sz", "bj"):
        if code_lower.startswith(p):
            return code[len(p):]
    return code


# 向后兼容旧名（auto_trading 等仍以 _strip_prefix_from_code 引用）
_strip_prefix_from_code = strip_prefix_from_code


def to_tencent_code(code: str) -> str:
    """裸代码 → 腾讯行情前缀（sh/sz/bj + 小写）。"""
    bare = strip_prefix_from_code(code).upper()
    if bare.startswith("6"):
        return f"sh{bare}"
    if bare.startswith(("0", "3")):
        return f"sz{bare}"
    if bare.startswith(("8", "4")):
        return f"bj{bare}"
    return f"sh{bare}"


_to_tencent_code = to_tencent_code  # 向后兼容


# ── 腾讯行情批量报价（迁自 intraday_tracker）──────────────────────────────

def batch_tencent_quotes(codes: List[str]) -> Dict[str, float]:
    """批量取腾讯行情现价。codes 需是带前缀的腾讯代码（如 sh600000）。

    返回 {tencent_code: price}。注意：本函数只返回现价，不含昨收。
    """
    result: Dict[str, float] = {}
    if not codes:
        return result
    try:
        import requests as _req
        query = ",".join(c.lower() for c in codes)
        r = _req.get(
            f"https://qt.gtimg.cn/q={query}",
            proxies={"http": "", "https": ""},
            timeout=8,
        )
        for code in codes:
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if not m:
                continue
            parts = m.group(1).split("~")
            # parts[3]=现价 parts[4]=昨收
            if len(parts) > 4 and parts[3]:
                try:
                    price = float(parts[3])
                    if price > 0:
                        result[code] = price
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"[radar_utils] tencent batch error: {e}")
    return result


# 向后兼容旧名
_batch_tencent_quotes = batch_tencent_quotes


def batch_tencent_quotes_full(codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
    """批量取腾讯行情，返回 {tencent_code: {price, prev_close}}。"""
    result: Dict[str, Dict[str, Optional[float]]] = {}
    if not codes:
        return result
    try:
        import requests as _req
        query = ",".join(c.lower() for c in codes)
        r = _req.get(
            f"https://qt.gtimg.cn/q={query}",
            proxies={"http": "", "https": ""},
            timeout=8,
        )
        for code in codes:
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if not m:
                continue
            parts = m.group(1).split("~")
            if len(parts) > 4:
                try:
                    price = float(parts[3]) if parts[3] else None
                    prev = float(parts[4]) if parts[4] else None
                    if price and price > 0:
                        result[code] = {"price": price, "prev_close": prev}
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"[radar_utils] tencent full batch error: {e}")
    return result


# ── ATR 估算（迁自 intraday_tracker）──────────────────────────────────────

def estimate_atr(code: str, current_price: float) -> Optional[float]:
    """用 kline 近 6 根算 ATR（True Range 均值）。不足 2 根退化为 price*2%。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        klines = list(
            db["kline"].find({"code": code.upper()}, {"high": 1, "low": 1, "close": 1, "_id": 0})
            .sort("date", -1)
            .limit(6)
        )
        if len(klines) < 2:
            return current_price * 0.02
        ranges = []
        prev_close = None
        for k in reversed(klines):
            high = float(k.get("high", 0) or 0)
            low = float(k.get("low", 0) or 0)
            close = float(k.get("close", 0) or 0)
            if prev_close is not None:
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                ranges.append(tr)
            prev_close = close
        if ranges:
            return sum(ranges) / len(ranges)
        return current_price * 0.02
    except Exception:
        return current_price * 0.02


_estimate_atr = estimate_atr  # 向后兼容


# ── 全市场板块强度（bug8 修复）────────────────────────────────────────────

def compute_sector_strength(
    snapshots: List[Dict],
    industry_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """计算全市场各板块强度（非仅 TOP30）。

    每个板块统计：股票数、平均跳空、涨停家数、总金额、强度分。
    返回按强度分降序的列表，供板块龙头识别使用。
    """
    sector_agg: Dict[str, Dict[str, Any]] = {}
    for snap in snapshots:
        code = snap.get("code", "")
        industry = industry_map.get(code, "")
        if not industry:
            continue
        gap = snap.get("gap_pct", 0.0) or 0.0
        amount = snap.get("amount", 0.0) or 0.0
        agg = sector_agg.setdefault(industry, {
            "sector": industry, "count": 0, "gap_sum": 0.0,
            "limit_up_count": 0, "amount_sum": 0.0,
        })
        agg["count"] += 1
        agg["gap_sum"] += gap
        agg["amount_sum"] += amount
        # 涨停近似：跳空 >= 9.8%（主板）/19.5%（创科）/29.5%（北交）
        bare = strip_prefix_from_code(code).upper()
        threshold = 9.8
        if bare.startswith(("30", "68")):
            threshold = 19.5
        elif bare.startswith(("8", "4")):
            threshold = 29.5
        if gap >= threshold:
            agg["limit_up_count"] += 1

    result = []
    for ind, agg in sector_agg.items():
        avg_gap = agg["gap_sum"] / agg["count"] if agg["count"] > 0 else 0
        # 板块强度分：平均跳空(40%) + 涨停家数密度(40%) + 金额分位(20%)
        gap_score = min(100, max(0, avg_gap * 20))  # 5%跳空→100
        density_score = min(100, agg["limit_up_count"] * 20)  # 5家涨停→100
        amount_score = min(100, agg["amount_sum"] / 1e8 * 10)  # 10亿→100
        strength = gap_score * 0.4 + density_score * 0.4 + amount_score * 0.2
        result.append({
            "sector": ind, "count": agg["count"],
            "avg_gap_pct": round(avg_gap, 2),
            "limit_up_count": agg["limit_up_count"],
            "total_amount": round(agg["amount_sum"], 0),
            "strength": round(strength, 1),
        })
    result.sort(key=lambda x: x["strength"], reverse=True)
    return result
