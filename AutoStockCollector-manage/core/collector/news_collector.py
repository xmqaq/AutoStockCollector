"""
新闻舆情数据采集器
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from utils.helpers import beijing_now
import pandas as pd
import akshare as ak
from .base import BaseCollector, ProgressTracker
from core.storage.mongo_storage import NewsStorage
from utils.helpers import call_with_timeout
from utils.logger import get_logger


logger = get_logger(__name__)

# akshare 接口无内置超时，外部源不响应时会无限阻塞，拖死采集任务（卡满后被看门狗强杀）。
# 所有 akshare 拉取统一套硬超时兜底。
_AK_TIMEOUT_SECONDS = 30


def _bare(code: str) -> str:
    """去掉 SH/SZ 前缀，返回纯 6 位代码。"""
    return code[2:] if code[:2] in ("SH", "SZ") else code


def _full(code: str) -> str:
    """补全 SH/SZ 前缀。"""
    code = str(code).strip().upper()
    if code.startswith(("SH", "SZ")):
        return code
    if code.startswith("6") or code.startswith("9"):
        return "SH" + code
    if code.startswith(("0", "3")):
        return "SZ" + code
    return code


def _pick(row, *candidates) -> str:
    """从一行里按候选列名顺序取第一个非空值（列名在不同 akshare 版本会变）。"""
    for c in candidates:
        v = row.get(c, "")
        if v is not None and str(v).strip():
            return str(v)
    return ""


class NewsCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = NewsStorage()

    def collect(
        self,
        date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        all_records = []

        try:
            records = self.execute_with_retry(self.collect_recent_news, limit=limit)
            if records:
                all_records.extend(records)
        except Exception as e:
            logger.error(f"Failed to collect recent news: {e}")

        try:
            records = self.execute_with_retry(self.collect_stock_news)
            if records:
                all_records.extend(records)
        except Exception as e:
            logger.error(f"Failed to collect stock news: {e}")

        if all_records:
            self.storage.save_news_batch(all_records)

        # 轨道一：对当前监控名单做个股精确采集（公告 + 个股新闻），失败不影响主流程。
        try:
            codes = self.watchlist_codes()
            if codes:
                self.collect_watchlist_announcements(codes)
                self.collect_watchlist_stock_news(codes)
        except Exception as e:
            logger.error(f"Failed to collect watchlist news: {e}")

        return all_records

    # ─── 监控名单代码 ────────────────────────────────────────────────────────
    def watchlist_codes(self) -> List[str]:
        """当前需要精确采集新闻的股票：自选股(watchlist) + 持仓(positions)，去重补全前缀。"""
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        codes = set()
        try:
            for c in db["watchlist"].distinct("code", {"enabled": True}):
                if c:
                    codes.add(_full(c))
        except Exception as e:
            logger.warning(f"watchlist_codes watchlist failed: {e}")
        try:
            for c in db["positions"].distinct("code"):
                if c:
                    codes.add(_full(c))
        except Exception as e:
            logger.warning(f"watchlist_codes positions failed: {e}")
        return sorted(codes)

    # ─── 轨道一：个股公告（按代码精确） ──────────────────────────────────────
    def collect_watchlist_announcements(self, codes: List[str]) -> List[Dict[str, Any]]:
        """逐只抓个股公告，每条显式写入 code（带前缀）和 news_type='announcement'。
        单只超时/失败不影响其他股票。

        说明（见排查结论）：akshare 的 stock_notice_report 的 symbol 是公告"类别"
        （全部/重大事项/...）+ date，返回的是全市场该类公告，并非按代码精确。真正
        按个股查的接口是 stock_zh_a_disclosure_report_cninfo(symbol=纯代码, ...)，
        这里用它。接口缺失时优雅跳过（轨道一仍有个股新闻 + 分析层标题兜底）。
        """
        if not codes:
            return []
        from config.settings import settings
        days = getattr(settings, "NEWS_WATCHLIST_DAYS", 30)
        end = beijing_now().strftime("%Y%m%d")
        start = (beijing_now() - timedelta(days=days)).strftime("%Y%m%d")

        func = getattr(ak, "stock_zh_a_disclosure_report_cninfo", None)
        if func is None:
            logger.warning("stock_zh_a_disclosure_report_cninfo unavailable, skip announcements")
            return []

        all_records: List[Dict[str, Any]] = []
        for code in codes:
            bare = _bare(code)
            full = _full(code)
            try:
                df = call_with_timeout(
                    func, _AK_TIMEOUT_SECONDS,
                    symbol=bare, market="沪深京",
                    start_date=start, end_date=end,
                )
            except Exception as e:
                logger.warning(f"announcement {code} failed: {e}")
                continue
            if df is None or df.empty:
                continue

            records = []
            for _, row in df.iterrows():
                title = _pick(row, "公告标题", "标题", "title")
                if not title:
                    continue
                records.append({
                    "code": full,
                    "title": title,
                    "content": _pick(row, "公告内容", "内容"),
                    "publish_date": _pick(row, "公告时间", "时间", "公告日期", "publish_date"),
                    "source": _pick(row, "公告来源", "来源") or "cninfo",
                    "url": _pick(row, "公告链接", "链接", "url"),
                    "news_type": "announcement",
                    "_updated_at": beijing_now(),
                })
            if records:
                self.storage.save_news_batch(records)
                all_records.extend(records)
                logger.info(f"collect_watchlist_announcements {code}: {len(records)} records")

        return all_records

    # ─── 轨道一：个股新闻（按代码精确） ──────────────────────────────────────
    def collect_watchlist_stock_news(self, codes: List[str]) -> List[Dict[str, Any]]:
        """逐只抓个股新闻并把 code 写实。

        说明（见排查结论）：akshare 的 stock_news_em(symbol=股票代码) 本就是"个股
        新闻"接口（返回该代码相关的最近约 100 条新闻）。原 collect() 里用 symbol='all'
        是把它当全市场新闻用——那条路不带 code。这里改回按代码逐只查询，采集时就把
        code 写实，不再靠标题模糊匹配。
        单只超时/失败继续下一只。
        """
        if not codes:
            return []
        func = getattr(ak, "stock_news_em", None)
        if func is None:
            logger.warning("stock_news_em unavailable, skip watchlist stock news")
            return []

        all_records: List[Dict[str, Any]] = []
        for code in codes:
            bare = _bare(code)
            full = _full(code)
            try:
                df = call_with_timeout(func, _AK_TIMEOUT_SECONDS, symbol=bare)
            except Exception as e:
                logger.warning(f"stock_news_em {code} failed: {e}")
                continue
            if df is None or df.empty:
                continue

            records = []
            for _, row in df.iterrows():
                title = _pick(row, "新闻标题", "标题", "title")
                if not title:
                    continue
                records.append({
                    "code": full,
                    "title": title,
                    "content": _pick(row, "新闻内容", "摘要", "content"),
                    "publish_date": _pick(row, "发布时间", "时间", "publish_date"),
                    "source": _pick(row, "文章来源", "来源", "source"),
                    "url": _pick(row, "新闻链接", "链接", "url"),
                    "news_type": "stock",
                    "_updated_at": beijing_now(),
                })
            if records:
                self.storage.save_news_batch(records)
                all_records.extend(records)
                logger.info(f"collect_watchlist_stock_news {code}: {len(records)} records")

        return all_records

    def collect_recent_news(self, limit: int = 100) -> List[Dict[str, Any]]:
        # stock_news_em: 东方财富综合新闻（有实际标题和内容）
        # news_economic_baidu: 百度经济日历（宏观经济事件，非新闻）
        sources = [
            ("stock_news_em", {"symbol": "all"}, {
                "新闻标题": "title", "新闻内容": "content",
                "发布时间": "publish_date", "文章来源": "source", "新闻链接": "url"
            }),
            ("stock_news_main_cx", {}, {
                "标题": "title", "摘要": "content",
                "时间": "publish_date", "来源": "source", "链接": "url"
            }),
        ]
        for func_name, params, col_map in sources:
            try:
                func = getattr(ak, func_name, None)
                if func is None:
                    continue
                df = call_with_timeout(func, _AK_TIMEOUT_SECONDS, **params)
                if df is None or df.empty:
                    continue

                records = []
                for _, row in df.iterrows():
                    record = {
                        "title": str(row.get(next((k for k, v in col_map.items() if v == "title"), ""), "")),
                        "content": str(row.get(next((k for k, v in col_map.items() if v == "content"), ""), "")),
                        "publish_date": str(row.get(next((k for k, v in col_map.items() if v == "publish_date"), ""), "")),
                        "source": str(row.get(next((k for k, v in col_map.items() if v == "source"), ""), "")),
                        "url": str(row.get(next((k for k, v in col_map.items() if v == "url"), ""), "")),
                        "news_type": "general",
                        "_updated_at": beijing_now(),
                    }
                    records.append(record)

                if records:
                    logger.info(f"collect_recent_news got {len(records)} records via {func_name}")
                    return records[:limit]

            except Exception as e:
                logger.warning(f"collect_recent_news via {func_name} failed: {e}")

        return []

    def collect_stock_news(self) -> List[Dict[str, Any]]:
        data_sources = [
            ("stock_news_em", {"symbol": "all"}),
            ("stock_news_main_cx", {}),
        ]

        all_records = []
        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for stock news")

                df = call_with_timeout(func, _AK_TIMEOUT_SECONDS, **params)

                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    record = {
                        "title": row.get("新闻标题", ""),
                        "publish_date": row.get("发布时间", ""),
                        "source": row.get("文章来源", ""),
                        "url": row.get("新闻链接", ""),
                        "news_type": "stock",
                        "_updated_at": beijing_now()
                    }
                    all_records.append(record)

                if all_records:
                    break

            except Exception as e:
                logger.warning(f"{source_name} failed: {e}")
                continue

        return all_records

    def collect_announcement(
        self,
        code: str,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        symbol = code[2:]

        data_sources = [
            ("stock_notice_report", {"symbol": symbol}),
            ("stock_news_em", {"symbol": "all"}),
            ("stock_news_main_cx", {}),
        ]

        all_records = []
        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for announcement")

                df = call_with_timeout(func, _AK_TIMEOUT_SECONDS, **params)

                if df is None or df.empty:
                    continue

                df["code"] = code
                df["_updated_at"] = beijing_now()
                records = self.normalize_dataframe(df, code)
                all_records.extend(records)

                if all_records:
                    break

            except Exception as e:
                logger.warning(f"{source_name} failed: {e}")
                continue

        return all_records

    def collect_single(self, code: str, date: Optional[str] = None):
        records = self.collect_announcement(code, date)
        if records:
            return records
        return None

    def collect_plate_news(self, plate_code: str) -> List[Dict[str, Any]]:
        try:
            df = call_with_timeout(ak.stock_board_industry_news_em, _AK_TIMEOUT_SECONDS, symbol=plate_code)
            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                record = {
                    "title": row.get("新闻标题", ""),
                    "publish_date": row.get("发布时间", ""),
                    "source": row.get("文章来源", ""),
                    "url": row.get("新闻链接", ""),
                    "plate_code": plate_code,
                    "news_type": "plate",
                    "_updated_at": beijing_now()
                }
                records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to collect plate news for {plate_code}: {e}")
            return []


class SentimentCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect_market_sentiment(self) -> Optional[Dict[str, Any]]:
        try:
            df = call_with_timeout(ak.stock_market_activity_em, _AK_TIMEOUT_SECONDS)
            if df is None or df.empty:
                return None

            sentiment = {
                "date": beijing_now().strftime("%Y-%m-%d"),
                "上涨家数": df.iloc[0].get("上涨家数", 0),
                "下跌家数": df.iloc[0].get("下跌家数", 0),
                "平盘家数": df.iloc[0].get("平盘家数", 0),
                "总成交额": df.iloc[0].get("总成交额", 0),
                "_updated_at": beijing_now()
            }

            return sentiment

        except Exception as e:
            logger.error(f"Failed to collect market sentiment: {e}")
            return None

    def collect_sector_sentiment(self) -> pd.DataFrame:
        try:
            df = call_with_timeout(ak.stock_board_industry_name_em, _AK_TIMEOUT_SECONDS)
            return df
        except Exception as e:
            logger.error(f"Failed to collect sector sentiment: {e}")
            return pd.DataFrame()

    def collect_hot_stocks(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if date is None:
                df = call_with_timeout(ak.stock_hot_rank_wc, _AK_TIMEOUT_SECONDS)
            else:
                df = call_with_timeout(ak.stock_hot_rank_wc, _AK_TIMEOUT_SECONDS, date=date)

            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                record = {
                    "rank": row.get("排名", 0),
                    "code": row.get("股票代码", ""),
                    "name": row.get("股票名称", ""),
                    "change_percent": row.get("涨跌幅", 0),
                    "hot_score": row.get("关注指数", 0),
                    "date": date or beijing_now().strftime("%Y-%m-%d"),
                    "_updated_at": beijing_now()
                }
                records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to collect hot stocks: {e}")
            return []
