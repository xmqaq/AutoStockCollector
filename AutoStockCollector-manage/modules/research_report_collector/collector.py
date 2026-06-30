import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.storage.mongo_storage import ResearchReportStorage
from utils.logger import get_logger
from utils.helpers import chunk_list, beijing_now

logger = get_logger(__name__)

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/report/stock.jshtml",
}

_META_COLLECTION = "research_reports_meta"
_META_KEY = "last_collect"

_DEFAULT_WORKERS = 8
_DEFAULT_DELAY = 0.4

# 全局限流：reportapi.eastmoney.com 对高频请求会 429/封 IP，
# 用 Semaphore 控并发 + 最小请求间隔保证 8 线程下整体 QPS 受控。
_RATE_MAX_CONCURRENT = 4
_RATE_MIN_INTERVAL = 0.5  # 两次请求间至少间隔 0.5s（全局，跨线程）
_RATE_RETRY_MAX = 3
_rate_sem = threading.Semaphore(_RATE_MAX_CONCURRENT)
_rate_lock = threading.Lock()
_rate_last_request = 0.0


def _rate_throttle() -> None:
    """全局节流：保证任意两次 HTTP 请求间隔不小于 _RATE_MIN_INTERVAL。"""
    global _rate_last_request
    with _rate_lock:
        now = time.time()
        elapsed = now - _rate_last_request
        if elapsed < _RATE_MIN_INTERVAL:
            time.sleep(_RATE_MIN_INTERVAL - elapsed)
        _rate_last_request = time.time()


def _rate_backoff(attempt: int) -> float:
    return min(2 ** attempt * 2, 30)


def _rate_get(url: str, params: Dict, timeout: int = 30) -> Optional[Dict]:
    """带限流 + 429 退避的 GET，返回解析后的 JSON dict 或 None。"""
    with _rate_sem:
        _rate_throttle()
        for attempt in range(1, _RATE_RETRY_MAX + 2):
            try:
                r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=timeout)
                if r.status_code == 429:
                    delay = _rate_backoff(attempt)
                    logger.warning(f"[ResearchCollector] 429 from eastmoney, retry in {delay:.0f}s")
                    time.sleep(delay)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.ConnectionError as e:
                if attempt > _RATE_RETRY_MAX:
                    logger.warning(f"[ResearchCollector] connection error (giving up): {e}")
                    return None
                time.sleep(_rate_backoff(attempt))
            except requests.Timeout as e:
                if attempt > _RATE_RETRY_MAX:
                    logger.warning(f"[ResearchCollector] timeout (giving up): {e}")
                    return None
                time.sleep(_rate_backoff(attempt))
            except Exception as e:
                logger.warning(f"[ResearchCollector] request error: {e}")
                return None
    return None


def _make_report_id(report: Dict) -> str:
    code = report.get("code", "")
    date = str(report.get("date", ""))
    title = report.get("title", "")
    org = report.get("org", "")
    raw = f"{code}|{date}|{title}|{org}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_all_stock_codes() -> List[str]:
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return list(df["code"].tolist())
    except Exception as e:
        logger.error(f"[ResearchCollector] Failed to get stock codes: {e}")
        return []


def _get_last_collect_time() -> Optional[str]:
    from config.database import DatabaseConfig
    try:
        col = DatabaseConfig.get_database()[_META_COLLECTION]
        doc = col.find_one({"_id": _META_KEY})
        if doc:
            return doc.get("last_collect")
    except Exception:
        pass
    return None


