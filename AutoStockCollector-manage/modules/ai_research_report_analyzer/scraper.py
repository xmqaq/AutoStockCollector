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
    """写入 MongoDB 缓存（去重，批量 upsert）。"""
    if not reports:
        return
    try:
        from pymongo import UpdateOne
        db = DatabaseConfig.get_database()
        coll = db[ResearchConfig.CACHE_COLLECTION]
        now = datetime.now()
        ops = []
        for r in reports:
            rid = _make_report_id(r)
            ops.append(UpdateOne(
                {"sector": sector, "report_id": rid},
                {"$set": {
                    "sector": sector,
                    "report_id": rid,
                    "data": r,
                    "cached_at": now,
                }},
                upsert=True,
            ))
        result = coll.bulk_write(ops, ordered=False)
        inserted = result.upserted_count
        logger.info(
            f"[ResearchAnalyzer] Cache saved sector={sector} "
            f"total={len(reports)} new={inserted}"
        )
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] Cache save error: {e}")


def _fetch_from_research_reports(sector: str, days: int) -> List[Dict]:
    """L2: 从 research_reports 集合（全量采集）按代表股拉取研报。
    
    数据来自 research_report_collector 模块的全量采集，包含 info_code 和 generated_abstract。
    优先于 L3 akshare，在后端已采集的情况下可完全替代 akshare。
    """
    sector_stocks = _load_sector_stocks()
    stock_codes = sector_stocks.get(sector, [])[:5]

    if not stock_codes:
        return []

    try:
        from core.storage.mongo_storage import ResearchReportStorage
    except ImportError:
        return []

    from datetime import datetime as dt
    cutoff = dt.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    all_reports = []
    seen_ids = set()
    storage = ResearchReportStorage()

    # 代表股信息（用于补 name/link 字段）
    stock_map = {s.get("code", ""): s for s in stock_codes if s.get("code")}
    batch_codes = list(stock_map.keys())

    # 一次查询所有代表股的研报（Mongo 端 code $in + date $gte 过滤），省去逐股 5 次往返
    try:
        reports = storage.find_many(
            {"code": {"$in": batch_codes}, "date": {"$gte": cutoff_str}},
            sort=[("date", -1)],
            limit=500,
        )
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] L2 batch fetch error: {e}")
        return []

    for r in reports:
        code = r.get("code", "")
        stock = stock_map.get(code, {})
        name = stock.get("name", "")
        link = stock.get("link", "")
        date_str = str(r.get("date", ""))[:10]
        if date_str < cutoff_str:
            continue

        rid = r.get("report_id", "") or _make_report_id(r)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        report = {
            "code": r.get("code", code),
            "name": r.get("name", name),
            "stock_name": name,
            "link_name": link,
            "title": r.get("title", ""),
            "date": date_str,
            "org": r.get("org", ""),
            "industry": r.get("industry", ""),
            "rating": r.get("rating", ""),
            "target_price_high": r.get("target_price_high"),
            "target_price_low": r.get("target_price_low"),
            "abstract": r.get("abstract", ""),
            "generated_abstract": r.get("generated_abstract", ""),
            "author": r.get("author", ""),
        }
        all_reports.append(report)

    logger.info(
        f"[ResearchAnalyzer] L2 research_reports sector={sector} "
        f"stocks={len(stock_codes)} reports={len(all_reports)}"
    )
    return all_reports


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
                target_high = str(row_dict.get("目标价上限", row_dict.get("target_high", "")))
                target_low = str(row_dict.get("目标价下限", row_dict.get("target_low", "")))

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

                tp_high_val = None
                tp_low_val = None
                try:
                    tp_high_val = float(target_high) if target_high else None
                except ValueError:
                    pass
                try:
                    tp_low_val = float(target_low) if target_low else None
                except ValueError:
                    pass

                report = {
                    "code": stock_code,
                    "name": stock_name,
                    "title": title,
                    "date": date_str,
                    "org": org_name,
                    "abstract": title,
                    "stock_name": name,
                    "link_name": link,
                    "industry": industry,
                    "rating": rating,
                    "target_price_high": tp_high_val,
                    "target_price_low": tp_low_val,
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

        # _throttle("akshare") 已在 fetch_engine.py 中处理了请求间隔
        # 此处无需额外 sleep

    logger.info(
        f"[ResearchAnalyzer] L3 akshare sector={sector} "
        f"reports={len(all_reports)}"
    )
    return all_reports


def get_reports(
    sector: str, days: int = 90, min_count: int = 15,
) -> Tuple[List[Dict], str]:
    """获取指定板块的研报。按 L1 → L2 → L3 链尝试。

    - L1: MongoDB reports_cache（旧缓存）
    - L2: research_reports 集合（全量采集，含 AI 摘要）
    - L3: akshare stock_research_report_em（兜底）

    Returns:
        (reports_list, source_label)
    """
    # L1: cache hit 且达标直接返回
    cached, source = _get_cached(sector, min_count)
    if cached:
        return cached, source

    # L2: 从 research_reports 获取
    l2_reports = _fetch_from_research_reports(sector, days)
    if len(l2_reports) >= min_count:
        _save_to_cache(sector, l2_reports)
        return l2_reports, "L2_RESEARCH_REPORTS"

    # L2 达标但数据不够？用 L3 补充
    l3_reports = _fetch_from_akshare_by_stocks(sector, days)
    combined = l2_reports + l3_reports
    if combined:
        _save_to_cache(sector, combined)
        source = "L2_L3" if l2_reports else "L3_AKSHARE"
        return combined, source

    return [], "NONE"
