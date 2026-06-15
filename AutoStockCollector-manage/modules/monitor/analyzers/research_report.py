"""
研报分析器 — 从财务数据 + AI深度报告提取投资评级
- 短期: 近期财务变化 momentum、报告活跃度
- 长期: 成长性、盈利质量、估值合理性
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from config.database import DatabaseConfig
from core.storage.mongo_storage import FinancialStorage, ValuationStorage
from utils.logger import get_logger

logger = get_logger(__name__)


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        fv = float(v)
        return fv if fv != 0 else None
    except (ValueError, TypeError):
        return None


class ResearchReportAnalyzer:
    SHORT_DAYS = 30
    LONG_DAYS = 120

    def __init__(self):
        self._fin = FinancialStorage()
        self._val = ValuationStorage()
        self._db = DatabaseConfig.get_database()

    def analyze(self, code: str, name: str) -> Dict[str, Any]:
        financials = self._get_financials(code)
        deep_report = self._get_deep_report(code)
        val = self._val.get_by_code(code)

        if not financials and not deep_report and not val:
            return self._empty_result("数据不足")

        short = self._analyze_short_term(financials, deep_report)
        long_ = self._analyze_long_term(financials, deep_report, val)
        combined = self._combine(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **combined,
            "report_count": len(financials),
            "has_deep_report": deep_report is not None,
        }

    def _get_financials(self, code: str) -> List[Dict[str, Any]]:
        """获取历史财务数据"""
        records = list(self._fin.find_many(
            {"code": code, "report_type": "annual"},
            sort=[("report_date", -1)],
            limit=5,
        ))
        result = []
        for r in records:
            r.pop("_id", None)
            result.append(r)
        return result

    def _get_deep_report(self, code: str) -> Optional[Dict[str, Any]]:
        """获取 AI 深度分析报告"""
        r = self._db["ai_deep_reports"].find_one(
            {"code": code},
            sort=[("created_at", -1)],
        )
        if r:
            r.pop("_id", None)
        return r

    def _analyze_short_term(self, financials: List[Dict], deep_report: Optional[Dict]) -> Dict[str, Any]:
        score = 50
        reasons = []

        # 短期: 最近一期财务数据变化
        if financials:
            latest = financials[0]
            np_growth = _f(latest.get("净利润同比增长率"))
            roe = _f(latest.get("净资产收益率"))

            if np_growth:
                if np_growth > 50:
                    score += 20
                    reasons.append(f"净利润暴增{np_growth:.0f}%")
                elif np_growth > 20:
                    score += 12
                    reasons.append(f"净利润增长{np_growth:.0f}%")
                elif np_growth > 0:
                    score += 5
                elif np_growth < -30:
                    score -= 20
                    reasons.append(f"净利润下滑{np_growth:.0f}%")
                elif np_growth < 0:
                    score -= 8
                    reasons.append("净利润小幅下滑")

            if roe and roe > 20:
                score += 8
                reasons.append(f"ROE{roe:.1f}% 优秀")

            # 多期趋势
            if len(financials) >= 2:
                prev_growth = _f(financials[1].get("净利润同比增长率"))
                if np_growth and prev_growth:
                    if np_growth > prev_growth:
                        score += 5
                        reasons.append("盈利增速提升")
                    elif np_growth < prev_growth:
                        score -= 3
                        reasons.append("盈利增速放缓")

        # AI深度报告
        if deep_report:
            score += 5
            reasons.append("有AI深度分析报告")

        score = max(10, min(90, score))
        signal = self._signal_from_score(score)

        if not reasons:
            reasons.append("暂无近期研报数据")

        return {
            "score": round(score, 1),
            "signal": signal,
            "reasons": reasons[:3],
            "recent_count": len(financials),
        }

    def _analyze_long_term(self, financials: List[Dict], deep_report: Optional[Dict], val: Optional[Dict]) -> Dict[str, Any]:
        score = 50
        reasons = []
        targets = {}

        # 成长性评分
        growth_score = 50
        if financials:
            latest = financials[0]
            np_growth = _f(latest.get("净利润同比增长率"))
            roe = _f(latest.get("净资产收益率"))
            eps = _f(latest.get("基本每股收益"))

            growth_score = 50
            if np_growth:
                growth_score += min(np_growth * 0.5, 30)
            if roe:
                growth_score += min(roe * 2, 20)
            growth_score = max(0, min(100, growth_score))

            reasons.append(f"成长性评分{growth_score:.0f}")
            if roe:
                reasons.append(f"ROE{roe:.1f}%")
            if eps:
                targets["eps"] = round(eps, 2)

        # 估值评分
        val_score = 50
        if val:
            pe = _f(val.get("pe_dynamic")) or _f(val.get("pe"))
            pb = _f(val.get("pb"))
            if pe and pe < 15:
                val_score = 80
                reasons.append(f"PE{pe:.1f} 低估")
            elif pe and pe < 25:
                val_score = 65
                reasons.append(f"PE{pe:.1f} 合理偏低")
            elif pe and pe < 40:
                val_score = 50
            elif pe and pe >= 60:
                val_score = 25
                reasons.append(f"PE{pe:.0f} 高估")
            if pb:
                targets["pb"] = round(pb, 2)

        score = growth_score * 0.5 + val_score * 0.5
        score = max(10, min(90, score))
        signal = self._signal_from_score(score)

        if deep_report:
            reasons.append("AI深度分析可用")

        if not reasons:
            reasons.append("暂无长期研报数据")

        return {
            "score": round(score, 1),
            "signal": signal,
            "total_reports": len(financials),
            "reasons": reasons[:3],
            "target_price": targets,
        }

    def _combine(self, short: Dict, long_: Dict) -> Dict:
        score = short.get("score", 50) * 0.3 + long_.get("score", 50) * 0.7
        signal = self._signal_from_score(score)
        return {"composite_score": round(score, 1), "composite_signal": signal}

    def _signal_from_score(self, score: float) -> str:
        if score >= 75:
            return "strong_buy"
        elif score >= 62:
            return "buy"
        elif score >= 38:
            return "hold"
        elif score >= 25:
            return "sell"
        else:
            return "strong_sell"

    def _empty_result(self, reason: str) -> Dict:
        return {
            "short_term": {
                "score": 50.0, "signal": "hold",
                "reasons": [reason], "recent_count": 0,
            },
            "long_term": {
                "score": 50.0, "signal": "hold",
                "total_reports": 0, "reasons": [reason],
                "target_price": {},
            },
            "composite_score": 50.0,
            "composite_signal": "hold",
            "report_count": 0,
            "has_deep_report": False,
        }
