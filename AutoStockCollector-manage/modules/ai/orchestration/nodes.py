import json
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Dict, List, Optional
from modules.ai.orchestration.state import TradingState, AnalystOutput, DebateEntry, RiskEntry
from modules.ai.foundation.llm_router import LLMRouter
from modules.ai.compression.compressor import Compressor
from utils.logger import get_logger

logger = get_logger(__name__)


def create_data_fetch_node():
    def data_fetch(state: TradingState) -> Dict[str, Any]:
        code = state.stock_code
        state.add_event("graph:node_start", {"node_id": "data_fetch", "name": "数据采集", "code": code})
        try:
            from api.routes.ai_advanced import _fetch_all_stock_data
            data = _fetch_all_stock_data(code)
            state.stock_data = data
            state.add_event("graph:node_stream", {"node_id": "data_fetch", "content": f"已采集 {len(data.get('kline_data', []))} 条K线"})
        except Exception as e:
            state.errors.append(f"data_fetch: {e}")
        state.add_event("graph:node_complete", {"node_id": "data_fetch"})
        return {"stock_data": state.stock_data}
    return data_fetch


def create_factor_calc_node():
    def factor_calc(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "factor_calc", "name": "因子计算"})
        try:
            from api.routes.ai_advanced import _calculate_debate_factors, _format_stock_data_text, _format_factor_text
            stock_text = _format_stock_data_text(state.stock_data)
            factors = _calculate_debate_factors(state.stock_data)
            factor_text = _format_factor_text(factors)
            state.factor_results = factors
            state.enriched_context = f"{stock_text}\n\n{factor_text}"
            state.add_event("graph:node_stream", {"node_id": "factor_calc", "content": f"综合评分: {factors.get('composite', 'N/A')}"})
        except Exception as e:
            state.errors.append(f"factor_calc: {e}")
        state.add_event("graph:node_complete", {"node_id": "factor_calc"})
        return {"factor_results": state.factor_results, "enriched_context": state.enriched_context}
    return factor_calc


def create_analyst_node(agent_id: str, agent_name: str, tier: str = "quick"):
    def analyst(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": f"analyst_{agent_id}", "name": agent_name})
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            agent_doc = db["ai_agents"].find_one({"id": agent_id})
            system_prompt = agent_doc["system_prompt"] if agent_doc else f"You are {agent_name}."

            prompt = f"""{system_prompt}

【数据】
{state.enriched_context[:8000]}

请基于以上数据给出专业分析。"""
            router = LLMRouter()
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            result = router.chat(compressed, use_cache=False, tier=tier, task_type=f"analyst_{agent_id}")

            content = result.raw if result.success else f"（{agent_name}分析暂不可用）"
            score = _extract_score(content)
            signal = _determine_signal(content)

            output = AnalystOutput(
                agent_id=agent_id, agent_name=agent_name,
                content=content, score=score, signal=signal,
            )
            state.add_event("graph:node_stream", {"node_id": f"analyst_{agent_id}", "content": content[:200]})
            state.analyst_outputs[agent_id] = output
        except Exception as e:
            logger.error(f"Analyst {agent_id} failed: {e}")
            state.errors.append(f"analyst_{agent_id}: {e}")
            state.analyst_outputs[agent_id] = AnalystOutput(agent_id=agent_id, agent_name=agent_name, content=f"分析失败: {e}")

        state.add_event("graph:node_complete", {"node_id": f"analyst_{agent_id}"})
        return {"analyst_outputs": {agent_id: state.analyst_outputs[agent_id]}}
    return analyst


def create_bull_node():
    def bull_analyst(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "bull_analyst", "name": "多头分析师"})
        try:
            analyst_contexts = []
            for aid, out in state.analyst_outputs.items():
                analyst_contexts.append(f"【{out.agent_name}】\n{out.content[:1500]}")
            base_context = "\n\n".join(analyst_contexts)

            prompt = f"""你是一位坚定的多头分析师。你的使命是从数据中找出一切支持看涨的理由。

【原始数据】
{state.enriched_context[:6000]}

【基础分析师观点】
{base_context}

请综合以上信息，从多头视角进行全面辩论。
最后必须给出一行：综合评分：XX/100（0=完全不看涨，100=极度看涨）"""
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            router = LLMRouter()
            result = router.chat(compressed, use_cache=False, tier="quick", task_type="debate_bull")
            content = result.raw if result.success else ""
            score = _extract_score(content) or 50
            state.bull_analysis = content
            state.bull_score = score
            state.add_event("graph:node_stream", {"node_id": "bull_analyst", "content": content[:200]})
        except Exception as e:
            logger.error(f"Bull analyst failed: {e}")
            state.errors.append(f"bull: {e}")
        state.add_event("graph:node_complete", {"node_id": "bull_analyst"})
        return {"bull_analysis": state.bull_analysis, "bull_score": state.bull_score}
    return bull_analyst


