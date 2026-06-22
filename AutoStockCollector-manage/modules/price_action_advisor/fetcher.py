"""实时行情 & K线数据获取 — 三层缓存 + EastMoney 直连 + 进程级 LRU。"""
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from config.database import DatabaseConfig
from utils.logger import get_logger

from .config import PAConfig

logger = get_logger(__name__)

_CACHE_LOCK = threading.Lock()
_FETCH_INTERVAL = max(getattr(PAConfig, "FETCH_INTERVAL", 0.3), 0.1)

_THREAD_LOCAL = threading.local()

_SPOT_MEM_CACHE: Dict[str, Any] = {}
_SPOT_MEM_CACHE_AT = 0.0
_SPOT_MEM_TTL = 60

# 进程级 LRU K 线缓存 — 同一次扫描内避免重复拉取
_KLINE_LRU: "OrderedDict[str, Any]" = OrderedDict()
_KLINE_LRU_MAX = 500
_KLINE_LRU_LOCK = threading.Lock()

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}


def _market(code: str) -> str:
    c = code.strip()
    if c.startswith(("6", "9")) or c.startswith("SH"):
        return "1"
    if c.startswith(("0", "3")) or c.startswith("SZ"):
        return "0"
    if c.startswith(("4", "8")) or c.startswith("BJ"):
        return "0"
    return "1"


def _secid(code: str) -> str:
    raw = code[2:] if code.startswith(("SH", "SZ", "BJ")) else code
    return f"{_market(raw)}.{raw}"


def _throttle():
    """每个工作线程独立节流 — 避免全局锁串行。"""
    last = getattr(_THREAD_LOCAL, "last_fetch_at", 0.0)
    now = time.time()
    elapsed = now - last
    if last > 0 and elapsed < _FETCH_INTERVAL:
        time.sleep(_FETCH_INTERVAL - elapsed)
    _THREAD_LOCAL.last_fetch_at = time.time()


def _normalize_code(code: str) -> str:
    if len(code) >= 8:
        return code
    if code.startswith(("SH", "sh", "SZ", "sz", "BJ", "bj")):
        return code.upper()
    if code.startswith(("6", "9", "7")):
        return f"SH{code}"
    return f"SZ{code}"


def _strip_prefix(code: str) -> str:
    return code[2:] if code.startswith(("SH", "SZ", "BJ")) else code


def _cache_key(code: str, dtype: str, timeframe: str = "") -> str:
    return f"{_normalize_code(code)}|{dtype}|{timeframe}"


def _get_cached(code: str, dtype: str, timeframe: str, ttl: int) -> Optional[Any]:
    key = _cache_key(code, dtype, timeframe)
    with _CACHE_LOCK:
        try:
            db = DatabaseConfig.get_database()
            cutoff = datetime.now() - timedelta(seconds=ttl)
            doc = db[PAConfig.CACHE_COLLECTION].find_one(
                {"cache_key": key, "cached_at": {"$gte": cutoff}},
            )
            if doc:
                return doc.get("data")
        except Exception as e:
            logger.warning(f"[PAFetcher] cache read error: {e}")
    return None


