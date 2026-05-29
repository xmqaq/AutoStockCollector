"""
舆情情绪因子库
"""
from typing import List, Dict, Any
from .base import FactorBase, FactorData, factor_registry
from utils.logger import get_logger


logger = get_logger(__name__)


class SentimentFactor(FactorBase):
    def __init__(self):
        super().__init__(name="sentiment", category="sentiment")
        self._positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作", "扩张", "订单", "签约", "中标", "技术突破"]
        self._negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "诉讼", "风险", "召回", "调查", "处罚", "业绩下滑"]

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        news_data = kwargs.get("news_data", [])

        if not news_data:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        positive_count = 0
        negative_count = 0
        total_mentions = 0

        for news in news_data:
            title = news.get("title", "")
            content = news.get("content", "")
            text = title + content
            total_mentions += 1

            for kw in self._positive_keywords:
                if kw in text:
                    positive_count += 1
                    break

            for kw in self._negative_keywords:
                if kw in text:
                    negative_count += 1
                    break

        total = positive_count + negative_count
        if total == 0:
            score = 50.0
        else:
            score = (positive_count / total) * 100

        sentiment_label = "neutral"
        if score > 65:
            sentiment_label = "positive"
        elif score < 35:
            sentiment_label = "negative"

        result = FactorData(
            code=code,
            name=news_data[0].get("name", ""),
            date=news_data[0].get("date", ""),
            values={
                "sentiment_score": float(score),
                "sentiment_label": sentiment_label,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "total_mentions": total_mentions,
                "sentiment_intensity": float(total / total_mentions) if total_mentions > 0 else 0.0
            },
            score=float(score)
        )
        self._save_to_cache(result)
        return result


class MarketSentimentFactor(FactorBase):
    def __init__(self):
        super().__init__(name="market_sentiment", category="sentiment")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 10:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        from collections import Counter
        changes = []
        for i in range(len(kline_data) - 1):
            prev = kline_data[i + 1].get("close", 0)
            curr = kline_data[i].get("close", 0)
            if prev > 0:
                change = (curr - prev) / prev * 100
                changes.append(change)

        if not changes:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        positive_days = sum(1 for c in changes[:10] if c > 0)
        negative_days = sum(1 for c in changes[:10] if c < 0)
        avg_change = sum(changes[:10]) / min(len(changes), 10)

        score = 50.0
        if positive_days > 7:
            score = 80.0
        elif positive_days > 5:
            score = 65.0
        elif negative_days > 7:
            score = 30.0
        elif negative_days > 5:
            score = 40.0
        else:
            score = 50.0 + avg_change * 2

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "positive_days": positive_days,
                "negative_days": negative_days,
                "avg_change": float(avg_change),
                "market_sentiment_score": score
            },
            score=score
        )
        self._save_to_cache(result)
        return result


factor_registry.register(SentimentFactor())
factor_registry.register(MarketSentimentFactor())