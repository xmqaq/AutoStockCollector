"""
全市场热点新闻发现 — 独立于个股监控名单。
反向匹配：拿全市场新闻标题去撞股票名称库 / 概念名称库，聚合出近 N 小时
被多次报道的个股与板块，并与资金流向、AI 智选结果交叉验证。
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from config.database import DatabaseConfig
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class NewsHotspotDetector:
    # 板块名是短词，易被同形的非板块语境误命中——板块匹配前先把这些噪声短语
    # 从标题剥掉。实测最大来源是"证券事务代表(董秘)辞职""证券虚假陈述/索赔(诉讼)"
    # 这类治理/法律用语里的"证券"，以及"证券时报"等媒体来源名。
    _SECTOR_STOPPHRASES = [
        "证券事务代表", "证券事务", "证券虚假陈述", "证券索赔", "证券监管",
        "中国证券报", "上海证券报", "证券时报", "证券日报",
        "第一财经", "财联社", "每日经济新闻", "中国基金报", "经济参考报",
    ]

    def __init__(self):
        self._db = DatabaseConfig.get_database()

    def detect(self, hours: int = 24, top_n: int = 20) -> Dict[str, Any]:
        now = datetime.now()
        # publish_date 存为 "YYYY-MM-DD HH:MM:SS" 字符串，字符串字典序与时间序一致，
        # 直接用 $gte 字符串比较即可（ponytail: 依赖 ISO 格式，足够，无需转 datetime）。
        since = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        news = list(self._db["news"].find(
            {"news_type": "general", "publish_date": {"$gte": since}},
            {"title": 1, "publish_date": 1},
        ))
        if not news:
            return self._empty(now, hours)

        name_map = self._build_name_library()
        sector_names = self._sector_names()

        # 反向匹配：每条标题撞名称库 / 概念库。
        # ponytail: 朴素 O(新闻数 × 名称数) 扫描；当前规模(几百条 × 数千名)百万级，足够快。
        mentions: Dict[str, List[str]] = defaultdict(list)
        code_name: Dict[str, str] = {}
        sector_mentions: Dict[str, int] = defaultdict(int)
        sector_stocks: Dict[str, set] = defaultdict(set)

        for n in news:
            title = n.get("title") or ""
            if not title:
                continue
            hit_codes = []
            for nm, code in name_map.items():
                if nm in title:
                    mentions[code].append(title)
                    code_name[code] = nm
                    hit_codes.append(code)
            # 板块匹配用剥掉噪声短语的标题，避免"证券事务代表/证券虚假陈述"误命中板块"证券"
            sector_title = title
            for stop in self._SECTOR_STOPPHRASES:
                if stop in sector_title:
                    sector_title = sector_title.replace(stop, "")
            for sec in sector_names:
                if sec in sector_title:
                    sector_mentions[sec] += 1
                    sector_stocks[sec].update(hit_codes)

        if not mentions:
            return self._empty(now, hours, sector_mentions, sector_stocks, top_n)

        codes = list(mentions.keys())
        flow = self._fund_inflow(codes)
        cross = self._fusion_codes()
        min_mentions = getattr(settings, "HOTSPOT_MIN_MENTIONS", 2)
        fund_threshold = getattr(settings, "HOTSPOT_FUND_THRESHOLD", 30000000)

        hot_stocks = []
        for code, titles in mentions.items():
            mention_count = len(titles)
            inflow = float(flow.get(code, 0) or 0)
            has_inflow = inflow > fund_threshold
            cross_validated = code in cross
            # 强势过滤：多次报道 OR 主力净流入 OR 被 AI 智选选中
            if not (mention_count >= min_mentions or has_inflow or cross_validated):
                continue
            score = mention_count * 10 + (20 if has_inflow else 0) + (30 if cross_validated else 0)
            # 去重保序取最多 5 条标题
            uniq_titles = list(dict.fromkeys(titles))[:5]
            hot_stocks.append({
                "code": code,
                "name": code_name.get(code, ""),
                "mention_count": mention_count,
                "news_titles": uniq_titles,
                "has_fund_inflow": has_inflow,
                "fund_inflow_amount": round(inflow, 2),
                "cross_validated": cross_validated,
                "score": float(score),
            })

        hot_stocks.sort(key=lambda x: x["score"], reverse=True)
        hot_stocks = hot_stocks[:top_n]

        hot_sectors = self._build_sectors(sector_mentions, sector_stocks, code_name, top_n)

        return {
            "hot_stocks": hot_stocks,
            "hot_sectors": hot_sectors,
            "detected_at": now.isoformat(),
            "window_hours": hours,
        }

    # ─── 辅助 ────────────────────────────────────────────────────────────────
    def _build_name_library(self) -> Dict[str, str]:
        """股票名称 → code。名称字段优先 name → A股简称 → 公司名称（与全库口径一致）。"""
        name_map: Dict[str, str] = {}
        try:
            for s in self._db["stock_info"].find(
                {}, {"code": 1, "name": 1, "A股简称": 1, "公司名称": 1}):
                code = s.get("code")
                nm = s.get("name") or s.get("A股简称") or s.get("公司名称") or ""
                # 太短的名称（<2字）易误命中，跳过
                if code and nm and len(nm) >= 2:
                    name_map[nm] = code
        except Exception as e:
            logger.error(f"build name library failed: {e}")
        return name_map

    def _sector_names(self) -> List[str]:
        """板块名称库。block 集合实际以 block_type='sector' 存储，板块名在 '行业' 字段
        （非 BlockAnalyzer 假设的 block_name/concept）。返回长度≥2 的去重板块名。"""
        try:
            names = self._db["block"].distinct("行业", {"block_type": "sector"})
            return [s for s in names if s and len(s) >= 2]
        except Exception as e:
            logger.error(f"sector names failed: {e}")
            return []

    def _fund_inflow(self, codes: List[str]) -> Dict[str, float]:
        """近 2 个自然日各 code 的主力净流入合计（fund_flow.main_net_inflow）。"""
        d2 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        flow: Dict[str, float] = {}
        try:
            pipe = [
                {"$match": {"code": {"$in": codes}, "date": {"$gte": d2}}},
                {"$group": {"_id": "$code", "net": {"$sum": "$main_net_inflow"}}},
            ]
            for doc in self._db["fund_flow"].aggregate(pipe, allowDiskUse=True):
                flow[doc["_id"]] = float(doc.get("net") or 0)
        except Exception as e:
            logger.error(f"fund inflow agg failed: {e}")
        return flow

    def _fusion_codes(self) -> set:
        """最新一轮 AI 智选 picks 的代码集合，用于交叉验证。"""
        try:
            latest = self._db["fusion_pick_results"].find_one({}, sort=[("created_at", -1)])
            return {p.get("code") for p in ((latest or {}).get("picks") or []) if p.get("code")}
        except Exception as e:
            logger.error(f"fusion codes failed: {e}")
            return set()

    def _build_sectors(self, sector_mentions, sector_stocks, code_name, top_n) -> List[Dict]:
        sectors = []
        for sec, cnt in sector_mentions.items():
            related = [code_name.get(c, c) for c in list(sector_stocks.get(sec, set()))[:5]]
            sectors.append({
                "sector": sec,
                "mention_count": cnt,
                "related_stocks": related,
            })
        sectors.sort(key=lambda x: x["mention_count"], reverse=True)
        return sectors[:top_n]

    def _empty(self, now, hours, sector_mentions=None, sector_stocks=None, top_n=20) -> Dict:
        hot_sectors = []
        if sector_mentions:
            hot_sectors = self._build_sectors(sector_mentions, sector_stocks or {}, {}, top_n)
        return {
            "hot_stocks": [],
            "hot_sectors": hot_sectors,
            "detected_at": now.isoformat(),
            "window_hours": hours,
        }


if __name__ == "__main__":
    # ponytail: 离线自检——score 公式 + 排序逻辑，不依赖 DB。
    fund_threshold = 30000000
    min_mentions = 2

    def _score(mention_count, inflow, cross):
        has = inflow > fund_threshold
        if not (mention_count >= min_mentions or has or cross):
            return None
        return mention_count * 10 + (20 if has else 0) + (30 if cross else 0)

    assert _score(1, 0, False) is None              # 不达任何强势标准 → 过滤
    assert _score(3, 0, False) == 30                # 3 次报道
    assert _score(1, 5e7, False) == 30              # 单次但有大额净流入
    assert _score(1, 0, True) == 40                 # 单次但被 AI 智选选中
    assert _score(3, 5e7, True) == 80               # 三重信号
    rows = [{"score": s} for s in (30, 80, 40)]
    rows.sort(key=lambda x: x["score"], reverse=True)
    assert [r["score"] for r in rows] == [80, 40, 30]
    print("hotspot self-check ok")