def _set_last_collect_time() -> None:
    from config.database import DatabaseConfig
    try:
        col = DatabaseConfig.get_database()[_META_COLLECTION]
        col.update_one(
            {"_id": _META_KEY},
            {"$set": {"last_collect": beijing_now().isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[ResearchCollector] Failed to set meta: {e}")


def _fetch_eastmoney_reports(raw_code: str, days: int = 365) -> List[Dict]:
    """直接从东方财富 API 拉取个股研报。raw_code 不含 SH/SZ 前缀 (如 688012)。"""
    end_str = datetime.now().strftime("%Y-%m-%d")
    start_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    url = "https://reportapi.eastmoney.com/report/list"
    params = {
        "industryCode": "*",
        "pageSize": "500",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": start_str,
        "endTime": end_str,
        "pageNo": "1",
        "fields": "",
        "qType": "0",
        "orgCode": "",
        "code": raw_code,
        "rcode": "",
    }

    try:
        data_json = _rate_get(url, params)
        if data_json is None:
            return []
    except Exception as e:
        logger.warning(f"[ResearchCollector] API error for {raw_code}: {e}")
        return []

    records = data_json.get("data", [])
    if not records:
        return []

    total_page = data_json.get("TotalPage", 1)
    for page in range(2, total_page + 1):
        params["pageNo"] = str(page)
        try:
            more_json = _rate_get(url, params)
            if more_json is None:
                break
            more = more_json.get("data", [])
            records.extend(more)
        except Exception as e:
            logger.warning(f"[ResearchCollector] page {page} error: {e}")
            break

    reports = []
    for item in records:
        title = item.get("title", "") or ""
        date_str = str(item.get("publishDate", ""))[:10]
        org_name = item.get("orgName", "") or ""
        stock_code = item.get("stockCode", "") or ""
        stock_name = item.get("stockName", "") or ""
        rating = item.get("emRatingName", "") or ""
        target_high = item.get("indvAimPriceT", None)
        target_low = item.get("indvAimPriceL", None)
        industry = item.get("industryName", "") or ""
        author = item.get("author", "") or ""
        info_code = item.get("infoCode", "")

        tp_high = None
        tp_low = None
        try:
            tp_high = float(target_high) if target_high else None
        except (ValueError, TypeError):
            pass
        try:
            tp_low = float(target_low) if target_low else None
        except (ValueError, TypeError):
            pass

        report = {
            "code": stock_code,
            "name": stock_name,
            "title": title,
            "date": date_str,
            "org": org_name,
            "industry": industry,
            "rating": rating,
            "author": author,
            "target_price_high": tp_high,
            "target_price_low": tp_low,
            "abstract": title,
            "info_code": info_code,
            "cached_at": datetime.now(),
        }
        report["report_id"] = _make_report_id(report)
        reports.append(report)

    return reports


class ResearchReportCollector:
    def __init__(self):
        self.storage = ResearchReportStorage()
        self._session_start = datetime.now()

    def collect_for_stock(self, raw_code: str, days: int = 365) -> List[Dict[str, Any]]:
        return _fetch_eastmoney_reports(raw_code, days=days)

    def collect_all_parallel(
        self,
        workers: int = _DEFAULT_WORKERS,
        delay: float = _DEFAULT_DELAY,
        batch_size: int = 100,
        incremental_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """并行采集所有个股研报。
        
        Args:
            workers: 并发线程数
            delay: 每次请求后的延迟秒数（并发下不叠加）
            batch_size: 每批保存的股票数
            incremental_days: 如果指定，只获取最近 N 天的数据（增量模式）
                              如果为 None，检查上次采集时间
        """
        codes = _get_all_stock_codes()
        if not codes:
            return {"success": False, "error": "No stock codes fetched", "total": 0}

        if incremental_days is None:
            last = _get_last_collect_time()
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    days_since = (beijing_now() - last_dt).days + 7
                    incremental_days = max(days_since, 30)
                    logger.info(f"[ResearchCollector] Incremental mode: last={last_dt.date()}, days={incremental_days}")
                except Exception:
                    incremental_days = 365
            else:
                incremental_days = 365

        total_fetched = 0
        total_new = 0
        total_errors = 0
        all_reports_batch: List[Dict] = []

        logger.info(
            f"[ResearchCollector] Starting parallel collection for {len(codes)} stocks, "
            f"{workers} workers, {incremental_days}d window"
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(self.collect_for_stock, code, days=incremental_days): code
                for code in codes
            }

            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    reports = future.result()
                    if reports:
                        all_reports_batch.extend(reports)
                        total_fetched += len(reports)
                except Exception as e:
                    logger.warning(f"[ResearchCollector] Error for {code}: {e}")
                    total_errors += 1

                if len(all_reports_batch) >= batch_size * workers:
                    saved, _ = self.storage.save_batch(all_reports_batch)
                    total_new += saved
                    logger.info(
                        f"[ResearchCollector] Intermediate save: {len(all_reports_batch)} reports, "
                        f"{saved} saved, fetched={total_fetched}, errors={total_errors}"
                    )
                    all_reports_batch = []
                # 请求节流已由 _rate_get 内部全局限流器接管，此处不再额外 sleep

        if all_reports_batch:
            saved, _ = self.storage.save_batch(all_reports_batch)
            total_new += saved
            logger.info(f"[ResearchCollector] Final save: {len(all_reports_batch)} reports, {saved} saved")

        _set_last_collect_time()

        return {
            "success": True,
            "total_codes": len(codes),
            "total_fetched": total_fetched,
            "total_saved": total_new,
            "errors": total_errors,
        }

    def collect_all(self, batch_size: int = 100, delay: float = 2.0) -> Dict[str, Any]:
        """保留的串行采集方式，供回退使用。"""
        return self.collect_all_parallel(workers=1, delay=delay, batch_size=batch_size)


def collect_all_reports() -> Dict[str, Any]:
    collector = ResearchReportCollector()
    result = collector.collect_all_parallel()
    import threading
    def _summarize_background():
        try:
            from .summarizer import summarize_pending_reports
            logger.info("[ResearchCollector] Starting background summarization...")
            sr = summarize_pending_reports(max_reports=50, delay=12)
            logger.info(f"[ResearchCollector] Background summarization done: {sr}")
        except Exception as e:
            logger.error(f"[ResearchCollector] Background summarization error: {e}")
    t = threading.Thread(target=_summarize_background, daemon=True)
    t.start()
    return result
