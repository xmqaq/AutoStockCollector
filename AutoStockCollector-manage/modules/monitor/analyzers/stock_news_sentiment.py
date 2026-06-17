"""
新闻舆情分析器 — 基于新闻标题/内容的关键词情感分析
从 MongoDB news 集合获取每只股票的相关新闻，输出利好/利空评分
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class StockNewsSentimentAnalyzer:
    POSITIVE_KEYWORDS = [
        "增长", "盈利", "突破", "利好", "创新", "合作", "扩张", "订单", "签约",
        "中标", "技术突破", "新高", "大涨", "涨停", "放量", "拉升", "回暖",
        "扭亏", "预增", "分红", "回购", "增持", "利好政策", "扶持",
    ]
    NEGATIVE_KEYWORDS = [
        "亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险", "召回",
        "调查", "处罚", "业绩下滑", "跌停", "暴跌", "暴雷", "违约",
        "st", "退市", "预警", "资金流出", "评级下调",
    ]

    def __init__(self, news_days: int = 7, max_news: int = 30):
        self._db = DatabaseConfig.get_database()
        self.news_days = news_days
        self.max_news = max_news

    def analyze(self, code: str, name: str = "", industry: str = "") -> Dict[str, Any]:
        try:
            news_items = self._fetch_news(code, name)
            if not news_items:
                return self._empty_result()

            return self._score_news(news_items)
        except Exception as e:
            logger.error(f"News sentiment analyze {code} failed: {e}")
            return self._empty_result()

    def _fetch_news(self, code: str, name: str) -> List[Dict]:
        if not name:
            return []

        since = (datetime.now() - timedelta(days=self.news_days)).strftime("%Y-%m-%d")
        name_query = name.replace("(", "").replace(")", "").strip()
        name_parts = [p for p in name_query.split() if p]
        name_terms = name_parts[:2] if name_parts else [name_query[:4]]

        title_regex = "|".join(name_terms)
        query = {
            "publish_date": {"$gte": since},
            "title": {"$regex": title_regex, "$options": "i"},
        }

        cursor = (
            self._db["news"]
            .find(query, {"title": 1, "publish_date": 1, "source": 1, "content": 1, "summary": 1})
            .sort("publish_date", -1)
            .limit(self.max_news)
        )
        return list(cursor)

    def _score_news(self, news_items: List[Dict]) -> Dict[str, Any]:
        total = len(news_items)
        positive_news = []
        negative_news = []
        neutral_news = []
        all_bullish_kws: set = set()
        all_bearish_kws: set = set()

        for item in news_items:
            title = item.get("title", "") or ""
            content = (item.get("content") or item.get("summary") or "") or ""
            text = title + " " + content

            pos_kws = [kw for kw in self.POSITIVE_KEYWORDS if kw in text]
            neg_kws = [kw for kw in self.NEGATIVE_KEYWORDS if kw in text]

            if pos_kws and not neg_kws:
                positive_news.append({
                    "title": title[:80],
                    "date": str(item.get("publish_date", ""))[:10],
                    "source": item.get("source", ""),
                    "keywords": pos_kws[:5],
                })
                all_bullish_kws.update(pos_kws)
            elif neg_kws and not pos_kws:
                negative_news.append({
                    "title": title[:80],
                    "date": str(item.get("publish_date", ""))[:10],
                    "source": item.get("source", ""),
                    "keywords": neg_kws[:5],
                })
                all_bearish_kws.update(neg_kws)
            else:
                neutral_news.append({
                    "title": title[:80],
                    "date": str(item.get("publish_date", ""))[:10],
                    "source": item.get("source", ""),
                })
                if pos_kws: all_bullish_kws.update(pos_kws)
                if neg_kws: all_bearish_kws.update(neg_kws)

        pos_count = len(positive_news)
        neg_count = len(negative_news)
        neutral_count = len(neutral_news)

        if total == 0:
            score = 50.0
        else:
            score = (pos_count / total) * 100

        if score >= 60:
            signal = "bullish"
        elif score <= 40:
            signal = "bearish"
        else:
            signal = "neutral"

        reasons = []
        if pos_count > 0:
            top_kws = list(all_bullish_kws)[:3]
            reasons.append(f"发现{pos_count}条利好新闻，提及关键词：{'、'.join(top_kws)}")
        if neg_count > 0:
            top_kws = list(all_bearish_kws)[:3]
            reasons.append(f"发现{neg_count}条利空新闻，提及关键词：{'、'.join(top_kws)}")
        if not reasons:
            reasons.append(f"近{self.news_days}天暂无相关舆情新闻")

        return {
            "overall": {
                "score": round(score, 1),
                "signal": signal,
                "bullish": score >= 60,
            },
            "news_count": total,
            "positive_count": pos_count,
            "negative_count": neg_count,
            "neutral_count": neutral_count,
            "recent_positive_news": positive_news[:5],
            "recent_negative_news": negative_news[:3],
            "keywords_found": {
                "bullish": sorted(all_bullish_kws),
                "bearish": sorted(all_bearish_kws),
            },
            "reasons": reasons[:3],
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "overall": {"score": 50.0, "signal": "neutral", "bullish": False},
            "news_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "recent_positive_news": [],
            "recent_negative_news": [],
            "keywords_found": {"bullish": [], "bearish": []},
            "reasons": ["暂无舆情新闻数据"],
        }