def _save_to_cache(code: str, dtype: str, timeframe: str, data: Any):
    key = _cache_key(code, dtype, timeframe)
    with _CACHE_LOCK:
        try:
            db = DatabaseConfig.get_database()
            db[PAConfig.CACHE_COLLECTION].update_one(
                {"cache_key": key},
                {"$set": {
                    "cache_key": key,
                    "code": _normalize_code(code),
                    "dtype": dtype,
                    "timeframe": timeframe,
                    "data": data,
                    "cached_at": datetime.now(),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[PAFetcher] cache save error: {e}")


def _kline_lru_get(key: str) -> Optional[Any]:
    with _KLINE_LRU_LOCK:
        if key in _KLINE_LRU:
            _KLINE_LRU.move_to_end(key)
            return _KLINE_LRU[key]
    return None


def _kline_lru_set(key: str, data: Any):
    with _KLINE_LRU_LOCK:
        if key in _KLINE_LRU:
            _KLINE_LRU.move_to_end(key)
        else:
            if len(_KLINE_LRU) >= _KLINE_LRU_MAX:
                _KLINE_LRU.popitem(last=False)
        _KLINE_LRU[key] = data


def clear_kline_lru():
    with _KLINE_LRU_LOCK:
        _KLINE_LRU.clear()


def get_spot(symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
    """获取实时行情。返回 {code: {price, change, high, low, ...}}。

    三级缓存: L0(内存 60s) → L1(MongoDB 60s) → L3(akshare 全量拉取)。
    """
    result = {}

    global _SPOT_MEM_CACHE, _SPOT_MEM_CACHE_AT
    mem_valid = _SPOT_MEM_CACHE and time.time() - _SPOT_MEM_CACHE_AT < _SPOT_MEM_TTL
    full_cache_hit = False
    if symbols and mem_valid:
        remaining = []
        for s in symbols:
            n = _normalize_code(s)
            entry = _SPOT_MEM_CACHE.get(n) or _SPOT_MEM_CACHE.get(s)
            if entry:
                result[n] = entry
            else:
                remaining.append(s)
        if not remaining:
            return result
        symbols_to_fetch = remaining
    elif mem_valid:
        result = dict(_SPOT_MEM_CACHE)
        return result
    else:
        symbols_to_fetch = symbols

    if symbols_to_fetch:
        remaining = []
        for s in symbols_to_fetch:
            cached = _get_cached(s, "spot", "", PAConfig.CACHE_TTL_SPOT)
            if cached:
                n = _normalize_code(s)
                result[n] = cached
            else:
                remaining.append(s)
        if not remaining:
            return result
        symbols_to_fetch = remaining
    else:
        symbols_to_fetch = None

    raw = _fetch_spot_from_eastmoney()
    if not raw:
        raw = _fetch_spot_from_akshare()
    if not raw:
        return result

    _SPOT_MEM_CACHE = {}
    for code, data in raw.items():
        n = _normalize_code(code)
        _SPOT_MEM_CACHE[n] = data
        _save_to_cache(code, "spot", "", data)
    _SPOT_MEM_CACHE_AT = time.time()

    if symbols_to_fetch:
        for s in symbols_to_fetch:
            n = _normalize_code(s)
            if n in raw:
                result[n] = raw[n]
            elif s in raw:
                result[n] = raw[s]
            else:
                for rk, rv in raw.items():
                    if rk == s or _normalize_code(rk) == n:
                        result[n] = rv
                        break
    else:
        result = dict(_SPOT_MEM_CACHE)

    return result


def _fetch_spot_from_eastmoney() -> Optional[Dict[str, Dict]]:
    """EastMoney 全量实时行情 — 替代 akshare stock_zh_a_spot_em。"""
    try:
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
        _throttle()
        r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", {}).get("diff", [])
        if not items:
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
                "amplitude": item.get("f7") or 0.0,
                "high": item.get("f15") or 0.0,
                "low": item.get("f16") or 0.0,
                "open": item.get("f17") or 0.0,
                "pre_close": item.get("f18") or 0.0,
                "volume_ratio": item.get("f10") or 0.0,
                "turnover": item.get("f8") or 0.0,
            }
        logger.info(f"[PAFetcher] eastmoney spot fetched {len(result)} stocks")
        return result
    except Exception as e:
        logger.warning(f"[PAFetcher] eastmoney spot error: {e}")
        return None


def _fetch_spot_from_akshare() -> Optional[Dict[str, Dict]]:
    """回退: akshare 全量实时行情。"""
    try:
        import akshare as ak
    except ImportError:
        return None

    for attempt in range(PAConfig.FETCH_RETRY_MAX + 1):
        try:
            if attempt > 0:
                time.sleep(3 * (attempt + 1))
            _throttle()
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return None

            col_map = {
                "代码": "code", "名称": "name",
                "最新价": "price", "涨跌幅": "change_pct",
                "涨跌额": "change", "成交量": "volume",
                "成交额": "amount", "振幅": "amplitude",
                "最高": "high", "最低": "low",
                "今开": "open", "昨收": "pre_close",
                "量比": "volume_ratio", "换手率": "turnover",
                "市盈率-动态": "pe", "市净率": "pb",
            }

            result = {}
            cols = list(df.columns)
            for _, row in df.iterrows():
                entry = {}
                for cn, en in col_map.items():
                    if cn in cols:
                        v = row.get(cn)
                        try:
                            entry[en] = float(v) if v is not None else 0.0
                        except (ValueError, TypeError):
                            entry[en] = 0.0
                raw_code = str(row.get("代码", ""))
                if raw_code:
                    result[raw_code] = entry

            logger.info(f"[PAFetcher] akshare spot fetched {len(result)} stocks")
            return result
        except Exception as e:
            logger.warning(f"[PAFetcher] akshare spot attempt {attempt+1} failed: {e}")
    return None


def _is_trading_time() -> bool:
    try:
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        h, m = now.hour, now.minute
        t = h * 100 + m
        return 915 <= t <= 1500
    except Exception:
        return False


def get_kline(code: str, timeframe: str = "daily", count: int = 120) -> Optional[List[Dict]]:
    """获取个股 K 线数据。

    timeframe: 'daily' | 'weekly' | 'monthly' | '30m' | '5m' | '15m' | '60m'
    返回 List[{date, open, high, low, close, volume}]

   缓存层次: LRU(进程) → MongoDB → EastMoney API → akshare(回退)
    """
    if timeframe in ("daily", "weekly", "monthly"):
        ttl = PAConfig.CACHE_TTL_KLINE_DAY
    else:
        ttl = 60 if _is_trading_time() else PAConfig.CACHE_TTL_KLINE_MIN

    # L0: 进程级 LRU（同一次扫描内共享）
    lru_key = _cache_key(code, "kline", timeframe)
    lru_hit = _kline_lru_get(lru_key)
    if lru_hit is not None:
        return lru_hit

    # L1: MongoDB
    cached = _get_cached(code, "kline", timeframe, ttl)
    if cached:
        _kline_lru_set(lru_key, cached)
        return cached

    # L2: EastMoney 直连
    bars = _fetch_kline_from_eastmoney(code, timeframe, count)
    if bars:
        _save_to_cache(code, "kline", timeframe, bars)
        _kline_lru_set(lru_key, bars)
        return bars

    # L3: akshare 回退
    bars = _fetch_kline_from_akshare(code, timeframe, count)
    if bars:
        _save_to_cache(code, "kline", timeframe, bars)
        _kline_lru_set(lru_key, bars)
    return bars


_KLTMAP = {
    "daily": "101", "weekly": "102", "monthly": "103",
    "5m": "5", "15m": "15", "30m": "30", "60m": "60",
}


def _fetch_kline_from_eastmoney(code: str, timeframe: str, count: int) -> Optional[List[Dict]]:
    """EastMoney 直连 K 线 API — 替代 akshare。"""
    klt = _KLTMAP.get(timeframe)
    if not klt:
        return None

    raw_code = _strip_prefix(code)
    sid = _secid(raw_code)
    end = "20500101"

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": sid,
        "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": klt,
        "fqt": "1",
        "end": end,
        "lmt": str(count),
    }

    for attempt in range(2):
        try:
            if attempt > 0:
                time.sleep(1)
            _throttle()
            r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
            klines = data.get("data", {}).get("klines", [])
            if not klines:
                return None

            bars = []
            for line in klines:
                parts = line.split(",")
                if len(parts) < 6:
                    continue
                try:
                    bar = {
                        "date": parts[0],
                        "open": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "close": float(parts[4]),
                        "volume": float(parts[5]),
                    }
                    bars.append(bar)
                except (ValueError, IndexError):
                    continue

            bars.sort(key=lambda x: x["date"])
            bars = bars[-count:]
            logger.info(f"[PAFetcher] eastmoney kline {code} {timeframe} bars={len(bars)}")
            return bars
        except Exception as e:
            logger.warning(f"[PAFetcher] eastmoney kline {code} attempt {attempt+1}: {e}")

    return None


def _fetch_kline_from_akshare(code: str, timeframe: str, count: int) -> Optional[List[Dict]]:
    """回退: akshare K 线。"""
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        return None

    symbol = _strip_prefix(code)
    norm = _normalize_code(code).lower()
    end = datetime.now()
    start = end - timedelta(days=count * 3)

    for attempt in range(min(PAConfig.FETCH_RETRY_MAX + 1, 2)):
        try:
            if attempt > 0:
                time.sleep(3)
            _throttle()

            if timeframe in ("5m", "15m", "30m", "60m"):
                df = ak.stock_zh_a_hist_min_em(
                    symbol=symbol, period=timeframe,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"), adjust="qfq",
                )
            elif timeframe in ("weekly", "monthly"):
                df = ak.stock_zh_a_hist(
                    symbol=symbol, period=timeframe,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"), adjust="qfq",
                )
            else:
                df = ak.stock_zh_a_daily(symbol=norm, adjust="qfq")

            if df is None or df.empty:
                return None

            bars = []
            col_is_min = timeframe in ("5m", "15m", "30m", "60m")

            for _, row in df.iterrows():
                try:
                    if col_is_min:
                        bar = {
                            "date": str(row.get("时间", "")),
                            "open": float(row.get("开盘", 0)),
                            "high": float(row.get("最高", 0)),
                            "low": float(row.get("最低", 0)),
                            "close": float(row.get("收盘", 0)),
                            "volume": float(row.get("成交量", 0)),
                        }
                    else:
                        date_val = row.get("date", "")
                        if hasattr(date_val, "strftime"):
                            date_str = date_val.strftime("%Y-%m-%d")
                        else:
                            date_str = str(date_val)[:10]
                        bar = {
                            "date": date_str,
                            "open": float(row.get("open", 0)),
                            "high": float(row.get("high", 0)),
                            "low": float(row.get("low", 0)),
                            "close": float(row.get("close", 0)),
                            "volume": float(row.get("volume", 0)),
                        }
                    bars.append(bar)
                except (ValueError, TypeError):
                    continue

            bars.sort(key=lambda x: x["date"])
            bars = bars[-count:]
            logger.info(f"[PAFetcher] akshare kline {code} {timeframe} bars={len(bars)}")
            return bars
        except Exception as e:
            logger.warning(f"[PAFetcher] akshare kline {code} attempt {attempt+1}: {e}")

    return None
