"""融合选股自带的辩论/总结辅助函数。

原本复用 api.routes.strategy_pick 的三个私有函数，为解除融合模块对策略选股
路由的依赖（断奶），此处整体复制一份，函数名加 fusion_ 前缀。逻辑与
strategy_pick.py 的同名函数保持一致；后续两边各自演进互不影响。

依赖说明：内部所有重型依赖（factors / PhilosophyRegistry / LLMRouter 等）均为
函数内局部 import，本文件顶层仅需 typing 与 logger。
"""
from typing import Any, Dict, List

from utils.logger import get_logger

logger = get_logger(__name__)


def fusion_get_philosophy_signals(code: str, bundle) -> tuple:
    """运行所有投资哲学 Agent 对单只股票生成信号，返回 (signals, dim_scores, flat_details, comp_details)。"""
    from modules.ai.foundation import factors
    closes_asc = list(reversed(bundle.closes))
    amounts_asc = list(reversed(bundle.volumes))

    fund_s, fund_d = factors.fundamental_score(
        roe=bundle.roe, revenue_growth=bundle.revenue_growth,
        profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
        debt_ratio=bundle.debt_ratio, industry=bundle.industry)
    tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
    flow_s, flow_d = factors.fund_flow_detail_score(
        main_net_inflow=bundle.main_net_inflow, total_amount=bundle.total_amount,
        turnover_rate=bundle.turnover_rate)
    val_s, val_d = factors.valuation_detail_score(pe=bundle.pe, pb=bundle.pb, industry=bundle.industry)

    dim_scores = {"fundamental": fund_s, "technical": tech_s, "fund_flow": flow_s, "valuation": val_s}

    raw_details = {"fundamental": fund_d, "technical": tech_d, "fund_flow": flow_d, "valuation": val_d}
    flat_details: Dict[str, Any] = {}
    for dim, detail in raw_details.items():
        flat: Dict[str, Any] = {"data_available": detail.get("data_available", True), "score": dim_scores[dim]}
        for key, val in detail.items():
            if key == "data_available": continue
            if isinstance(val, dict) and "value" in val:
                if val["value"] is not None: flat[key] = val["value"]
                if "score" in val: flat[f"{key}_score"] = val["score"]
            elif isinstance(val, dict) and "score" in val:
                flat[f"{key}_score"] = val["score"]
                if val.get("value") is not None: flat[key] = val["value"]
            else: flat[key] = val
        flat_details[dim] = flat

    from modules.ai.philosophies.registry import PhilosophyRegistry
    PhilosophyRegistry.init_default()
    signals = []
    for ph in PhilosophyRegistry.get_all():
        try:
            signal = ph.interpret_signal(dim_scores, flat_details)
            signals.append(signal.to_dict())
        except Exception as e:
            logger.warning(f"Philosophy {ph.agent_id} signal failed: {e}")

    comp, comp_details = factors.composite_score(
        {"fundamental": (fund_s, {}), "technical": (tech_s, {}),
         "fund_flow": (flow_s, {}), "valuation": (val_s, {})},
        factors.DEFAULT_WEIGHTS)

    dim_scores_flat = {**dim_scores, "composite": comp}
    return signals, dim_scores_flat, flat_details, comp_details


def fusion_build_debate_consensus(agent_signals: List[Dict]) -> Dict[str, Any]:
    """从多个 Agent 信号构建共识结果。"""
    if not agent_signals:
        return {"tendency": 0, "consensus_level": 0, "confidence": 0,
                "positive_count": 0, "negative_count": 0, "neutral_count": 0}

    scores = [s.get("score", 50) for s in agent_signals]
    actions = [s.get("action", "hold") for s in agent_signals]
    avg_score = sum(scores) / len(scores)
    tendency = round((avg_score - 50) / 50, 3)

    # 分歧度：score 的标准差 / 100
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
    divergence = (variance ** 0.5) / 100 if scores else 0
    consensus_level = round(max(0, min(1, 1 - divergence)), 2)
    confidence = round(0.5 + consensus_level * 0.3, 2)

    positive = sum(1 for a in actions if a in ("strong_buy", "buy"))
    negative = sum(1 for a in actions if a in ("strong_sell", "sell"))
    neutral = len(actions) - positive - negative

    return {
        "tendency": tendency,
        "consensus_level": consensus_level,
        "confidence": confidence,
        "high_conviction": divergence < 0.2,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "avg_score": round(avg_score, 1),
        "agent_count": len(agent_signals),
    }


