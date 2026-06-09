from typing import Any, Dict
from modules.ai.orchestration.state import TradingState, DebateEntry


def extract_final_verdict(state: TradingState) -> Dict[str, Any]:
    bull_bullish = state.bull_score
    bear_bullish = 100 - state.bear_score
    net = (bull_bullish + bear_bullish) / 2

    if net >= 55:
        tendency = "偏多"
    elif net <= 45:
        tendency = "偏空"
    else:
        tendency = "中性震荡"

    risk_level = "中"
    all_text = str(state.risk_assessments)
    if "高风险" in all_text or "预警" in all_text:
        risk_level = "高"
    elif "低风险" in all_text:
        risk_level = "低"

    recommendation = "买入" if net >= 60 else ("回避" if net <= 40 else "观望")

    return {
        "code": state.stock_code,
        "bullScore": state.bull_score,
        "bearScore": state.bear_score,
        "tendency": tendency,
        "riskLevel": risk_level,
        "recommendation": recommendation,
        "bullArgument": state.bull_analysis[:800],
        "bearArgument": state.bear_analysis[:800],
        "judgeVerdict": state.research_summary[:800] or state.trader_decision[:800],
        "traderDecision": state.trader_decision[:500],
        "finalDecision": state.final_decision.get("decision", "")[:800],
        "analysts": {
            aid: out.to_dict() if hasattr(out, 'to_dict') else out
            for aid, out in state.analyst_outputs.items()
        },
        "generatedAt": state.final_decision.get("timestamp", ""),
    }
