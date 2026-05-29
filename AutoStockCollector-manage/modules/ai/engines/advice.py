"""买卖参考建议引擎。复用 AnalysisEngine 结果 + 持仓上下文 → LLM 操作建议 → 风控。
LLM 失败时按综合分降级为规则建议。所有输出标注仅供参考。
"""
from typing import Any, Dict, Optional

from modules.ai.content_risk import sanitize_text, RISK_DISCLAIMER


class AdviceEngine:
    def __init__(self, analysis_engine=None, router=None):
        if analysis_engine is None:
            from modules.ai.engines.analysis import AnalysisEngine
            analysis_engine = AnalysisEngine()
        if router is None:
            from modules.ai.foundation.llm_router import LLMRouter
            router = LLMRouter()
        self.analysis_engine = analysis_engine
        self.router = router

    def advise(
        self,
        code: str,
        cost: Optional[float] = None,
        position: Optional[float] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        analysis = self.analysis_engine.analyze(code, use_cache=use_cache)
        composite = analysis.get("scores", {}).get("composite", 50.0)

        prompt = self._build_prompt(analysis, cost, position)
        schema = {"action": "str", "reason": "str", "buy_zone": "str", "stop_loss": "str", "position_advice": "str"}
        llm_result = self.router.chat(prompt, schema=schema, use_cache=use_cache, task_type="trade_advice")

        if llm_result.success and llm_result.data:
            d = llm_result.data
            advice = {
                "action": sanitize_text(str(d.get("action", "")))[0],
                "reason": sanitize_text(str(d.get("reason", "")))[0],
                "buy_zone": str(d.get("buy_zone", "")),
                "stop_loss": str(d.get("stop_loss", "")),
                "position_advice": sanitize_text(str(d.get("position_advice", "")))[0],
            }
            source = "llm"
        else:
            advice = self._rule_based_advice(composite, position)
            source = "rule"

        return {
            "code": analysis.get("code", code),
            "name": analysis.get("name", ""),
            "composite": composite,
            "current_price": analysis.get("current_price"),
            "advice": advice,
            "source": source,
            "disclaimer": RISK_DISCLAIMER,
        }

    def _build_prompt(self, analysis: Dict[str, Any], cost: Optional[float], position: Optional[float]) -> str:
        scores = analysis.get("scores", {})
        holding = "无持仓"
        if position is not None:
            holding = f"已持仓，仓位={position}，成本价={cost}"
        return (
            f"基于以下分析为股票 {analysis.get('code')}（{analysis.get('name')}）给出操作参考。\n"
            f"综合评分={scores.get('composite')}，技术面={scores.get('technical')}，当前价={analysis.get('current_price')}。\n"
            f"持仓情况：{holding}。\n"
            f"请给出客观稳健的操作参考（动作、理由、参考区间、止损、仓位建议），"
            f"避免任何绝对化或收益承诺表述。"
        )

    def _rule_based_advice(self, composite: float, position: Optional[float]) -> Dict[str, str]:
        held = position is not None and position > 0
        if composite >= 70:
            action = "持有" if held else "关注"
            reason = "综合评分较高，基本面与技术面相对占优。"
        elif composite >= 50:
            action = "持有" if held else "观望"
            reason = "综合评分中性，建议等待更明确信号。"
        else:
            action = "减仓" if held else "回避"
            reason = "综合评分偏低，下行风险相对较高。"
        return {
            "action": action,
            "reason": reason,
            "buy_zone": "",
            "stop_loss": "",
            "position_advice": "控制仓位，分批操作",
        }
