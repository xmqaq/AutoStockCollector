import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.storage.mongo_storage import ResearchReportStorage
from utils.logger import get_logger
from utils.helpers import chunk_list

logger = get_logger(__name__)

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/report/stock.jshtml",
}


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
        r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=30)
        r.raise_for_status()
        data_json = r.json()
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
            r = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=30)
            r.raise_for_status()
            more = r.json().get("data", [])
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

    def collect_all(self, batch_size: int = 100, delay: float = 2.0) -> Dict[str, Any]:
        codes = _get_all_stock_codes()
        if not codes:
            return {"success": False, "error": "No stock codes fetched", "total": 0}

        total_fetched = 0
        total_new = 0
        total_errors = 0
        batches = chunk_list(codes, batch_size)

        logger.info(
            f"[ResearchCollector] Starting collection for {len(codes)} stocks "
            f"in {len(batches)} batches"
        )

        for batch_idx, batch in enumerate(batches):
            batch_reports = []
            for code in batch:
                try:
                    reports = self.collect_for_stock(code)
                    batch_reports.extend(reports)
                    total_fetched += len(reports)
                    if reports:
                        logger.info(
                            f"[ResearchCollector] {code}: {len(reports)} reports"
                        )
                except Exception as e:
                    logger.warning(
                        f"[ResearchCollector] Error for {code}: {e}"
                    )
                    total_errors += 1

                time.sleep(delay)

            if batch_reports:
                saved, failed = self.storage.save_batch(batch_reports)
                total_new += saved
                logger.info(
                    f"[ResearchCollector] Batch {batch_idx + 1}/{len(batches)}: "
                    f"{len(batch_reports)} reports, {saved} saved"
                )

        return {
            "success": True,
            "total_codes": len(codes),
            "total_fetched": total_fetched,
            "total_saved": total_new,
            "errors": total_errors,
        }


def collect_all_reports() -> Dict[str, Any]:
    collector = ResearchReportCollector()
    result = collector.collect_all()
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
