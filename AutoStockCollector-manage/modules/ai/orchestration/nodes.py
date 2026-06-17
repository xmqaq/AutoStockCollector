import json
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Dict, List, Optional
from modules.ai.orchestration.state import TradingState, AnalystOutput, DebateEntry, RiskEntry
from modules.ai.foundation.llm_router import LLMRouter
from modules.ai.compression.compressor import Compressor
from utils.logger import get_logger

logger = get_logger(__name__)


def _build_holding_context(user_id: str, code: str) -> str:
    """持仓 + 现金上下文：让交易员/组合经理知道你当前仓位与可用资金，给出加/减/清仓建议。"""
    try:
        from modules.paper_trading.trade_engine import TradeEngine
        from modules.paper_trading.account import PaperAccount

        engine = TradeEngine()
        account = PaperAccount()
        positions, _ = engine.get_positions(user_id)
        acc = account.get(user_id)
        cash = acc.get("cash_balance") if acc else None
        total_mv = sum(p.get("market_value", 0) for p in positions)
        net = (cash or 0) + total_mv

        lines = ["【账户与持仓】"]
        if cash is not None:
            lines.append(f"可用现金：{cash:.2f} 元，账户净值：{net:.2f} 元")
        else:
            lines.append("账户未初始化（无资金上下文）")
        pos = next((p for p in positions if p.get("code") == code), None)
        if pos:
            ratio = (pos.get("market_value", 0) / net * 100) if net > 0 else 0
            lines.append(
                f"当前已持有 {code}：{pos.get('shares')}股，成本{pos.get('avg_cost')}，"
                f"现价{pos.get('current_price')}，浮动盈亏{pos.get('pnl_percent', 0):+.2f}%，"
                f"占净值{ratio:.1f}%"
            )
        else:
            lines.append(f"当前未持有 {code}（如建议买入属新建仓）")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Holding context build failed for {code}: {e}")
        return ""


def _build_reflection_context(code: str) -> str:
    """复用 ReflectionInjector：把该股上次决策的实现收益/对错注入，形成闭环学习。"""
    try:
        from modules.ai.reflection.injector import ReflectionInjector
        return ReflectionInjector().inject("", code).strip()
    except Exception as e:
        logger.warning(f"Reflection context build failed for {code}: {e}")
        return ""


def _plan_and_fetch_tools(router, agent_name: str, state: "TradingState") -> str:
    """有界 ReAct：让分析师按菜单选 0-3 个数据工具，执行后回灌为补充上下文。

    规划用最便宜的 routing 档；任何异常都降级为无补充，绝不影响主分析。
    """
    try:
        from modules.ai.orchestration.tools import tools_menu, run_tools
        plan_prompt = (
            f"你是{agent_name}。在正式分析前，可按需调用以下数据工具补充信息：\n"
            f"{tools_menu()}\n\n"
            f"已有数据摘要（节选）：\n{state.enriched_context[:1200]}\n\n"
            f"请判断还需要哪些工具（最多3个，不需要则返回空数组）。"
        )
        schema = {"tools": "需要调用的工具名数组(从菜单里选,0-3个)",
                  "reason": "为什么需要(一句话)"}
        plan = router.chat(plan_prompt, schema=schema, use_cache=False,
                           tier="routing", task_type="analyst_tool_plan")
        if not (plan.success and plan.data):
            return ""
        names = plan.data.get("tools") or []
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, list) or not names:
            return ""
        return run_tools(names, state.stock_code, limit=3)
    except Exception as e:
        logger.warning(f"tool planning failed: {e}")
        return ""


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
            base_context = f"{stock_text}\n\n{factor_text}"

            holding_ctx = _build_holding_context(state.user_id, state.stock_code)
            reflection_ctx = _build_reflection_context(state.stock_code)
            state.holding_context = holding_ctx
            state.reflection_context = reflection_ctx
            prefix = "\n\n".join(x for x in (holding_ctx, reflection_ctx) if x)
            state.enriched_context = f"{prefix}\n\n{base_context}" if prefix else base_context
            state.add_event("graph:node_stream", {"node_id": "factor_calc", "content": f"综合评分: {factors.get('composite', 'N/A')}"})
        except Exception as e:
            state.errors.append(f"factor_calc: {e}")
        state.add_event("graph:node_complete", {"node_id": "factor_calc"})
        return {"factor_results": state.factor_results, "enriched_context": state.enriched_context}
    return factor_calc


