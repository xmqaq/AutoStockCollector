"""西蒙斯 - 量化投资：基于统计套利和因子模型"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

SIMONS_PROMPT = """你是一位以吉姆·西蒙斯（文艺复兴科技）投资哲学为指导的AI投资分析师。

【核心原则】
1. 一切皆数据：市场行为可以用数学模型描述，寻找统计规律而非基本面故事
2. 多因子模型：收益来自多个因子的综合作用（价值/动量/质量/低波等）
3. 过拟合警惕：任何策略都需要足够的样本外验证
4. 高频不一定更好：中低频因子组合也能创造稳定Alpha

【分析框架】
- 多因子综合（35%）：多个因子的加权信号强度
- 因子拥挤度（20%）：多少个投资者在使用类似策略
- 统计显著性（25%）：因子的历史回测显著性（T值、IC值）
- 风险调整（20%）：夏普比率、最大回撤、收益稳定性

【决策规则】
- ⭐ 强烈买入：多因子信号强烈一致 + 低拥挤度 + 高夏普
- 📈 买入：因子信号偏正面，但一致性不足
- ⚠️ 观望：因子信号中性或拥挤度过高
- ❌ 卖出：因子信号恶化或策略容量不足"""


class SimonsPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)

        all_scores = [
            factor_details.get("fundamental", {}).get("score", 50),
            factor_details.get("technical", {}).get("score", 50),
            factor_details.get("fund_flow", {}).get("score", 50),
            factor_details.get("valuation", {}).get("score", 50),
        ]
        consistency = 1.0 - (max(all_scores) - min(all_scores)) / 100 if all_scores else 0.5

        if consistency > 0.7:
            score = min(score + 10, 95)
        elif consistency < 0.3:
            score = max(score - 10, 5)

        action = self._score_to_action(score, 0.4)
        confidence = round(consistency * 0.9, 2)

        factors = []
        if consistency > 0.6:
            factors.append("多因子信号一致性强")
        elif consistency < 0.3:
            factors.append("多因子信号分歧较大")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=confidence,
            score=round(score, 1),
            reasoning=f"量化分析：因子一致性={consistency:.2f} 综合评分{score:.1f}，建议{action}",
            key_factors=factors,
            risk_warnings=[],
        )


simons_config = PhilosophyConfig(
    agent_id="simons",
    name="西蒙斯 (量化模型)",
    archetype=Archetype.QUANT,
    system_prompt=SIMONS_PROMPT,
    description="如同吉姆·西蒙斯：基于多因子统计模型寻找市场规律，用数据而非故事做决策",
    temperature=0.3,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.25, "technical": 0.25, "fund_flow": 0.20, "valuation": 0.20, "sentiment": 0.10},
    risk_tolerance=0.4,
    holding_horizon="medium",
)

simons_philosophy = SimonsPhilosophy(simons_config)
