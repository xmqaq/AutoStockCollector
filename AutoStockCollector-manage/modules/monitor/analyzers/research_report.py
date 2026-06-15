"""
研报分析器 — 从新闻中提取个股研报信息，分析机构评级、目标价
- 短期: 近期研报评级变化 momentum
- 长期: 机构一致预期、目标价 vs 现价、盈利预测
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from core.storage.mongo_storage import NewsStorage, ValuationStorage
from utils.logger import get_logger

logger = get_logger(__name__)

# 评级关键词 → 分数
RATING_MAP: Dict[str, float] = {
    "买入": 90, "强烈推荐": 90, "推荐": 80, "增持": 75, "优于大市": 70,
    "中性": 50, "持有": 50, "同步大市": 50,
    "减持": 30, "卖出": 10, "强烈卖出": 5,
}

RATING_PAT = re.compile(
    "|".join(re.escape(k) for k in RATING_MAP)
)


class ResearchReportAnalyzer:
    SHORT_DAYS = 30
    LONG_DAYS = 120

    def __init__(self):
        self._news = NewsStorage()
        self._val = ValuationStorage()

    def analyze(self, code: str, name: str) -> Dict[str, Any]:
        reports = self._get_reports(code, name)
        val = self._val.get_by_code(code)

        if not reports and not val:
            return self._empty_result("暂无研报数据")

        short = self._analyze_short_term(reports)
        long_ = self._analyze_long_term(reports, val)
        combined = self._combine(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **combined,
            "report_count": len(reports),
        }

    def _get_reports(self, code: str, name: str) -> List[Dict[str, Any]]:
        """从新闻中筛选个股相关研报"""
        bare_code = code.replace(".SZ", "").replace(".SH", "").replace("SH", "").replace("SZ", "")
        keywords = [bare_code]
        if name and name != "未知":
            keywords.append(name)

        cutoff = (datetime.now() - timedelta(days=self.LONG_DAYS)).isoformat()
        pattern = re.compile("|".join(re.escape(k) for k in keywords))

        # 搜索标题包含股票代码或名称，且内容偏向研报的新闻
        news = self._news.find_many(
            {"publish_date": {"$gte": cutoff}},
            sort=[("publish_date", -1)],
            limit=200,
        )
        results = []
        for n in news:
            title = n.get("title", "")
            if pattern.search(title):
                rating = self._extract_rating(title + (n.get("content", "") or ""))
                target_price = self._extract_target_price(title)
                results.append({
                    "title": title,
                    "date": str(n.get("publish_date", ""))[:10],
                    "rating": rating,
                    "rating_score": RATING_MAP.get(rating, 50),
                    "target_price": target_price,
                })
        return results[:50]

    def _analyze_short_term(self, reports: List[Dict]) -> Dict[str, Any]:
        recent = [r for r in reports if r["date"] >= (datetime.now() - timedelta(days=self.SHORT_DAYS)).strftime("%Y-%m-%d")]
        if not recent:
            return self._short_empty()

        scores = [r["rating_score"] for r in recent if r["rating_score"] != 50]
        avg_score = sum(scores) / len(scores) if scores else 50

        # 评级变化 momentum: 最近 vs 之前
        mid = len(recent) // 2
        if mid > 0:
            recent_avg = sum(r["rating_score"] for r in recent[:mid]) / mid
        else:
            recent_avg = avg_score

        momentum = recent_avg - avg_score
        score = min(100, max(0, avg_score + momentum * 2))
        signal = self._signal_from_score(score)

        reasons = []
        if momentum > 5:
            reasons.append("近期评级上调")
        elif momentum < -5:
            reasons.append("近期评级下调")
        reasons.append(f"近{self.SHORT_DAYS}天{len(recent)}份研报")
        if scores:
            reasons.append(f"平均评级评分{avg_score:.0f}")

        # 目标价信息
        target_prices = [r["target_price"] for r in recent if r["target_price"]]
        price_info = {}
        if target_prices:
            price_info = {
                "avg_target": round(sum(target_prices) / len(target_prices), 2),
                "max_target": max(target_prices),
                "min_target": min(target_prices),
                "report_count": len(target_prices),
            }

        return {
            "score": round(score, 1),
            "signal": signal,
            "avg_rating_score": round(avg_score, 1),
            "momentum": round(momentum, 1),
            "recent_count": len(recent),
            "reasons": reasons[:3],
            "target_price": price_info,
        }

    def _analyze_long_term(self, reports: List[Dict], val: Optional[Dict]) -> Dict[str, Any]:
        score = 50
        reasons = []
        price_info = {}

        # 基于全部研报的机构一致预期
        if reports:
            all_scores = [r["rating_score"] for r in reports if r["rating_score"] != 50]
            consensus = sum(all_scores) / len(all_scores) if all_scores else 50
            score = consensus

            # 目标价一致预期
            targets = [r["target_price"] for r in reports if r["target_price"]]
            if targets:
                avg_target = sum(targets) / len(targets)
                price_info["consensus_target"] = round(avg_target, 2)
                price_info["target_reports"] = len(targets)

            total = len(reports)
            reasons.append(f"近{self.LONG_DAYS}天共{total}份研报")
            reasons.append(f"机构一致评分{score:.0f}")

            # 评级分布
            buys = sum(1 for r in reports if r["rating_score"] >= 70)
            sells = sum(1 for r in reports if r["rating_score"] <= 30)
            if total > 0:
                reasons.append(f"买入{buys}/{total} 减持{sells}/{total}")

        # 结合估值
        if val:
            pe = val.get("pe_dynamic") or val.get("pe", 0)
            pb = val.get("pb", 0)
            if pe and 0 < pe < 50:
                score += 10  # PE合理加分
                reasons.append(f"PE{pe:.1f} 估值合理")
            elif pe and pe >= 100:
                score -= 10
                reasons.append(f"PE{pe:.0f} 估值偏高")

        score = max(0, min(100, score))
        signal = self._signal_from_score(score)

        return {
            "score": round(score, 1),
            "signal": signal,
            "total_reports": len(reports),
            "reasons": reasons[:3],
            "target_price": price_info,
        }

    def _combine(self, short: Dict, long_: Dict) -> Dict:
        score = short.get("score", 50) * 0.4 + long_.get("score", 50) * 0.6
        signal = self._signal_from_score(score)
        return {"composite_score": round(score, 1), "composite_signal": signal}

    def _extract_rating(self, text: str) -> str:
        match = RATING_PAT.search(text)
        return match.group(0) if match else ""

    def _extract_target_price(self, text: str) -> Optional[float]:
        """提取目标价"""
        patterns = [
            r"目标价[约~]?(\d+\.?\d*)",
            r"看[好涨到至]?[到]?(\d+\.?\d*)元",
            r"(\d+\.?\d*)元目标",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def _signal_from_score(self, score: float) -> str:
        if score >= 75:
            return "strong_buy"
        elif score >= 60:
            return "buy"
        elif score >= 40:
            return "hold"
        elif score >= 20:
            return "sell"
        else:
            return "strong_sell"

    def _empty_result(self, reason: str) -> Dict:
        return {
            "short_term": self._short_empty(reason),
            "long_term": {
                "score": 50.0, "signal": "hold",
                "total_reports": 0, "reasons": [reason],
                "target_price": {},
            },
            "composite_score": 50.0,
            "composite_signal": "hold",
            "report_count": 0,
        }

    def _short_empty(self, reason: str = "暂无近期研报") -> Dict:
        return {
            "score": 50.0, "signal": "hold",
            "avg_rating_score": 50.0, "momentum": 0,
            "recent_count": 0, "reasons": [reason],
            "target_price": {},
        }
