"""研报采集编排 — L1(L3)多级缓存架构。

数据流：
1. L1 Cache: MongoDB reports_cache → 命中且数量达标直接返回
2. L3 API: akshare stock_research_report_em 按代表股批量拉取
"""
import hashlib
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.database import DatabaseConfig
from utils.logger import get_logger

from .config import ResearchConfig
from .fetch_engine import get_fetcher

logger = get_logger(__name__)

_CACHE_LOCK = threading.Lock()


def _load_sector_stocks() -> Dict[str, List[Dict]]:
    """从 chain_templates.json 加载各板块的代表股列表。"""
    import json
    from pathlib import Path
    path = Path(__file__).parent / "chain_templates.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text("utf-8"))
        result = {}
        for sector, info in data.items():
            stocks = info.get("representative_stocks", [])
            if stocks:
                result[sector] = stocks
        return result
    except Exception as e:
        logger.warning(f"Failed to load chain_templates.json: {e}")
        return {}


def _make_report_id(report: Dict) -> str:
    code = report.get("code", "")
    date = str(report.get("date", ""))
    title = report.get("title", "")
    org = report.get("org", "")
    raw = f"{code}|{date}|{title}|{org}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _get_cached(sector: str, min_count: int) -> Tuple[Optional[List[Dict]], str]:
    """L1: 查 MongoDB 缓存。"""
    try:
        db = DatabaseConfig.get_database()
        cutoff = datetime.now() - timedelta(days=ResearchConfig.CACHE_TTL_DAYS)
        coll = db[ResearchConfig.CACHE_COLLECTION]
        docs = list(
            coll.find({
                "sector": sector,
                "cached_at": {"$gte": cutoff},
            }).sort("cached_at", -1).limit(min_count * 2)
        )
        if len(docs) >= min_count:
            reports = []
            seen_ids = set()
            for d in docs:
                rid = d.get("report_id", "")
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    r = d.get("data", {})
                    if r:
                        reports.append(r)
            if len(reports) >= min_count:
                logger.info(
                    f"[ResearchAnalyzer] L1 Cache HIT sector={sector} "
                    f"reports={len(reports)}"
                )
                return reports[:min_count * 2], "L1_CACHE"
        return None, "L1_MISS"
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] L1 cache error: {e}")
        return None, "L1_ERROR"


def _save_to_cache(sector: str, reports: List[Dict]):
    """写入 MongoDB 缓存（去重）。"""
    try:
        db = DatabaseConfig.get_database()
        coll = db[ResearchConfig.CACHE_COLLECTION]
        now = datetime.now()
        inserted = 0
        for r in reports:
            rid = _make_report_id(r)
            result = coll.update_one(
                {"sector": sector, "report_id": rid},
                {"$set": {
                    "sector": sector,
                    "report_id": rid,
                    "data": r,
                    "cached_at": now,
                }},
                upsert=True,
            )
            if result.upserted_id:
                inserted += 1
        logger.info(
            f"[ResearchAnalyzer] Cache saved sector={sector} "
            f"total={len(reports)} new={inserted}"
        )
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] Cache save error: {e}")


def _fetch_from_akshare_by_stocks(sector: str, days: int) -> List[Dict]:
    """L3: 通过 akshare stock_research_report_em 按代表股批量拉取研报。"""
    sector_stocks = _load_sector_stocks()
    stock_codes = sector_stocks.get(sector, [])[:5]  # 最多用 5 只代表股

    if not stock_codes:
        logger.warning(
            f"[ResearchAnalyzer] No representative stocks for sector={sector}"
        )
        return []

    try:
        import akshare as ak
    except ImportError:
        logger.warning("[ResearchAnalyzer] akshare not installed")
        return []

    all_reports = []
    seen_titles = set()
    fetcher = get_fetcher()
    cutoff_date = datetime.now() - timedelta(days=days)

    for stock in stock_codes:
        code = stock.get("code", "")
        name = stock.get("name", "")
        link = stock.get("link", "")
        if not code:
            continue

        # 限速
        fetcher._throttle("akshare")

        try:
            df = ak.stock_research_report_em(symbol=code)
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                row_dict = row.to_dict()
                title = str(row_dict.get("报告名称", row_dict.get("title", row_dict.get("REPORT_TITLE", ""))))
                date_str = str(row_dict.get("日期", row_dict.get("date", row_dict.get("NOTICE_DATE", ""))))
                org_name = str(row_dict.get("机构", row_dict.get("org", row_dict.get("ORG_NAME", ""))))
                stock_code = str(row_dict.get("股票代码", row_dict.get("code", row_dict.get("SECURITY_CODE", ""))))
                stock_name = str(row_dict.get("股票简称", row_dict.get("name", row_dict.get("SECURITY_NAME_ABBR", ""))))
                industry = str(row_dict.get("行业", row_dict.get("industry", "")))
                rating = str(row_dict.get("东财评级", row_dict.get("rating", "")))

                # 按日期过滤
                try:
                    report_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    if report_date < cutoff_date:
                        continue
                except (ValueError, IndexError):
                    pass

                # 去重
                title_key = f"{code}|{title}"
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                report = {
                    "code": stock_code,
                    "name": stock_name,
                    "title": title,
                    "date": date_str,
                    "org": org_name,
                    "abstract": title,  # 实际只取到标题，无全文内容
                    "stock_name": name,
                    "link_name": link,
                    "industry": industry,
                    "rating": rating,
                }
                all_reports.append(report)

            logger.info(
                f"[ResearchAnalyzer] Fetched {len(df)} reports for "
                f"{name}({code})"
            )
        except Exception as e:
            logger.warning(
                f"[ResearchAnalyzer] akshare error for {name}({code}): {e}"
            )
            continue

        time.sleep(1.0)

    logger.info(
        f"[ResearchAnalyzer] L3 akshare sector={sector} "
        f"reports={len(all_reports)}"
    )
    return all_reports


def get_reports(
    sector: str, days: int = 90, min_count: int = 15,
) -> Tuple[List[Dict], str]:
    """获取指定板块的研报。按 L1 → L3 链尝试。

    Returns:
        (reports_list, source_label)
    """
    cached, source = _get_cached(sector, min_count)
    if cached:
        return cached, source

    l3_reports = _fetch_from_akshare_by_stocks(sector, days)

    if l3_reports:
        _save_to_cache(sector, l3_reports)
        return l3_reports, "L3_AKSHARE"

    return [], "NONE"
