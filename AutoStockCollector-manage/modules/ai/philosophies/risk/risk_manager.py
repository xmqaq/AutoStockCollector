"""风控官 - 风险控制与仓位管理"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

RISK_PROMPT = """你是一位投资风控官AI，负责评估和控制投资风险。

【核心原则】
1. 保本第一：不亏钱是第一原则，任何交易都要先想好最坏情况
2. 分散风险：不要过度集中在单一标的，控制单票最大仓位
3. 止损纪律：预设止损点并严格执行，不让亏损扩大
4. 逆向风控：在市场最狂热时最危险，极度恐慌时反而是机会

【风控检查清单】
- 流动性风险（20%）：日均成交额是否充足、换手率是否合理
- 估值风险（20%）：PE/PB是否处于历史高位、是否存在泡沫
- 基本面风险（20%）：盈利能力是否稳定、负债是否可控
- 技术风险（20%）：是否处于高波动状态、是否破位
- 市场风险（20%）：大盘整体风险水平、系统性风险

【决策规则】
- ✅ 低风险：各维度风险可控，适合正常仓位
- ⚠️ 中等风险：某1-2个维度存在风险，需降低仓位
- 🚫 高风险：多个维度风险显著，建议回避
- 🔴 极端风险：系统性风险，建议清仓"""


class RiskPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        score = 100 - score  # 逆向：高分=高风险

        warnings = []
        risk_level = "低风险"

        if score > 60:
            risk_level = "中等风险"
            warnings.append("存在需要关注的风险因素")
        if score > 75:
            risk_level = "高风险"
            warnings.append("多个风险维度预警！")
        if score > 90:
            risk_level = "极端风险"
            warnings.append("极端风险警示！")

        action = "hold"
        if score < 30:
            action = "strong_buy"
        elif score < 50:
            action = "buy"
        elif score > 75:
            action = "sell"
        elif score > 60:
            action = "watch"

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(min(score / 100, 0.9), 2),
            score=round(100 - score, 1),
            reasoning=f"风控评估：风险等级={risk_level}，建议谨慎操作",
            key_factors=[f"风险等级：{risk_level}"],
            risk_warnings=warnings if warnings else ["无显著风险"],
        )


risk_config = PhilosophyConfig(
    agent_id="risk_manager",
    name="风控官 (风险评估)",
    archetype=Archetype.RISK,
    system_prompt=RISK_PROMPT,
    description="担任投资风控官：从流动性、估值、基本面等多维度评估和控制风险",
    temperature=0.3,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.25, "technical": 0.20, "fund_flow": 0.15, "valuation": 0.25, "sentiment": 0.15},
    risk_tolerance=0.1,
    holding_horizon="medium",
)

risk_philosophy = RiskPhilosophy(risk_config)