def create_bear_node():
    def bear_analyst(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "bear_analyst", "name": "空头分析师"})
        try:
            analyst_contexts = []
            for aid, out in state.analyst_outputs.items():
                analyst_contexts.append(f"【{out.agent_name}】\n{out.content[:1500]}")
            base_context = "\n\n".join(analyst_contexts)

            prompt = f"""你是一位谨慎的空头分析师。你的使命是找出一切看跌信号和风险。

【原始数据】
{state.enriched_context[:6000]}

【基础分析师观点】
{base_context}

请综合以上信息，从空头视角进行全面辩论。
最后必须给出一行：综合评分：XX/100（0=完全不看跌，100=极度看跌）"""
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            router = LLMRouter()
            result = router.chat(compressed, use_cache=False, tier="quick", task_type="debate_bear")
            content = result.raw if result.success else ""
            score = _extract_score(content) or 50
            state.bear_analysis = content
            state.bear_score = score
            state.add_event("graph:node_stream", {"node_id": "bear_analyst", "content": content[:200]})
        except Exception as e:
            logger.error(f"Bear analyst failed: {e}")
            state.errors.append(f"bear: {e}")
        state.add_event("graph:node_complete", {"node_id": "bear_analyst"})
        return {"bear_analysis": state.bear_analysis, "bear_score": state.bear_score}
    return bear_analyst


def create_research_manager_node():
    def research_manager(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "research_manager", "name": "研究主管"})
        analyst_contexts = "\n".join(
            f"【{out.agent_name}】评分{out.score}: {out.content[:300]}"
            for out in state.analyst_outputs.values()
        )
        prompt = f"""综合以下所有分析师的报告，生成一份简洁的市场观点摘要。

{analyst_contexts}

多头评分: {state.bull_score}/100
空头评分: {state.bear_score}/100

请给出综合研判（看涨/看跌/中性）及核心理由。"""
        try:
            router = LLMRouter()
            result = router.chat(prompt, use_cache=False, tier="deep", task_type="research_manager")
            state.research_summary = result.raw if result.success else "综合研判暂不可用"
            state.add_event("graph:node_stream", {"node_id": "research_manager", "content": state.research_summary[:200]})
        except Exception as e:
            logger.error(f"Research manager failed: {e}")
            state.research_summary = "研判失败"
        state.add_event("graph:node_complete", {"node_id": "research_manager"})
        return {"research_summary": state.research_summary}
    return research_manager


def create_trader_node():
    def trader(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "trader", "name": "交易员"})
        prompt = f"""基于以下分析，生成交易决策。

研究摘要: {state.research_summary[:2000]}
多头评分: {state.bull_score}/100
空头评分: {state.bear_score}/100

请确定: 方向(买入/卖出/持有), 仓位比例(0-100%), 置信度(0-100%)。"""
        try:
            router = LLMRouter()
            result = router.chat(prompt, use_cache=False, tier="routing", task_type="trader")
            content = result.raw if result.success else "hold"
            state.trader_decision = content
            state.trader_confidence = 0.5
            for kw, conf in [("买入", 0.8), ("卖出", 0.7), ("持有", 0.5)]:
                if kw in content and conf > state.trader_confidence:
                    state.trader_confidence = conf
            state.add_event("graph:node_stream", {"node_id": "trader", "content": content[:200]})
        except Exception as e:
            logger.error(f"Trader failed: {e}")
            state.trader_decision = "hold"
        state.add_event("graph:node_complete", {"node_id": "trader"})
        return {"trader_decision": state.trader_decision, "trader_confidence": state.trader_confidence}
    return trader


