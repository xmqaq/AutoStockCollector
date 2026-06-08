"""格雷厄姆 - 价值投资：安全边际"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

GRAHAM_PROMPT = """你是一位以本杰明·格雷厄姆投资哲学为指导的AI投资分析师。

【核心原则】
1. 安全边际：永远以低于内在价值的价格买入，安全边际越大越好
2. 防御型投资：注重低估值、高股息、财务稳健的"烟蒂股"
3. 市场先生：利用市场波动而非被其左右，暴跌时买入，暴涨时卖出
4. 量化筛选：严格基于财务指标而非市场预期

【分析框架】
- 安全边际（40%）：价格远低于内在价值、PB<1.5、PE<历史均值
- 财务稳健性（30%）：流动比率>2、负债率<50%、连续20年分红
- 资产价值（20%）：每股净资产>股价*0.7、有形资产充足
- 防御性（10%）：低波动、行业稳定、非热门

【决策规则】
- ⭐ 强烈买入：价格低于内在价值2/3，安全边际>50%
- 📈 买入：价格低于内在价值，安全边际>30%
- ⚠️ 观望：价格接近内在价值，安全边际不足
- ❌ 卖出：价格超过内在价值50%以上，安全边际消失"""


class GrahamPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        valuation = factor_details.get("valuation", {})
        fundamental = factor_details.get("fundamental", {})

        pe = valuation.get("pe", 100)
        pb = valuation.get("pb", 10)
        debt_ratio = fundamental.get("debt_ratio", 50)

        warnings = []
        if pb > 1.5:
            warnings.append("PB>1.5，不符合格雷厄姆标准")
        if debt_ratio > 50:
            warnings.append("负债率偏高")

        pb_score = max(0, 100 - pb * 20) if pb > 0 else 50
        if pb <= 1.0:
            score = score * 0.7 + 30 * 0.3
        elif pb <= 1.5:
            score = score * 0.8 + 20 * 0.2

        action = self._score_to_action(score, 0.7)
        confidence = min(score / 100, 0.85)

        factors = []
        if pb < 1.5:
            factors.append("低PB符合格雷厄姆标准")
        if pe and pe < 12:
            factors.append("PE处于深度价值区间")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"安全边际分析：PE={pe} PB={pb}，建议{action}",
            key_factors=factors,
            risk_warnings=warnings,
        )


graham_config = PhilosophyConfig(
    agent_id="graham",
    name="格雷厄姆 (安全边际)",
    archetype=Archetype.VALUE,
    system_prompt=GRAHAM_PROMPT,
    description="遵循本杰明·格雷厄姆的防御型价值投资：极度重视安全边际和财务稳健性",
    temperature=0.4,
    max_tokens=1800,
    weight_dimensions={"fundamental": 0.35, "technical": 0.05, "fund_flow": 0.10, "valuation": 0.45, "sentiment": 0.05},
    risk_tolerance=0.7,
    holding_horizon="long",
)

graham_philosophy = GrahamPhilosophy(graham_config)
