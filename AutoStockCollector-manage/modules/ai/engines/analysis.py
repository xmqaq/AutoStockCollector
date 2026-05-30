"""个股深度分析引擎。编排 DAL → 因子引擎 → LLMRouter → 内容风控 → 结构化结果。
依赖 dal/router 注入便于测试。LLM 失败降级为纯因子结果（source=factor）。
"""
from typing import Any, Dict, Optional

from modules.ai.foundation import factors
from modules.ai.content_risk import sanitize_text, RISK_DISCLAIMER

# 综合评分权重
_WEIGHTS = {"technical": 0.4, "fundamental": 0.25, "fund_flow": 0.2, "sentiment": 0.15}


class AnalysisEngine:
    def __init__(self, dal=None, router=None):
        if dal is None:
            from modules.ai.foundation.dal import StockDAL
            dal = StockDAL()
        if router is None:
            from modules.ai.foundation.llm_router import LLMRouter
            router = LLMRouter()
        self.dal = dal
        self.router = router

    def analyze(self, code: str, use_cache: bool = True) -> Dict[str, Any]:
        bundle = self.dal.get_stock_bundle(code)

        technical = factors.trend_score(bundle.closes)
        volume = factors.volume_score(bundle.volumes)
        technical_dim = round(technical * 0.7 + volume * 0.3, 2)
        fundamental = factors.valuation_score(bundle.pe, bundle.pb, bundle.ps)
        fund_flow = factors.fund_flow_score(bundle.main_net_inflow)
        sentiment = 50.0  # 占位，舆情雷达后续期接入

        scores = {
            "technical": technical_dim,
            "fundamental": fundamental,
            "fund_flow": fund_flow,
            "sentiment": sentiment,
        }
        scores["composite"] = round(factors.composite_score(scores, _WEIGHTS), 2)

        prompt = self._build_prompt(bundle, scores)
        schema = {"summary": "str", "recommendation": "str", "risk_factors": "list"}
        llm_result = self.router.chat(prompt, schema=schema, use_cache=use_cache, task_type="stock_analysis")

        llm_payload: Optional[Dict[str, Any]] = None
        source = "factor"
        if llm_result.success and llm_result.data:
            data = llm_result.data
            summary, _ = sanitize_text(str(data.get("summary", "")))
            recommendation, _ = sanitize_text(str(data.get("recommendation", "")))
            risks = [sanitize_text(str(r))[0] for r in (data.get("risk_factors") or [])]
            llm_payload = {"summary": summary, "recommendation": recommendation, "risk_factors": risks}
            source = "llm"

        current_price = bundle.realtime_price or (bundle.closes[0] if bundle.closes else None)
        return {
            "code": bundle.code,
            "name": bundle.name,
            "scores": scores,
            "current_price": current_price,
            "llm": llm_payload,
            "source": source,
            "disclaimer": RISK_DISCLAIMER,
        }

    def _build_prompt(self, bundle, scores: Dict[str, float]) -> str:
        current_price = bundle.realtime_price or (bundle.closes[0] if bundle.closes else "NA")
        return (
            f"分析股票 {bundle.code}（{bundle.name}）的投资价值。\n"
            f"量化因子得分(0-100)：技术面={scores['technical']}，基本面={scores['fundamental']}，"
            f"资金面={scores['fund_flow']}，综合={scores['composite']}。\n"
            f"当前价={current_price}，PE={bundle.pe}，PB={bundle.pb}。\n"
            f"请给出客观、稳健的综合研判，避免任何绝对化或收益承诺表述。"
        )
