"""
新闻舆情数据采集器
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.helpers import beijing_now
import pandas as pd
import akshare as ak
from .base import BaseCollector, ProgressTracker
from core.storage.mongo_storage import NewsStorage
from utils.logger import get_logger


logger = get_logger(__name__)


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
                df = func(**params) if params else func()
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

                if params:
                    df = func(**params)
                else:
                    df = func()

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

                if params:
                    df = func(**params)
                else:
                    df = func()

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
            df = ak.stock_board_industry_news_em(symbol=plate_code)
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
            df = ak.stock_market_activity_em()
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
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            logger.error(f"Failed to collect sector sentiment: {e}")
            return pd.DataFrame()

    def collect_hot_stocks(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if date is None:
                df = ak.stock_hot_rank_wc()
            else:
                df = ak.stock_hot_rank_wc(date=date)

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