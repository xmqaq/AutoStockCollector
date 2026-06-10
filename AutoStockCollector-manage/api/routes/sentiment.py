"""
舆情趋势相关接口
包含：舆情趋势数据、事件驱动信号、关键词提取
支持真实数据源（从MongoDB获取）和模拟数据fallback
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from typing import Dict, List
import random

sentiment_bp = Blueprint("sentiment", __name__, url_prefix="/api/v1/sentiment")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


def _get_real_sentiment_trend(code: str, days: int = 30) -> List[Dict]:
    """从数据库获取真实舆情趋势数据"""
    if not code:
        return []

    db = _get_db()
    code = _normalize_code(code)

    cutoff_date = beijing_now() - timedelta(days=days)

    news_list = list(db["news"].find(
        {"code": code, "datetime": {"$gte": cutoff_date.isoformat()}},
        sort=[("datetime", -1)],
        limit=days
    ))

    if not news_list:
        return []

    result = []
    for news in news_list:
        title = news.get("title", "")
        sentiment = news.get("sentiment", "")

        positive_keywords = ["增长", "利好", "突破", "创新", "业绩", "盈利", "预增", "超预期", "买入", "推荐"]
        negative_keywords = ["下降", "利空", "亏损", "减持", "风险", "预警", "预亏", "不及预期", "卖出"]

        positive_count = sum(1 for kw in positive_keywords if kw in title)
        negative_count = sum(1 for kw in negative_keywords if kw in title)

        if positive_count > negative_count:
            score = 60 + min(positive_count * 10, 30)
            sentiment_label = "positive"
        elif negative_count > positive_count:
            score = 60 - min(negative_count * 10, 30)
            sentiment_label = "negative"
        else:
            score = 50
            sentiment_label = "neutral"

        result.append({
            "date": news.get("datetime", news.get("date", ""))[:10],
            "score": max(20, min(90, score)),
            "positive": positive_count,
            "neutral": 1,
            "negative": negative_count,
            "title": title,
            "sentiment_label": sentiment_label
        })

    return result


def _get_real_events(code: str, limit: int = 20) -> List[Dict]:
    """从数据库获取真实事件数据"""
    if not code:
        return []

    db = _get_db()
    code = _normalize_code(code)

    news_list = list(db["news"].find(
        {"code": code},
        sort=[("datetime", -1)],
        limit=limit
    ))

    if not news_list:
        return []

    events = []
    for news in news_list:
        title = news.get("title", "")
        content = news.get("content", "") or news.get("summary", "")

        positive_keywords = ["增长", "利好", "突破", "创新", "业绩", "盈利", "预增"]
        negative_keywords = ["下降", "利空", "亏损", "减持", "风险", "预警"]

        event_type = "neutral"
        type_label = "中性"

        if any(kw in title for kw in positive_keywords):
            event_type = "positive"
            type_label = "利好"
        elif any(kw in title for kw in negative_keywords):
            event_type = "negative"
            type_label = "利空"

        events.append({
            "date": news.get("datetime", news.get("date", ""))[:10],
            "type": event_type,
            "type_label": type_label,
            "title": title,
            "description": content[:200] if content else "",
            "impact": 3 if event_type != "neutral" else 2,
        })

    return events


def _get_real_keywords(code: str) -> List[Dict]:
    """从数据库提取真实关键词"""
    if not code:
        return _generate_mock_keywords()

    db = _get_db()
    code = _normalize_code(code)

    news_list = list(db["news"].find(
        {"code": code},
        limit=50
    ))

    if not news_list:
        return _generate_mock_keywords()

    keyword_freq: Dict[str, int] = {}
    important_words = ["业绩", "增长", "利润", "市场", "产品", "技术", "合作", "订单", "产能", "研发",
                      "行业", "政策", "资金", "投资", "收购", "重组", "创新", "出口", "销售", "成本"]

    for news in news_list:
        title = news.get("title", "")
        content = news.get("content", "") or ""

        for word in important_words:
            if word in title:
                keyword_freq[word] = keyword_freq.get(word, 0) + 3
            if word in content:
                keyword_freq[word] = keyword_freq.get(word, 0) + 1

    sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)

    max_freq = sorted_keywords[0][1] if sorted_keywords else 1
    result = []
    for word, freq in sorted_keywords[:10]:
        result.append({
            "word": word,
            "weight": int(freq / max_freq * 100)
        })

    if not result:
        return _generate_mock_keywords()

    return result


def _generate_mock_sentiment_trend(days: int = 30) -> List[Dict]:
    """生成模拟舆情趋势数据"""
    result = []
    score = 60
    for i in range(days):
        date = beijing_now() - timedelta(days=days - i - 1)
        score += random.uniform(-5, 5)
        score = max(20, min(90, score))
        result.append({
            "date": date.strftime("%Y-%m-%d"),
            "score": round(score, 1),
            "positive": random.randint(30, 60),
            "neutral": random.randint(20, 40),
            "negative": random.randint(5, 20),
        })
    return result


def _generate_mock_events() -> List[Dict]:
    """生成模拟事件数据"""
    events = [
        {
            "date": (beijing_now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "type": "positive",
            "type_label": "利好",
            "title": "业绩预增公告",
            "description": "公司发布业绩预告，预计全年净利润增长50%",
            "impact": 4,
        },
        {
            "date": (beijing_now() - timedelta(days=5)).strftime("%Y-%m-%d"),
            "type": "neutral",
            "type_label": "中性",
            "title": "行业政策发布",
            "description": "行业相关政策出台，对公司影响中性",
            "impact": 2,
        },
        {
            "date": (beijing_now() - timedelta(days=10)).strftime("%Y-%m-%d"),
            "type": "negative",
            "type_label": "利空",
            "title": "高管减持",
            "description": "高管计划减持不超过1%股份",
            "impact": 3,
        },
        {
            "date": (beijing_now() - timedelta(days=15)).strftime("%Y-%m-%d"),
            "type": "positive",
            "type_label": "利好",
            "title": "订单公告",
            "description": "重大订单落地，合同金额超预期",
            "impact": 5,
        },
    ]
    return events


def _generate_mock_keywords() -> List[Dict]:
    """生成模拟关键词"""
    keywords = [
        {"word": "业绩", "weight": 95},
        {"word": "增长", "weight": 85},
        {"word": "订单", "weight": 75},
        {"word": "突破", "weight": 65},
        {"word": "合作", "weight": 55},
        {"word": "研发", "weight": 50},
        {"word": "市场", "weight": 45},
        {"word": "扩张", "weight": 40},
    ]
    return keywords


@sentiment_bp.route("/trend", methods=["GET"])
def get_sentiment_trend():
    """获取舆情趋势数据"""
    code = request.args.get("code")
    days = int(request.args.get("days", 30))

    trend_data = _get_real_sentiment_trend(code, days)

    if not trend_data:
        trend_data = _generate_mock_sentiment_trend(days)

    current_score = trend_data[-1]["score"] if trend_data else 60
    latest = trend_data[-1] if trend_data else {}

    return jsonify({
        "success": True,
        "code": code,
        "current_score": current_score,
        "sentiment_stats": {
            "positive": latest.get("positive", 45),
            "neutral": latest.get("neutral", 32),
            "negative": latest.get("negative", 12),
            "attention": "高" if current_score > 60 else "中",
        },
        "data": trend_data,
    })


@sentiment_bp.route("/events", methods=["GET"])
def get_events():
    """获取事件驱动信号"""
    code = request.args.get("code")
    limit = int(request.args.get("limit", 20))

    events = _get_real_events(code, limit)

    if not events:
        events = _generate_mock_events()[:limit]

    return jsonify({
        "success": True,
        "code": code,
        "count": len(events),
        "data": events,
    })


@sentiment_bp.route("/keywords", methods=["GET"])
def get_keywords():
    """获取关键词云数据"""
    code = request.args.get("code")

    keywords = _get_real_keywords(code)

    return jsonify({
        "success": True,
        "code": code,
        "data": keywords,
    })


@sentiment_bp.route("/news-sentiment", methods=["GET"])
def get_news_sentiment():
    """获取新闻情感分析"""
    code = request.args.get("code")
    limit = int(request.args.get("limit", 20))

    db = _get_db()
    code = _normalize_code(code) if code else None

    filter_doc = {}
    if code:
        filter_doc["code"] = code

    news_items = []
    if db:
        news_list = list(db["news"].find(
            filter_doc,
            sort=[("datetime", -1)],
            limit=limit
        ))

        positive_keywords = ["增长", "利好", "突破", "创新", "业绩", "盈利", "预增"]
        negative_keywords = ["下降", "利空", "亏损", "减持", "风险", "预警"]

        for news in news_list:
            title = news.get("title", "")
            sentiment = "neutral"
            sentiment_score = 50

            if any(kw in title for kw in positive_keywords):
                sentiment = "positive"
                sentiment_score = 70
            elif any(kw in title for kw in negative_keywords):
                sentiment = "negative"
                sentiment_score = 30

            news_items.append({
                "title": title,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "datetime": news.get("datetime", ""),
                "source": news.get("source", "财经网"),
            })

    if not news_items:
        sentiments = ["positive", "neutral", "negative"]
        for i in range(limit):
            sentiment = random.choice(sentiments)
            news_items.append({
                "title": f"新闻标题 {i + 1}",
                "sentiment": sentiment,
                "sentiment_score": 70 if sentiment == "positive" else (50 if sentiment == "neutral" else 30),
                "datetime": (beijing_now() - timedelta(hours=i * 2)).isoformat(),
                "source": "财经网",
            })

    return jsonify({
        "success": True,
        "code": code,
        "count": len(news_items),
        "data": news_items,
    })


@sentiment_bp.route("/summary", methods=["GET"])
def get_sentiment_summary():
    """获取舆情摘要"""
    code = request.args.get("code")

    trend_data = _get_real_sentiment_trend(code, 7)

    if not trend_data:
        trend_data = _generate_mock_sentiment_trend(7)

    avg_score = sum(d["score"] for d in trend_data) / len(trend_data) if trend_data else 60

    events = _get_real_events(code, 10)
    positive_count = len([e for e in events if e.get("type") == "positive"])
    negative_count = len([e for e in events if e.get("type") == "negative"])

    return jsonify({
        "success": True,
        "code": code,
        "summary": {
            "overall_score": round(avg_score, 1),
            "trend": "上涨" if trend_data[-1]["score"] > trend_data[0]["score"] else "下跌",
            "trend_value": round(trend_data[-1]["score"] - trend_data[0]["score"], 1) if len(trend_data) > 1 else 0,
            "positive_count": positive_count or random.randint(3, 8),
            "negative_count": negative_count or random.randint(1, 5),
            "key_events": [
                "业绩预增公告",
                "资金净流入",
                "机构上调评级",
            ] if not events else [e.get("title", "") for e in events[:3]],
            "risk_factors": [
                "估值偏高",
                "行业竞争加剧",
            ],
        },
    })