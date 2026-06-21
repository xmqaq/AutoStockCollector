"""研报采集编排 — L1(L3)多级缓存架构。

数据流：
1. L1 Cache: MongoDB reports_cache → 命中且数量达标直接返回
2. L3 API: akshare stock_research_report_em 按代表股批量拉取
"""
import json
import re
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

# 东方财富数据中心 - 研究报告接口
_EASTMONEY_REPORT_URL = "https://reportapi.eastmoney.com/report/list"


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
    import hashlib
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
                    "abstract": title,
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


def _matches_sector_keyword(report: Dict, sector: str) -> bool:
    """检查研报标题/摘要是否匹配板块关键词。"""
    title = report.get("title", "")
    abstract = report.get("abstract", "")
    text = f"{title} {abstract}"
    keywords = [sector]
    if sector == "人形机器人":
        keywords.extend(["人形", "机器人", "仿生", "具身智能"])
    elif sector == "储能":
        keywords.extend(["储能", "电池", "逆变器", "BMS", "EMS", "电芯"])
    elif sector == "半导体":
        keywords.extend(["半导体", "芯片", "晶圆", "封测", "EDA", "光刻", "刻蚀"])
    elif sector == "新能源汽车":
        keywords.extend(["新能源汽车", "电动车", "锂电池", "电控", "自动驾驶", "智能座舱"])
    elif sector == "AI算力":
        keywords.extend(["AI算力", "GPU", "光模块", "液冷", "服务器", "算力"])
    elif sector == "创新药":
        keywords.extend(["创新药", "临床", "CRO", "CDMO", "抗体", "ADC", "靶点"])
    elif sector == "光伏":
        keywords.extend(["光伏", "太阳能", "组件", "逆变器", "硅片", "电池片"])
    elif sector == "军工":
        keywords.extend(["军工", "国防", "航空航天", "导弹", "雷达", "军机", "发动机"])
    elif sector == "消费电子":
        keywords.extend(["消费电子", "手机", "PC", "平板", "可穿戴", "OLED", "VR"])
    elif sector == "医疗器械":
        keywords.extend(["医疗器械", "IVD", "影像", "耗材", "手术机器人", "POCT"])
    elif sector == "白酒":
        keywords.extend(["白酒", "茅台", "五粮液", "高端酒", "次高端", "啤酒"])
    elif sector == "家电":
        keywords.extend(["家电", "空调", "冰箱", "洗衣机", "小家电", "扫地机"])
    elif sector == "房地产":
        keywords.extend(["房地产", "地产", "商品房", "物业", "REITs", "保障房"])
    elif sector == "银行":
        keywords.extend(["银行", "商业", "贷款", "存款", "净息差", "财富管理"])
    elif sector == "证券":
        keywords.extend(["证券", "券商", "投行", "经纪", "资管", "财富管理"])
    elif sector == "养殖":
        keywords.extend(["养殖", "猪周期", "生猪", "饲料", "动保", "鸡周期"])
    elif sector == "煤炭":
        keywords.extend(["煤炭", "动力煤", "焦煤", "煤化工", "焦化", "煤层气"])
    elif sector == "有色金属":
        keywords.extend(["有色金属", "铜", "铝", "黄金", "稀土", "锂", "镍"])
    elif sector == "基础化工":
        keywords.extend(["化工", "化纤", "化肥", "农药", "钛白粉", "聚氨酯", "有机硅"])
    elif sector == "电力":
        keywords.extend(["电力", "火电", "水电", "风电", "核电", "电网", "特高压"])
    return any(kw in text for kw in keywords)


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