def fusion_generate_debate_summary(all_debates: List[Dict], picks: List[Dict]) -> str:
    """对整体选股结果生成辩论摘要。"""
    try:
        from modules.ai.foundation.llm_router import LLMRouter
        from modules.ai.content_risk import sanitize_text
        router = LLMRouter()

        total = len(all_debates)
        if total == 0: return ""

        avg_consensus = sum(d.get("consensus", {}).get("consensus_level", 0.5) for d in all_debates) / total
        avg_tendency = sum(d.get("consensus", {}).get("tendency", 0) for d in all_debates) / total
        avg_confidence = sum(d.get("consensus", {}).get("confidence", 0.5) for d in all_debates) / total
        total_positive = sum(d.get("consensus", {}).get("positive_count", 0) for d in all_debates)
        total_negative = sum(d.get("consensus", {}).get("negative_count", 0) for d in all_debates)

        lines = []
        for i, p in enumerate(picks[:10], 1):
            sc = p.get("scores", {})
            debate = next((d for d in all_debates if d.get("code") == p.get("code")), None)
            consensus = debate.get("consensus", {}) if debate else {}
            signal_cnt = consensus.get("agent_count", 0)
            pos = consensus.get("positive_count", 0)
            neg = consensus.get("negative_count", 0)
            lines.append(
                f"{i}. {p.get('code','')} {p.get('name','')} "
                f"综合={p.get('composite',0):.0f} 基本面={sc.get('fundamental',0):.0f} "
                f"技术面={sc.get('technical',0):.0f} 资金面={sc.get('fund_flow',0):.0f} "
                f"估值面={sc.get('valuation',0):.0f} 行业={p.get('industry','')} "
                f"辩论: {signal_cnt}位Agent|看多{pos}|看空{neg}"
            )

        prompt = (
            "你是一位专业的A股投资顾问。以下是多策略选股 + 多Agent深度分析 + 多投资哲学辩论后的股票列表"
            f"（共{len(picks)}只精选股票，{total}只经辩论，"
            f"整体共识度{avg_consensus*100:.0f}%，倾向度{avg_tendency:.2f}）：\n\n"
            + "\n".join(lines)
            + f"\n\n整体辩论统计：共识度{avg_consensus*100:.0f}%，信心{avg_confidence*100:.0f}%，"
              f"看多信号{total_positive}次，看空信号{total_negative}次。"
              f"{'市场整体偏乐观' if avg_tendency > 0.1 else '市场整体偏谨慎' if avg_tendency < -0.1 else '市场看法分歧'}。"
            + "\n\n请直接给出投资建议，严格遵守：\n"
            "1. 不要复述题目或股票列表，直接输出结论；\n"
            "2. 语言简洁，总字数控制在300字以内；\n"
            "3. 格式：\n\n"
            "**综合研判**\n一句话总结市场共识\n\n"
            "**优先关注**\n- 股票名：理由（含辩论共识度）\n\n"
            "**风险提示**\n- 需注意的风险点\n\n"
            "**配置建议**\n一句话仓位配置建议。"
        )
        result = router.chat(prompt, use_cache=False, task_type="stock_analysis")
        if result.success and result.data:
            raw = result.data.get("content", "") if isinstance(result.data, dict) else str(result.data)
            text, _ = sanitize_text(str(raw))
            return text.strip() or ""
    except Exception as e:
        logger.warning(f"Debate summary failed: {e}")
    return ""
