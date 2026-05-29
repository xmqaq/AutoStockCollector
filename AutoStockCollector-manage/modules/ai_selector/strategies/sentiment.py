"""
舆情情绪事件驱动策略
"""
from typing import List, Dict, Any
from .base import BaseStrategy, SelectionResult
from modules.ai.ai_analyzer import ai_analyzer
from utils.logger import get_logger


logger = get_logger(__name__)


class SentimentDrivenStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="舆情情绪事件驱动",
            description="基于舆情情绪事件驱动选股"
        )
        self.min_score = 60.0
        self.max_stocks = 20

    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage
        from core.storage.mongo_storage import NewsStorage

        info_storage = StockInfoStorage()
        news_storage = NewsStorage()

        filtered = []
        for code in codes:
            info = info_storage.get_by_code(code)
            if not info:
                continue

            name = info.get("name", "")
            if any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                continue

            news = news_storage.get_latest_news(code=code, limit=10)
            if not news:
                continue

            filtered.append(code)

        return filtered

    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, NewsStorage

        kline_storage = KlineStorage()
        news_storage = NewsStorage()

        factors = {}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=10
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]
            factors["current_price"] = current
            factors["name"] = klines[0].get("name", "")

            if len(closes) >= 2 and closes[1] > 0:
                factors["change_pct"] = (current - closes[1]) / closes[1] * 100
            else:
                factors["change_pct"] = 0

            factors["technical_score"] = 50.0
            if factors["change_pct"] > 0:
                factors["technical_score"] += min(20, factors["change_pct"] * 3)
        else:
            factors["current_price"] = 0
            factors["name"] = ""
            factors["change_pct"] = 0
            factors["technical_score"] = 50.0

        news = news_storage.get_latest_news(code=code, limit=20)
        factors["sentiment_score"] = self._analyze_sentiment(news)
        factors["fundamental_score"] = 50.0
        factors["fund_flow_score"] = 50.0

        return factors

    def _analyze_sentiment(self, news: List[Dict[str, Any]]) -> float:
        if not news:
            return 50.0

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作", "扩张", "订单", "签约"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险", "调查"]

        positive_count = 0
        negative_count = 0

        for n in news:
            text = (n.get("title", "") + n.get("content", ""))

            for kw in positive_keywords:
                if kw in text:
                    positive_count += 1
                    break

            for kw in negative_keywords:
                if kw in text:
                    negative_count += 1
                    break

        total = positive_count + negative_count
        if total == 0:
            return 50.0

        return (positive_count / total) * 100

    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        sentiment = factors.get("sentiment_score", 50.0)
        technical = factors.get("technical_score", 50.0)
        change_pct = factors.get("change_pct", 0)

        total_score = sentiment * 0.7 + technical * 0.3

        if change_pct > 3:
            total_score = min(100, total_score + 5)
        elif change_pct < -3:
            total_score = max(0, total_score - 5)

        return max(0, min(100, total_score))