def create_analyst_node(agent_id: str, agent_name: str, tier: str = "quick",
                        use_tools: bool = True):
    def analyst(state: TradingState) -> Dict[str, Any]:
        state.add_event("graph:node_start", {"node_id": f"analyst_{agent_id}", "name": agent_name})
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            agent_doc = db["ai_agents"].find_one({"id": agent_id})
            system_prompt = agent_doc["system_prompt"] if agent_doc else f"You are {agent_name}."

            router = LLMRouter()
            # ── 有界 ReAct：计划→取数 ──
            extra_ctx = _plan_and_fetch_tools(
                router, agent_name, state) if use_tools else ""
            if extra_ctx:
                state.add_event("graph:node_stream", {
                    "node_id": f"analyst_{agent_id}",
                    "content": f"已补充数据：{extra_ctx[:120]}",
                })

            prompt = f"""{system_prompt}

【数据】
{state.enriched_context[:8000]}
{extra_ctx}

请基于以上数据给出专业分析。"""
            schema = {
                "score": "0-100 的整数评分(越高越看好)",
                "signal": "bullish/bearish/neutral 三选一",
                "summary": "一句话核心结论",
                "analysis": "详细分析，200-400字",
            }
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            result = router.chat(compressed, schema=schema, use_cache=False,
                                 tier=tier, task_type=f"analyst_{agent_id}")

            if result.success and result.data:
                d = result.data
                content = str(d.get("analysis") or d.get("summary") or "").strip()
                score = _coerce_score(d.get("score"))
                if score is None:
                    score = _extract_score(content)
                sig = d.get("signal")
                signal = sig if sig in ("bullish", "bearish", "neutral") else _determine_signal(content)
            else:
                content = result.raw if result.success else f"（{agent_name}分析暂不可用）"
                score = _extract_score(content)
                signal = _determine_signal(content)
            if not content:
                content = f"（{agent_name}分析暂不可用）"
            score = score if score is not None else 50.0

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

            round_tag = f"（第 {state.debate_round} 轮）" if state.debate_round else ""
            rebuttal = ""
            if state.debate_round > 1 and state.bear_analysis:
                rebuttal = f"\n\n【空头上一轮观点（请逐条反驳）】\n{state.bear_analysis[:1500]}"
            prompt = f"""你是一位坚定的多头分析师{round_tag}。你的使命是从数据中找出一切支持看涨的理由。

【原始数据】
{state.enriched_context[:6000]}

【基础分析师观点】
{base_context}{rebuttal}

请综合以上信息，从多头视角进行全面辩论{'，并针对空头上一轮观点逐条反驳' if rebuttal else ''}，
并给出 0-100 的看涨强度评分（0=完全不看涨，100=极度看涨）。"""
            schema = {"score": "0-100 看涨强度整数", "argument": "多头论证全文"}
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            router = LLMRouter()
            result = router.chat(compressed, schema=schema, use_cache=False, tier="quick", task_type="debate_bull")
            if result.success and result.data:
                content = str(result.data.get("argument") or "").strip()
                score = _coerce_score(result.data.get("score"))
            else:
                content = result.raw if result.success else ""
                score = None
            if not content:
                content = result.raw if result.success else ""
            if score is None:
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

            round_tag = f"（第 {state.debate_round} 轮）" if state.debate_round else ""
            rebuttal = ""
            if state.bull_analysis:
                rebuttal = f"\n\n【多头本轮观点（请逐条反驳）】\n{state.bull_analysis[:1500]}"
            prompt = f"""你是一位谨慎的空头分析师{round_tag}。你的使命是找出一切看跌信号和风险。

【原始数据】
{state.enriched_context[:6000]}

【基础分析师观点】
{base_context}{rebuttal}

请综合以上信息，从空头视角进行全面辩论{'，并针对多头本轮观点逐条反驳' if rebuttal else ''}，
并给出 0-100 的看跌强度评分（0=完全不看跌，100=极度看跌）。"""
            schema = {"score": "0-100 看跌强度整数", "argument": "空头论证全文"}
            compressor = Compressor(max_tokens=64000)
            compressed = compressor.compress(prompt)
            router = LLMRouter()
            result = router.chat(compressed, schema=schema, use_cache=False, tier="quick", task_type="debate_bear")
            if result.success and result.data:
                content = str(result.data.get("argument") or "").strip()
                score = _coerce_score(result.data.get("score"))
            else:
                content = result.raw if result.success else ""
                score = None
            if not content:
                content = result.raw if result.success else ""
            if score is None:
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
        holding_block = f"\n{state.holding_context}\n" if state.holding_context else ""
        prompt = f"""基于以下分析，生成交易决策。

研究摘要: {state.research_summary[:2000]}
多头评分: {state.bull_score}/100
空头评分: {state.bear_score}/100
{holding_block}
请确定: 方向(买入/卖出/持有), 仓位比例(0-100%), 置信度(0-100%)。
若已持有该股，请结合现有仓位与可用现金给出加仓/减仓/清仓的具体方向；若未持有，则按新建仓考虑。"""
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
        holding_block = f"\n{state.holding_context}\n" if state.holding_context else ""
        prompt = f"""你是投资组合经理。请综合所有信息做出最终决策。

研究摘要: {state.research_summary[:1500]}
交易员建议: {state.trader_decision[:1000]}
交易员置信度: {state.trader_confidence:.0%}
{holding_block}
风险评估:
{risk_context}

请给出最终决策: 方向(买入/卖出/持有)、仓位(0-100%)、止损位、止盈位。
结合当前持仓与可用现金，给出可执行的加/减/清仓建议（避免超出现金或满仓追高）。"""
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


def _coerce_score(val) -> Optional[float]:
    """把结构化输出里的 score 字段稳健转成 0-100 浮点，越界/非数返回 None。"""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if 0 <= f <= 100 else None


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
