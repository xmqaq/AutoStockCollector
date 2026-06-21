"""实时行情 & K线数据获取 — L1(MongoDB缓存) + L3(akshare) 两级架构。"""
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.database import DatabaseConfig
from utils.logger import get_logger

from .config import PAConfig

logger = get_logger(__name__)

_CACHE_LOCK = threading.Lock()


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


def _get_cached(code: str, dtype: str, timeframe: str, ttl: int) -> Optional[Dict]:
    key = _cache_key(code, dtype, timeframe)
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


def get_spot(symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
    """获取实时行情。返回 {code: {price, change, high, low, ...}}。

    优先 L1 缓存（60s），L3 akshare stock_zh_a_spot_em 全量拉取。
    """
    result = {}

    if symbols:
        remaining = []
        for s in symbols:
            cached = _get_cached(s, "spot", "", PAConfig.CACHE_TTL_SPOT)
            if cached:
                result[_normalize_code(s)] = cached
            else:
                remaining.append(s)
        if not remaining:
            return result
        symbols_to_fetch = remaining
    else:
        symbols_to_fetch = None

    raw = _fetch_spot_from_akshare()
    if not raw:
        return result

    now = datetime.now()
    for code, data in raw.items():
        _save_to_cache(code, "spot", "", data)

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
        result = raw

    return result


def _fetch_spot_from_akshare() -> Optional[Dict[str, Dict]]:
    """调用 akshare 全量实时行情。"""
    try:
        import akshare as ak
    except ImportError:
        logger.warning("[PAFetcher] akshare not installed")
        return None

    for attempt in range(PAConfig.FETCH_RETRY_MAX + 1):
        try:
            if attempt > 0:
                time.sleep(3 * (attempt + 1))
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                logger.warning("[PAFetcher] spot_em returned empty")
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

            logger.info(f"[PAFetcher] spot_em fetched {len(result)} stocks")
            return result
        except Exception as e:
            logger.warning(f"[PAFetcher] spot_em attempt {attempt+1} failed: {e}")
    return None


def get_kline(code: str, timeframe: str = "daily", count: int = 120) -> Optional[List[Dict]]:
    """获取个股 K 线数据。

    timeframe: 'daily' | 'weekly' | 'monthly' | '30m' | '5m'
    返回 List[{date, open, high, low, close, volume}]
    """
    if timeframe in ("daily", "weekly", "monthly"):
        ttl = PAConfig.CACHE_TTL_KLINE_DAY
    else:
        ttl = PAConfig.CACHE_TTL_KLINE_MIN

    cached = _get_cached(code, "kline", timeframe, ttl)
    if cached:
        return cached

    bars = _fetch_kline_from_akshare(code, timeframe, count)
    if bars:
        _save_to_cache(code, "kline", timeframe, bars)
    return bars


def _fetch_kline_from_akshare(code: str, timeframe: str, count: int) -> Optional[List[Dict]]:
    """调用 akshare 获取 K 线。

   优先使用 Sina API (stock_zh_a_daily) 因其稳定性高于 Eastmoney API。
    """
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        logger.warning("[PAFetcher] akshare/pandas not installed")
        return None

    symbol = _strip_prefix(code)
    norm = _normalize_code(code).lower()

    end = datetime.now()
    start = end - timedelta(days=count * 3)

    for attempt in range(min(PAConfig.FETCH_RETRY_MAX + 1, 2)):
        try:
            if attempt > 0:
                time.sleep(3)

            if timeframe in ("5m", "15m", "30m", "60m"):
                df = ak.stock_zh_a_hist_min_em(
                    symbol=symbol,
                    period=timeframe,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
            elif timeframe in ("weekly", "monthly"):
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=timeframe,
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
            else:
                df = ak.stock_zh_a_daily(
                    symbol=norm,
                    adjust="qfq",
                )

            if df is None or df.empty:
                logger.warning(f"[PAFetcher] kline empty for {code} {timeframe}")
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
            logger.info(f"[PAFetcher] kline {code} {timeframe} bars={len(bars)}")
            return bars
        except Exception as e:
            logger.warning(f"[PAFetcher] kline {code} attempt {attempt+1} failed: {e}")

    return None
