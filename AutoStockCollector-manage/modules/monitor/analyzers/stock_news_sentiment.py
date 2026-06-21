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
    # 注意：关键词只在标题中匹配（content含免责声明/邮箱等干扰信息）
    POSITIVE_KEYWORDS = [
        "增长", "盈利", "突破", "利好", "创新", "合作", "扩张", "订单", "签约",
        "中标", "新高", "大涨", "涨停", "放量", "拉升", "回暖",
        "扭亏", "预增", "分红", "回购", "增持", "扶持",
        "上涨", "涨", "走高", "反弹", "回升", "向好", "改善", "加速",
    ]
    NEGATIVE_KEYWORDS = [
        "亏损", "下跌", "跌", "减持", "利空", "违规", "诉讼",
        "召回", "调查", "处罚", "业绩下滑", "跌停", "暴跌", "暴雷", "违约",
        "退市", "预警", "资金流出", "评级下调", "下滑", "下挫", "做空",
    ]

    def __init__(self, news_days: int = 30, max_news: int = 50):
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

    # 公司名常见后缀，去掉后得到核心名（如"贵州茅台酒股份" → 核心匹配仍按全名优先）
    _NAME_SUFFIXES = ["股份有限公司", "有限公司", "股份", "集团", "控股",
                      "科技", "实业", "公司", "(", ")", "（", "）"]

    _PROJECTION = {"title": 1, "publish_date": 1, "source": 1,
                   "content": 1, "summary": 1, "code": 1}

    def _fetch_news(self, code: str, name: str) -> List[Dict]:
        since = (datetime.now() - timedelta(days=self.news_days)).strftime("%Y-%m-%d")

        # 主路径：采集层已把 code 写实，直接按 code 精确查询（带/不带前缀都兜上）。
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        code_candidates = list({code, bare, f"SH{bare}", f"SZ{bare}"})
        cursor = (
            self._db["news"]
            .find({"code": {"$in": code_candidates},
                   "publish_date": {"$gte": since}}, self._PROJECTION)
            .sort("publish_date", -1)
            .limit(self.max_news)
        )
        items = list(cursor)
        if items:
            for it in items:
                it["match_method"] = "code_exact"
            return items

        # 兜底路径（数据尚未采集到的过渡期）：标题/正文模糊匹配。
        if not name:
            return []
        name_query = name.replace("(", "").replace(")", "").strip()

        terms = set()
        if name_query:
            terms.add(name_query)               # 公司全名精确优先
            core = name_query
            for suf in self._NAME_SUFFIXES:
                core = core.replace(suf, "")
            core = core.strip()
            if len(core) >= 2:
                terms.add(core)                 # 去后缀核心名
        # 代码纯数字部分作为补充匹配条件（OR）
        if bare.isdigit() and len(bare) >= 4:
            terms.add(bare)

        if not terms:
            return []

        import re as _re
        title_regex = "|".join(_re.escape(t) for t in terms)
        query = {
            "publish_date": {"$gte": since},
            "$or": [
                {"title": {"$regex": title_regex, "$options": "i"}},
                {"content": {"$regex": title_regex, "$options": "i"}},
            ],
        }
        cursor = (
            self._db["news"]
            .find(query, self._PROJECTION)
            .sort("publish_date", -1)
            .limit(self.max_news)
        )
        items = list(cursor)
        for it in items:
            it["match_method"] = "title_fallback"
        return items

    def _score_news(self, news_items: List[Dict]) -> Dict[str, Any]:
        total = len(news_items)
        positive_news = []
        negative_news = []
        neutral_news = []
        all_bullish_kws: set = set()
        all_bearish_kws: set = set()

        for item in news_items:
            title = item.get("title", "") or ""
            # 只在标题中匹配（正文含免责声明"市场有风险"、邮箱"biz@staff.*"等干扰）
            text = title

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
        elif pos_count == 0 and neg_count == 0:
            score = 50.0
        else:
            score = ((pos_count - neg_count) / total) * 50 + 50

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
                "bullish": signal == "bullish",
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
