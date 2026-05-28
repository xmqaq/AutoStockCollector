"""
舆情时间衰减权重模块
实现舆情时间衰减因子，确保研判聚焦最新市场动态
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from core.storage.mongo_storage import NewsStorage
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class NewsItem:
    title: str
    content: str
    publish_date: str
    sentiment_score: float
    source: str = ""
    relevance_score: float = 1.0


@dataclass
class WeightedNews:
    news: NewsItem
    decay_factor: float
    weighted_score: float
    days_ago: int


class SentimentDecayCalculator:
    def __init__(
        self,
        half_life_days: float = 3.0,
        max_age_days: int = 30
    ):
        self.half_life_days = half_life_days
        self.max_age_days = max_age_days
        self.decay_rate = 0.693 / half_life_days

    def calculate_decay_factor(self, publish_date: str) -> float:
        try:
            if isinstance(publish_date, str):
                if "T" in publish_date:
                    pub_dt = datetime.fromisoformat(publish_date.replace("Z", "+08:00"))
                else:
                    pub_dt = datetime.strptime(publish_date, "%Y-%m-%d %H:%M:%S")
            elif isinstance(publish_date, datetime):
                pub_dt = publish_date
            else:
                return 0.0

            days_ago = (datetime.now() - pub_dt).total_seconds() / 86400

            if days_ago > self.max_age_days:
                return 0.0

            decay_factor = pow(2, -days_ago / self.half_life_days)
            return max(0.0, min(1.0, decay_factor))

        except Exception as e:
            logger.error(f"Decay calculation error: {e}")
            return 0.0

    def get_news_weight(
        self,
        news_items: List[NewsItem]
    ) -> List[WeightedNews]:
        weighted_news = []

        for news in news_items:
            decay_factor = self.calculate_decay_factor(news.publish_date)

            if decay_factor > 0:
                weighted_score = news.sentiment_score * decay_factor * news.relevance_score
                days_ago = self._calculate_days_ago(news.publish_date)

                weighted_news.append(WeightedNews(
                    news=news,
                    decay_factor=decay_factor,
                    weighted_score=weighted_score,
                    days_ago=days_ago
                ))

        weighted_news.sort(key=lambda x: x.weighted_score, reverse=True)
        return weighted_news

    def _calculate_days_ago(self, publish_date: str) -> int:
        try:
            if isinstance(publish_date, str):
                if "T" in publish_date:
                    pub_dt = datetime.fromisoformat(publish_date.replace("Z", "+08:00"))
                else:
                    pub_dt = datetime.strptime(publish_date, "%Y-%m-%d %H:%M:%S")
            elif isinstance(publish_date, datetime):
                pub_dt = publish_date
            else:
                return 999

            return max(0, int((datetime.now() - pub_dt).total_seconds() / 86400))
        except:
            return 999

    def calculate_aggregated_sentiment(
        self,
        news_items: List[NewsItem]
    ) -> Dict[str, Any]:
        if not news_items:
            return {
                "sentiment_score": 50.0,
                "sentiment_label": "neutral",
                "news_count": 0,
                "weighted_count": 0,
                "recent_positive": 0,
                "recent_negative": 0
            }

        weighted_news = self.get_news_weight(news_items)

        if not weighted_news:
            return {
                "sentiment_score": 50.0,
                "sentiment_label": "neutral",
                "news_count": len(news_items),
                "weighted_count": 0,
                "recent_positive": 0,
                "recent_negative": 0
            }

        total_weighted_score = sum(w.weighted_score for w in weighted_news)
        avg_weighted_score = total_weighted_score / len(weighted_news)

        recent_positive = sum(
            1 for w in weighted_news
            if w.days_ago <= 7 and w.weighted_score > 60
        )

        recent_negative = sum(
            1 for w in weighted_news
            if w.days_ago <= 7 and w.weighted_score < 40
        )

        sentiment_label = "neutral"
        if avg_weighted_score > 60:
            sentiment_label = "positive"
        elif avg_weighted_score < 40:
            sentiment_label = "negative"

        return {
            "sentiment_score": round(avg_weighted_score, 2),
            "sentiment_label": sentiment_label,
            "news_count": len(news_items),
            "weighted_count": len(weighted_news),
            "recent_positive": recent_positive,
            "recent_negative": recent_negative,
            "top_news": [
                {
                    "title": w.news.title,
                    "score": round(w.weighted_score, 2),
                    "days_ago": w.days_ago,
                    "decay_factor": round(w.decay_factor, 3)
                }
                for w in weighted_news[:5]
            ]
        }


class NewsDecayEnhancer:
    def __init__(self):
        self.news_storage = NewsStorage()
        self.decay_calculator = SentimentDecayCalculator()

    def enhance_sentiment_analysis(
        self,
        code: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        news_data = self.news_storage.get_latest_news(code=code, limit=limit)

        if not news_data:
            return {
                "code": code,
                "sentiment_score": 50.0,
                "sentiment_label": "neutral",
                "enhanced": False,
                "message": "No news data available"
            }

        news_items = []
        for news in news_data:
            sentiment = self._analyze_single_news(news)
            news_items.append(NewsItem(
                title=news.get("title", ""),
                content=news.get("content", ""),
                publish_date=news.get("publish_date", ""),
                sentiment_score=sentiment,
                source=news.get("source", ""),
                relevance_score=1.0
            ))

        result = self.decay_calculator.calculate_aggregated_sentiment(news_items)
        result["code"] = code
        result["enhanced"] = True

        return result

    def _analyze_single_news(self, news: Dict[str, Any]) -> float:
        title = news.get("title", "")
        content = news.get("content", "")

        positive_keywords = [
            "增长", "盈利", "突破", "利好", "创新", "合作", "扩张",
            "收购", "签约", "中标", "业绩", "提升", "大涨", "涨停"
        ]

        negative_keywords = [
            "亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险",
            "调查", "处罚", "暴跌", "跌停", "警示", "整改", "造假"
        ]

        text = title + content
        positive_count = sum(1 for kw in positive_keywords if kw in text)
        negative_count = sum(1 for kw in negative_keywords if kw in text)

        if positive_count > negative_count:
            base_score = 50 + (positive_count - negative_count) * 10
        elif negative_count > positive_count:
            base_score = 50 - (negative_count - positive_count) * 10
        else:
            base_score = 50.0

        return max(0.0, min(100.0, base_score))


sentiment_decay_calculator = SentimentDecayCalculator()
news_decay_enhancer = NewsDecayEnhancer()