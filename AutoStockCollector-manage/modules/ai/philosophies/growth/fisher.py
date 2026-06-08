"""费雪 - 成长投资：深入调研寻找优质成长股"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

FISHER_PROMPT = """你是一位以菲利普·费雪投资哲学为指导的AI投资分析师。

【核心原则】
1. 成长为王：寻找未来数年收入和利润能持续高速增长的公司
2. 闲聊法（Scuttlebutt）：通过多维度信息交叉验证公司实力
3. 研发驱动：重视企业的研发投入和技术壁垒
4. 持有优质成长股需要长期持有，不要轻易卖出

【分析框架】
- 收入增长（35%）：连续3年营收增速>15%、市场份额持续扩大
- 利润质量（25%）：毛利率稳定或提升、净利润增速>收入增速
- 研发壁垒（20%）：研发投入占比>5%、核心技术专利多
- 管理层（20%）：管理层持股比例高、战略清晰

【决策规则】
- ⭐ 强烈买入：高增长 + 高毛利 + 强研发 + 优秀管理
- 📈 买入：良好增长但需要确认可持续性
- ⚠️ 观望：增长放缓或竞争加剧
- ❌ 卖出：基本面恶化或增长逻辑被证伪"""


class FisherPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        fundamental = factor_details.get("fundamental", {})

        revenue_growth = fundamental.get("revenue_growth", 0)
        profit_growth = fundamental.get("profit_growth", 0)
        gross_margin = fundamental.get("gross_margin", 0)

        if revenue_growth > 20:
            score = min(score + 10, 95)
        if profit_growth > revenue_growth:
            score = min(score + 5, 95)

        action = self._score_to_action(score, 0.5)
        confidence = min(score / 100, 0.85)

        factors = []
        if revenue_growth > 15:
            factors.append(f"营收高增长({revenue_growth:.1f}%)")
        if gross_margin > 40:
            factors.append(f"毛利率优秀({gross_margin:.1f}%)")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"成长分析：营收增长{revenue_growth:.1f}% 毛利率{gross_margin:.1f}%，建议{action}",
            key_factors=factors,
            risk_warnings=["成长股波动较大，需关注估值匹配度"],
        )


fisher_config = PhilosophyConfig(
    agent_id="fisher",
    name="费雪 (成长投资)",
    archetype=Archetype.GROWTH,
    system_prompt=FISHER_PROMPT,
    description="如同菲利普·费雪：通过深入调研寻找能长期高成长的优质公司",
    temperature=0.6,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.45, "technical": 0.15, "fund_flow": 0.15, "valuation": 0.15, "sentiment": 0.10},
    risk_tolerance=0.5,
    holding_horizon="long",
)

fisher_philosophy = FisherPhilosophy(fisher_config)
