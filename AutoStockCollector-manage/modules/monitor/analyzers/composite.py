"""
综合评分器 — 将各维度分析结果融合为短线和长线投资建议

短期信号权重:
  - 资金流向短期 (40%)
  - 技术面短期 (30%)
  - 研报短期 momentum (30%)

长期信号权重:
  - 资金流向长期 (35%)
  - 基本面 (35%)
  - 研报长期 (30%)
"""
from typing import Any, Dict, List, Tuple


class CompositeAnalyzer:
    # 短期各维度权重
    SHORT_WEIGHTS = {
        "fund_flow": 0.40,
        "technical": 0.30,
        "research": 0.30,
    }
    # 长期各维度权重
    LONG_WEIGHTS = {
        "fund_flow": 0.35,
        "fundamental": 0.35,
        "research": 0.30,
    }

    SIGNAL_ORDER = ["strong_buy", "buy", "hold", "sell", "strong_sell"]
    SIGNAL_LABELS = {
        "strong_buy": "强烈买入",
        "buy": "买入",
        "hold": "持有",
        "sell": "卖出",
        "strong_sell": "强烈卖出",
    }

    def composite(
        self,
        fund_flow: Dict[str, Any],
        research: Dict[str, Any],
        technical: Dict[str, Any],
        fundamental: Dict[str, Any],
    ) -> Dict[str, Any]:
        short = self._compose_short(fund_flow, research, technical)
        long_ = self._compose_long(fund_flow, research, fundamental)
        final = self._final_advice(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **final,
        }

    def _compose_short(
        self,
        fund_flow: Dict[str, Any],
        research: Dict[str, Any],
        technical: Dict[str, Any],
    ) -> Dict[str, Any]:
        scores = []
        reasons = []

        ff_score = fund_flow.get("short_term", {}).get("score", 50)
        scores.append(("主力资金", ff_score, self.SHORT_WEIGHTS["fund_flow"]))
        if ff_score >= 60:
            reasons.extend(fund_flow.get("short_term", {}).get("reasons", [])[:1])
        elif ff_score <= 40:
            reasons.extend(fund_flow.get("short_term", {}).get("reasons", [])[:1])

        tech_score = technical.get("short_term", {}).get("score", 50)
        scores.append(("技术面", tech_score, self.SHORT_WEIGHTS["technical"]))
        if tech_score >= 60 or tech_score <= 40:
            reasons.extend(technical.get("short_term", {}).get("reasons", [])[:1])

        res_score = research.get("short_term", {}).get("score", 50)
        scores.append(("研报", res_score, self.SHORT_WEIGHTS["research"]))
        if research.get("short_term", {}).get("recent_count", 0) > 0:
            r_reasons = research.get("short_term", {}).get("reasons", [])[:1]
            reasons.extend(r_reasons)

        raw_score = sum(s * w for _, s, w in scores)
        total_score = self._stretch(raw_score)
        signal = self._score_to_signal(total_score)

        return {
            "score": round(total_score, 1),
            "signal": signal,
            "signal_label": self.SIGNAL_LABELS[signal],
            "breakdown": {k: round(v, 1) for k, v, _ in scores},
            "reasons": reasons[:4],
            "weights": dict(self.SHORT_WEIGHTS),
        }

    def _compose_long(
        self,
        fund_flow: Dict[str, Any],
        research: Dict[str, Any],
        fundamental: Dict[str, Any],
    ) -> Dict[str, Any]:
        scores = []
        reasons = []

        ff_score = fund_flow.get("long_term", {}).get("score", 50)
        scores.append(("主力资金", ff_score, self.LONG_WEIGHTS["fund_flow"]))
        if ff_score >= 60:
            reasons.extend(fund_flow.get("long_term", {}).get("reasons", [])[:1])
        elif ff_score <= 40:
            reasons.extend(fund_flow.get("long_term", {}).get("reasons", [])[:1])

        fund_score = fundamental.get("score", 50)
        scores.append(("基本面", fund_score, self.LONG_WEIGHTS["fundamental"]))
        if fund_score >= 60 or fund_score <= 40:
            reasons.extend(fundamental.get("reasons", [])[:1])

        res_score = research.get("long_term", {}).get("score", 50)
        scores.append(("研报", res_score, self.LONG_WEIGHTS["research"]))
        if research.get("long_term", {}).get("total_reports", 0) > 0:
            r_reasons = research.get("long_term", {}).get("reasons", [])[:1]
            reasons.extend(r_reasons)

        raw_score = sum(s * w for _, s, w in scores)
        total_score = self._stretch(raw_score)
        signal = self._score_to_signal(total_score)

        return {
            "score": round(total_score, 1),
            "signal": signal,
            "signal_label": self.SIGNAL_LABELS[signal],
            "breakdown": {k: round(v, 1) for k, v, _ in scores},
            "reasons": reasons[:4],
            "weights": dict(self.LONG_WEIGHTS),
        }

    def _stretch(self, score: float) -> float:
        """拉伸分数，扩大区分度。将 40-60 区间拉伸到 20-80。"""
        if 40 <= score <= 60:
            return (score - 40) * 2 + 20
        return score

    def _final_advice(self, short: Dict, long_: Dict) -> Dict:
        """生成最终综合建议"""
        s_score = short["score"]
        l_score = long_["score"]
        combined_score = self._stretch(s_score * 0.5 + l_score * 0.5)
        combined_signal = self._score_to_signal(combined_score)

        # 短/长期分歧提示
        divergence = ""
        if s_score >= 65 and l_score <= 35:
            divergence = "短期看好、长期偏弱，注意控制仓位"
        elif s_score <= 35 and l_score >= 65:
            divergence = "短期承压、长期看好，可逢低布局"
        elif abs(s_score - l_score) <= 8:
            divergence = "短长期一致"

        return {
            "composite_score": round(combined_score, 1),
            "composite_signal": combined_signal,
            "composite_label": self.SIGNAL_LABELS[combined_signal],
            "divergence": divergence,
        }

    def _score_to_signal(self, score: float) -> str:
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
