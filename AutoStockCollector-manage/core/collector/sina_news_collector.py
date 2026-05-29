"""
新浪财经新闻爬虫
从 https://finance.sina.com.cn/ 采集多种类型的财经新闻并分类存储
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import requests
from bs4 import BeautifulSoup
import re
import json
from .base import BaseCollector
from core.storage.mongo_storage import NewsStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class NewsCategory(Enum):
    GENERAL = "general"
    STOCK = "stock"
    FUND = "fund"
    FINANCE = "finance"
    ECONOMIC = "economic"
    GLOBAL = "global"
    INDUSTRY = "industry"
    POLICY = "policy"
    TECHNOLOGY = "technology"
    BREAKING = "breaking"


class SinaNewsCollector(BaseCollector):
    BASE_URL = "https://finance.sina.com.cn"

    CHANNEL_MAP = {
        "stock": {
            "name": "股票",
            "url": "https://finance.sina.com.cn/stock/",
            "pattern": r"finance\.sina\.com\.cn/stock/"
        },
        "fund": {
            "name": "基金",
            "url": "https://finance.sina.com.cn/money/fund/",
            "pattern": r"finance\.sina\.com\.cn/money/fund/"
        },
        "finance": {
            "name": "金融",
            "url": "https://finance.sina.com.cn/bank/",
            "pattern": r"finance\.sina\.com\.cn/(bank|insurance)/"
        },
        "futures": {
            "name": "期货",
            "url": "https://finance.sina.com.cn/futuremarket/",
            "pattern": r"finance\.sina\.com\.cn/future/"
        },
        "forex": {
            "name": "外汇",
            "url": "https://finance.sina.com.cn/forex/",
            "pattern": r"finance\.sina\.com\.cn/forex/"
        },
        "gold": {
            "name": "黄金",
            "url": "https://finance.sina.com.cn/nmetal/",
            "pattern": r"finance\.sina\.com\.cn/(nmetal|gold)/"
        },
        "tech": {
            "name": "科技",
            "url": "https://tech.sina.com.cn/",
            "pattern": r"tech\.sina\.com\.cn/"
        },
        "economic": {
            "name": "宏观经济",
            "url": "https://finance.sina.com.cn/macro/",
            "pattern": r"finance\.sina\.com\.cn/macro/"
        },
        "real_estate": {
            "name": "房地产",
            "url": "https://finance.sina.com.cn/realestate/",
            "pattern": r"finance\.sina\.com\.cn/realestate/"
        }
    }

    ROLL_NEWS_CHANNELS = [
        {"cid": "56594", "name": "基金", "pattern": r"finance\.sina\.com\.cn/money/fund/"},
        {"cid": "56595", "name": "股票", "pattern": r"finance\.sina\.com\.cn/stock/"},
        {"cid": "56597", "name": "期货", "pattern": r"finance\.sina\.com\.cn/future/"},
        {"cid": "56599", "name": "外汇", "pattern": r"finance\.sina\.com\.cn/forex/"},
        {"cid": "56600", "name": "贵金属", "pattern": r"finance\.sina\.com\.cn/nmetal/"},
        {"cid": "56602", "name": "理财", "pattern": r"finance\.sina\.com\.cn/money/"},
        {"cid": "56593", "name": "要闻", "pattern": r"finance\.sina\.com\.cn/(roll|jxw)/"},
    ]

    def __init__(self):
        super().__init__()
        self.storage = NewsStorage()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://finance.sina.com.cn/"
        })

    def collect(self, date: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        all_records = []

        channels_to_collect = [
            "stock", "fund", "futures", "forex", "gold", "economic"
        ]

        for channel in channels_to_collect:
            try:
                records = self.execute_with_retry(
                    self.collect_channel_news,
                    channel=channel,
                    limit=limit // len(channels_to_collect)
                )
                if records:
                    all_records.extend(records)
                    logger.info(f"Collected {len(records)} news from channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to collect channel {channel}: {e}")

        try:
            records = self.execute_with_retry(self.collect_roll_news, limit=limit)
            if records:
                all_records.extend(records)
        except Exception as e:
            logger.error(f"Failed to collect roll news: {e}")

        try:
            records = self.execute_with_retry(self.collect_breaking_news, limit=20)
            if records:
                all_records.extend(records)
        except Exception as e:
            logger.error(f"Failed to collect breaking news: {e}")

        if all_records:
            self.storage.save_news_batch(all_records)
            logger.info(f"Total collected: {len(all_records)} news items")

        return all_records

    def collect_channel_news(
        self,
        channel: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if channel not in self.CHANNEL_MAP:
            logger.warning(f"Unknown channel: {channel}")
            return []

        channel_info = self.CHANNEL_MAP[channel]
        url = channel_info["url"]
        pattern = channel_info["pattern"]

        records = []
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            news_links = soup.find_all("a", href=re.compile(r"finance\.sina\.com\.cn"))
            for link in news_links[:limit]:
                try:
                    title = link.get_text(strip=True)
                    href = link.get("href", "")

                    if not title or len(title) < 10:
                        continue

                    if href.startswith("//"):
                        href = "https:" + href

                    record = {
                        "title": title,
                        "url": href,
                        "news_type": channel,
                        "channel_name": channel_info["name"],
                        "source": "新浪财经",
                        "publish_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "_updated_at": datetime.now(),
                        "_collect_at": datetime.now()
                    }
                    records.append(record)

                except Exception as e:
                    logger.debug(f"Failed to parse news link: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Request failed for channel {channel}: {e}")

        return records

    def collect_roll_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        all_records = []

        for channel in self.ROLL_NEWS_CHANNELS:
            try:
                url = f"https://finance.sina.com.cn/roll/index.d.html?cid={channel['cid']}&page=1"
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                response.encoding = "utf-8"

                soup = BeautifulSoup(response.text, "html.parser")

                news_items = soup.find_all("li")
                for item in news_items[:limit // len(self.ROLL_NEWS_CHANNELS)]:
                    try:
                        link = item.find("a")
                        if not link:
                            continue

                        title = link.get_text(strip=True)
                        href = link.get("href", "")

                        if not title or len(title) < 5:
                            continue

                        if href.startswith("//"):
                            href = "https:" + href

                        time_elem = item.find("span", class_="time")
                        publish_date = time_elem.get_text(strip=True) if time_elem else datetime.now().strftime("%Y-%m-%d")

                        record = {
                            "title": title,
                            "url": href,
                            "news_type": self._categorize_by_url(href, channel["pattern"]),
                            "channel_name": channel["name"],
                            "source": "新浪财经",
                            "publish_date": publish_date,
                            "_updated_at": datetime.now(),
                            "_collect_at": datetime.now()
                        }
                        all_records.append(record)

                    except Exception as e:
                        logger.debug(f"Failed to parse roll news item: {e}")
                        continue

            except requests.RequestException as e:
                logger.error(f"Request failed for roll channel {channel['name']}: {e}")

        return all_records

    def collect_breaking_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        records = []

        try:
            url = "https://finance.sina.com.cn/"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            breaking_section = soup.find("div", id="blk_rollnews_02")
            if breaking_section:
                links = breaking_section.find_all("a", href=True)
            else:
                all_links = soup.find_all("a", href=re.compile(r"sina\.com\.cn.*\.shtml"))
                links = [l for l in all_links if l.find_parent("script") is None][:limit]

            for link in links[:limit]:
                try:
                    title = link.get_text(strip=True)
                    href = link.get("href", "")

                    if not title or len(title) < 10:
                        continue

                    if href.startswith("//"):
                        href = "https:" + href

                    record = {
                        "title": title,
                        "url": href,
                        "news_type": "breaking",
                        "channel_name": "突发",
                        "source": "新浪财经",
                        "publish_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "is_breaking": True,
                        "_updated_at": datetime.now(),
                        "_collect_at": datetime.now()
                    }
                    records.append(record)

                except Exception as e:
                    logger.debug(f"Failed to parse breaking news: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Request failed for breaking news: {e}")

        return records

    def collect_7x24_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        records = []

        try:
            url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                "page": 1,
                "num": limit,
                "lid": 2516,
                "k": "",
                "r": 0.5
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            if data.get("result", {}).get("status", {}).get("code") == 0:
                items = data.get("result", {}).get("data", [])
                for item in items:
                    record = {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "news_type": self._categorize_by_url(item.get("url", "")),
                        "channel_name": "7x24快讯",
                        "source": "新浪财经",
                        "publish_date": item.get("ctime", ""),
                        "datetime": item.get("ctime", ""),
                        "_updated_at": datetime.now(),
                        "_collect_at": datetime.now()
                    }
                    records.append(record)

        except requests.RequestException as e:
            logger.error(f"Request failed for 7x24 news: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse 7x24 JSON: {e}")

        return records

    def _categorize_by_url(self, url: str, specific_pattern: str = None) -> str:
        if specific_pattern and re.search(specific_pattern, url):
            return specific_pattern.split("finance\\.sina\\.com\\.cn/")[1].split("/")[0]

        patterns = {
            "stock": r"finance\.sina\.com\.cn/stock/",
            "fund": r"finance\.sina\.com\.cn/money/fund/",
            "futures": r"finance\.sina\.com\.cn/future/",
            "forex": r"finance\.sina\.com\.cn/forex/",
            "nmetal": r"finance\.sina\.com\.cn/nmetal/",
            "bank": r"finance\.sina\.com\.cn/bank/",
            "macro": r"finance\.sina\.com\.cn/macro/",
            "realestate": r"finance\.sina\.com\.cn/realestate/",
            "tech": r"tech\.sina\.com\.cn/",
            "roll": r"finance\.sina\.com\.cn/roll/",
            "jxw": r"finance\.sina\.com\.cn/jjxw/",
        }

        for category, pattern in patterns.items():
            if re.search(pattern, url):
                return category

        return "general"

    def collect_by_category(
        self,
        category: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        if category == "7x24":
            return self.collect_7x24_news(limit=limit)
        elif category == "breaking":
            return self.collect_breaking_news(limit=limit)
        elif category in self.CHANNEL_MAP:
            return self.collect_channel_news(channel=category, limit=limit)
        else:
            logger.warning(f"Unknown category: {category}")
            return []

    def get_news_summary(self) -> Dict[str, int]:
        summary = {}
        for channel in list(self.CHANNEL_MAP.keys()) + ["breaking", "7x24"]:
            summary[channel] = 0
        return summary

    def close(self):
        self.session.close()