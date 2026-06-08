"""动量交易 - 强者恒强"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

MOMENTUM_PROMPT = """你是一位动量交易流派的AI投资分析师。

【核心原则】
1. 强者恒强：过去表现好的股票未来一段时间继续表现好（动量效应）
2. 关注相对强度：选择相对于大盘表现最强的股票
3. 时间窗口关键：6-12个月的动量最有效，1个月以内存在反转效应
4. 严格止损：动量策略最大回撤控制在15%以内

【分析框架】
- 价格动量（35%）：过去6个月涨幅排名、创52周新高
- 相对强度（25%）：相对大盘的Alpha、行业排名
- 资金动量（25%）：主力资金持续流入、成交量放大
- 分析师动量（15%）：盈利预测上调、评级升级

【决策规则】
- ⭐ 强烈买入：价格新高 + 资金流入 + 盈利上调三重确认
- 📈 买入：动量强但尚未加速
- ⚠️ 观望：动量衰减或分歧加大
- ❌ 卖出：动量转负或跌破关键支撑"""


class MomentumPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        technical = factor_details.get("technical", {})
        fund_flow = factor_details.get("fund_flow", {})

        momentum_score = technical.get("momentum_score", 50)
        net_inflow = fund_flow.get("main_net_inflow", 0)

        if momentum_score > 70:
            score = min(score + 12, 95)
        if net_inflow > 0:
            score = min(score + 8, 90)

        action = self._score_to_action(score, 0.3)
        confidence = min(abs(score - 50) / 50, 0.8)

        factors = []
        if momentum_score > 65:
            factors.append("动量强劲")
        if net_inflow > 0:
            factors.append("主力资金净流入")

        warnings = []
        if momentum_score < 30:
            warnings.append("动量不足")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"动量分析：动量得分{momentum_score:.1f} 主力净流入{net_inflow:.0f}，建议{action}",
            key_factors=factors,
            risk_warnings=warnings,
        )


momentum_config = PhilosophyConfig(
    agent_id="momentum",
    name="动量派 (强者恒强)",
    archetype=Archetype.TECHNICAL,
    system_prompt=MOMENTUM_PROMPT,
    description="强者恒强：买入近期表现最强的股票，严格止损控制回撤",
    temperature=0.4,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.05, "technical": 0.45, "fund_flow": 0.30, "valuation": 0.05, "sentiment": 0.15},
    risk_tolerance=0.3,
    holding_horizon="short",
)

momentum_philosophy = MomentumPhilosophy(momentum_config)
