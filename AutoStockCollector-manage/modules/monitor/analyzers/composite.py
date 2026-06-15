"""
综合评分器 — 将各维度分析结果融合为短线和长线投资建议

参考量化选股+策略选股评分体系，扩展五维度评分:

短期信号权重:
  - 资金流向短期 (35%) — 短期资金博弈主导
  - 技术面短期 (30%) — 价格趋势确认
  - 研报短期 momentum (20%) — 催化剂
  - 估值面 (15%) — 安全边际参考

长期信号权重:
  - 基本面 (30%) — 盈利质量
  - 资金流向长期 (25%) — 长线资金
  - 研报长期 (20%) — 成长性
  - 估值面 (15%) — 估值水位
  - 技术面 (10%) — 趋势辅助
"""
from typing import Any, Dict

class CompositeAnalyzer:
    SHORT_WEIGHTS = {
        "fund_flow": 0.35,
        "technical": 0.30,
        "research": 0.20,
        "valuation": 0.15,
    }
    LONG_WEIGHTS = {
        "fundamental": 0.30,
        "fund_flow": 0.25,
        "research": 0.20,
        "valuation": 0.15,
        "technical": 0.10,
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
        valuation: Dict[str, Any],
    ) -> Dict[str, Any]:
        short = self._compose_short(fund_flow, research, technical, valuation)
        long_ = self._compose_long(fund_flow, research, fundamental, valuation, technical)
        final = self._final_advice(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **final,
        }

    def _compose_short(
        self,
        fund_flow: Dict,
        research: Dict,
        technical: Dict,
        valuation: Dict,
    ) -> Dict:
        scores = []
        reasons = []

        ff_score = fund_flow.get("short_term", {}).get("score", 50)
        scores.append(("主力资金", ff_score, self.SHORT_WEIGHTS["fund_flow"]))
        self._add_reason(reasons, fund_flow.get("short_term", {}), ff_score)

        tech_score = technical.get("short_term", {}).get("score", 50)
        scores.append(("技术面", tech_score, self.SHORT_WEIGHTS["technical"]))
        self._add_reason(reasons, technical.get("short_term", {}), tech_score)

        res_score = research.get("short_term", {}).get("score", 50)
        scores.append(("研报", res_score, self.SHORT_WEIGHTS["research"]))
        if research.get("short_term", {}).get("recent_count", 0) > 0:
            r_rs = research.get("short_term", {}).get("reasons", [])[:1]
            reasons.extend(r_rs)

        val_score = valuation.get("score", 50)
        scores.append(("估值", val_score, self.SHORT_WEIGHTS["valuation"]))
        self._add_reason(reasons, valuation, val_score)

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
        fund_flow: Dict,
        research: Dict,
        fundamental: Dict,
        valuation: Dict,
        technical: Dict,
    ) -> Dict:
        scores = []
        reasons = []

        fund_score = fundamental.get("score", 50)
        scores.append(("基本面", fund_score, self.LONG_WEIGHTS["fundamental"]))
        self._add_reason(reasons, fundamental, fund_score)

        ff_score = fund_flow.get("long_term", {}).get("score", 50)
        scores.append(("主力资金", ff_score, self.LONG_WEIGHTS["fund_flow"]))
        self._add_reason(reasons, fund_flow.get("long_term", {}), ff_score)

        res_score = research.get("long_term", {}).get("score", 50)
        scores.append(("研报", res_score, self.LONG_WEIGHTS["research"]))
        if research.get("long_term", {}).get("total_reports", 0) > 0:
            r_rs = research.get("long_term", {}).get("reasons", [])[:1]
            reasons.extend(r_rs)

        val_score = valuation.get("score", 50)
        scores.append(("估值", val_score, self.LONG_WEIGHTS["valuation"]))
        self._add_reason(reasons, valuation, val_score)

        tech_score = technical.get("long_term", {}).get("score", 50)
        scores.append(("技术面", tech_score, self.LONG_WEIGHTS["technical"]))
        self._add_reason(reasons, technical.get("long_term", {}), tech_score)

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

    def _add_reason(self, reasons: list, src: Dict, score: float):
        if score >= 60 or score <= 40:
            reasons.extend(src.get("reasons", [])[:1])

    def _stretch(self, score: float) -> float:
        """拉伸分数，扩大区分度。将 40-60 区间拉伸到 20-80。"""
        if 40 <= score <= 60:
            return (score - 40) * 2 + 20
        return score

    def _final_advice(self, short: Dict, long_: Dict) -> Dict:
        s_score = short["score"]
        l_score = long_["score"]
        combined_score = self._stretch(s_score * 0.5 + l_score * 0.5)
        combined_signal = self._score_to_signal(combined_score)

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
        if score >= 75: return "strong_buy"
        elif score >= 62: return "buy"
        elif score >= 38: return "hold"
        elif score >= 25: return "sell"
        else: return "strong_sell"
