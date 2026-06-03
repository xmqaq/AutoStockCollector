"""个股深度分析引擎。编排 DAL → 多因子引擎 → LLMRouter → 内容风控 → 结构化结果。
依赖 dal/router 注入便于测试。LLM 失败降级为纯因子结果（source=factor）。
"""
from typing import Any, Dict, Optional

from modules.ai.foundation import factors
from modules.ai.content_risk import sanitize_text, RISK_DISCLAIMER


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

        # closes/volumes 在 bundle 中是倒序（新→旧），技术面需要正序
        closes_asc = list(reversed(bundle.closes))
        amounts_asc = list(reversed(bundle.volumes))

        # 各维度评分
        fund_s, fund_d = factors.fundamental_score(
            roe=bundle.roe,
            revenue_growth=bundle.revenue_growth,
            profit_growth=bundle.profit_growth,
            gross_margin=bundle.gross_margin,
            debt_ratio=bundle.debt_ratio,
            industry=bundle.industry,
        )
        tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
        flow_s, flow_d = factors.fund_flow_detail_score(
            main_net_inflow=bundle.main_net_inflow,
            total_amount=bundle.total_amount,
            turnover_rate=bundle.turnover_rate,
        )
        val_s, val_d = factors.valuation_detail_score(
            pe=bundle.pe,
            pb=bundle.pb,
            industry=bundle.industry,
        )

        dim_scores = {
            "fundamental": (fund_s, fund_d),
            "technical":   (tech_s, tech_d),
            "fund_flow":   (flow_s, flow_d),
            "valuation":   (val_s, val_d),
        }
        comp, comp_details = factors.composite_score(dim_scores, factors.DEFAULT_WEIGHTS)

        scores = {
            "fundamental": fund_s,
            "technical":   tech_s,
            "fund_flow":   flow_s,
            "valuation":   val_s,
            "composite":   comp,
        }

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
            "score_details": comp_details,
            "current_price": current_price,
            "llm": llm_payload,
            "source": source,
            "industry": bundle.industry,
            "disclaimer": RISK_DISCLAIMER,
        }

    def _build_prompt(self, bundle, scores: Dict[str, float]) -> str:
        current_price = bundle.realtime_price or (bundle.closes[0] if bundle.closes else "NA")
        pe_label = f"{bundle.pe:.1f}(TTM)" if bundle.pe else "N/A"
        pb_label = f"{bundle.pb:.2f}" if bundle.pb else "N/A"
        roe_label = f"{bundle.roe:.1f}%" if bundle.roe else "N/A"
        gm_label = f"{bundle.gross_margin:.1f}%" if bundle.gross_margin else "N/A"
        dr_label = f"{bundle.debt_ratio:.1f}%" if bundle.debt_ratio else "N/A"
        rg_label = f"{bundle.revenue_growth:+.1f}%" if bundle.revenue_growth else "N/A"
        pg_label = f"{bundle.profit_growth:+.1f}%" if bundle.profit_growth else "N/A"
        return (
            f"分析股票 {bundle.code}（{bundle.name}）的投资价值。\n"
            f"量化因子得分(0-100)：基本面={scores.get('fundamental', 'N/A')}，"
            f"技术面={scores.get('technical', 'N/A')}，"
            f"资金面={scores.get('fund_flow', 'N/A')}，"
            f"估值面={scores.get('valuation', 'N/A')}，"
            f"综合={scores.get('composite', 'N/A')}。\n"
            f"当前价={current_price}，TTM PE={pe_label}，PB={pb_label}。\n"
            f"基本面：ROE={roe_label}，毛利率={gm_label}，负债率={dr_label}，"
            f"营收同比={rg_label}，净利润同比={pg_label}。\n"
            f"请给出客观、稳健的综合研判，避免任何绝对化或收益承诺表述。"
        )
