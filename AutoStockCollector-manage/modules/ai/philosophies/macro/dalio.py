"""达利欧 - 宏观驱动：经济机器模型与风险平价"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

DALIO_PROMPT = """你是一位以瑞·达利欧投资哲学为指导的AI投资分析师。

【核心原则】
1. 经济机器模型：经济由交易构成，理解短期债务周期（5-8年）和长期债务周期（50-75年）
2. 风险平价：任何单一资产都存在风险，通过配置不相关资产实现风险平衡
3. 极度透明：基于数据和逻辑的决策，而非直觉
4. 可转债（Alpha）和被动（Beta）的区分：Beta是你的市场敞口，Alpha是你的超额收益

【分析框架】
- 宏观环境（35%）：当前所处经济周期位置、货币政策方向
- 行业周期（25%）：行业是处于扩张期还是收缩期
- 资本流向（20%）：资金在社会各领域的分配趋势
- 风险因子（20%）：通胀、利率、信用、流动性等因子暴露

【决策规则】
- ⭐ 强烈买入：宏观环境极度配合 + 行业向上周期 + 估值合理
- 📈 买入：宏观环境偏正面 + 行业景气度提升
- ⚠️ 观望：宏观环境不确定性高，等待信号明确
- ❌ 卖出：宏观环境恶化或行业周期见顶"""


class DalioPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        valuation = factor_details.get("valuation", {})
        fund_flow = factor_details.get("fund_flow", {})

        pe = valuation.get("pe", 20)
        total_flow = fund_flow.get("total_net_inflow", 0)

        action = self._score_to_action(score, 0.5)
        confidence = min(score / 100, 0.75)

        factors = []
        if total_flow and total_flow > 0:
            factors.append("资金整体流向积极")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"宏观分析：综合评分{score:.1f} PE={pe}，建议{action}",
            key_factors=factors,
            risk_warnings=["宏观分析需要结合更多全球宏观数据"],
        )


dalio_config = PhilosophyConfig(
    agent_id="dalio",
    name="达利欧 (宏观周期)",
    archetype=Archetype.MACRO,
    system_prompt=DALIO_PROMPT,
    description="如同瑞·达利欧：基于经济周期模型进行宏观驱动的投资决策与风险平价配置",
    temperature=0.5,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.15, "technical": 0.15, "fund_flow": 0.30, "valuation": 0.15, "sentiment": 0.25},
    risk_tolerance=0.5,
    holding_horizon="medium",
)

dalio_philosophy = DalioPhilosophy(dalio_config)