def create_risk_debater_node(debater_id: str, debater_name: str, stance: str):
    def risk_debater(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": f"risk_{debater_id}", "name": debater_name})
        prompt = f"""你是一位{debater_name}。你的任务是评估以下交易决策的风险。

交易决策: {state.trader_decision[:1000]}
研究摘要: {state.research_summary[:2000]}

请从{stance}视角给出风险评估（0-100分）和具体理由。"""
        try:
            router = LLMRouter()
            result = router.chat(prompt, use_cache=False, tier="quick", task_type=f"risk_{debater_id}")
            content = result.raw if result.success else ""
            score = _extract_score(content) or 50
            entry = RiskEntry(agent_id=debater_id, stance=stance, argument=content, risk_score=score)
            state.risk_assessments[debater_id] = content
            state.risk_discuss_history.append(entry)
            state.add_event("graph:node_stream", {"node_id": f"risk_{debater_id}", "content": content[:200]})
        except Exception as e:
            logger.error(f"Risk debater {debater_id} failed: {e}")
        state.add_event("graph:node_complete", {"node_id": f"risk_{debater_id}"})
        return {"risk_assessments": {debater_id: state.risk_assessments.get(debater_id, "")}}
    return risk_debater


def create_portfolio_manager_node():
    def portfolio_manager(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": "portfolio_manager", "name": "投资组合经理"})
        risk_context = "\n".join(
            f"【{e.agent_id}】{e.stance}视角: {e.argument[:300]}"
            for e in state.risk_discuss_history
        )
        prompt = f"""你是投资组合经理。请综合所有信息做出最终决策。

研究摘要: {state.research_summary[:1500]}
交易员建议: {state.trader_decision[:1000]}
交易员置信度: {state.trader_confidence:.0%}

风险评估:
{risk_context}

请给出最终决策: 方向(买入/卖出/持有)、仓位(0-100%)、止损位、止盈位。"""
        try:
            router = LLMRouter()
            result = router.chat(prompt, use_cache=False, tier="deep", task_type="portfolio_manager")
            decision_text = result.raw if result.success else "观望"
            state.final_decision = {
                "decision": decision_text,
                "bull_score": state.bull_score,
                "bear_score": state.bear_score,
                "confidence": state.trader_confidence,
                "timestamp": beijing_now().isoformat(),
            }
            state.add_event("graph:node_stream", {"node_id": "portfolio_manager", "content": decision_text[:300]})
        except Exception as e:
            logger.error(f"Portfolio manager failed: {e}")
            state.final_decision = {"decision": "error", "error": str(e)}
        state.add_event("graph:node_complete", {"node_id": "portfolio_manager"})
        return {"final_decision": state.final_decision}
    return portfolio_manager


def _extract_score(text: str) -> Optional[float]:
    import re
    tail = text[-600:] if len(text) > 600 else text
    patterns = [
        r'综合评分[：:]\s*(\d+(?:\.\d+)?)\s*(?:/\s*100)?',
        r'(?:综合)?信心[指度][数标]?[：:]\s*(\d+(?:\.\d+)?)',
        r'评分[：:]\s*(\d+(?:\.\d+)?)',
    ]
    for pat in patterns:
        matches = list(re.finditer(pat, tail))
        if matches:
            val = float(matches[-1].group(1))
            if 0 <= val <= 100:
                return val
    return None


def _determine_signal(text: str) -> str:
    bullish_kw = ["买入", "看涨", "上涨", "多头", "推荐", "增持", "金叉"]
    bearish_kw = ["卖出", "看跌", "下跌", "空头", "回避", "减持", "死叉"]
    pos = sum(1 for kw in bullish_kw if kw in text)
    neg = sum(1 for kw in bearish_kw if kw in text)
    if pos > neg:
        return "bullish"
    elif neg > pos:
        return "bearish"
    return "neutral"
