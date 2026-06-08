"""巴菲特 - 价值投资：优秀公司合理价格"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

BUFFETT_PROMPT = """你是一位以沃伦·巴菲特投资哲学为指导的AI投资分析师。

【核心原则】
1. 护城河优先：寻找具有持久竞争优势的企业（品牌、专利、规模效应、转换成本）
2. 合理价格：好公司也需要好价格，但不要为平庸公司讨价还价
3. 能力圈：只投资你理解的企业，商业模式要简单明了
4. 长期持有：我们的持股期限是"永远"

【分析框架】
- 企业质量（40%）：ROE>15%、负债率低、现金流充裕、毛利率稳定
- 估值合理性（30%）：PE合理、PB合理、有安全边际
- 管理层质量（15%）：诚信、能力、股东导向
- 行业前景（15%）：稳定增长、非周期性、不易被颠覆

【决策规则】
- ⭐ 强烈买入：伟大公司 + 合理价格 + 安全边际充足
- 📈 关注：优秀公司但价格略高，等待回调
- ⚠️ 警惕：好行业但无明显竞争优势的公司
- ❌ 卖出：护城河被侵蚀或价格极度高估

请综合上述原则分析给定的股票数据，输出分析结论。"""


class BuffettPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        fundamental = factor_details.get("fundamental", {})
        valuation = factor_details.get("valuation", {})

        warnings = []
        if valuation.get("pe_score", 50) < 30:
            warnings.append("估值偏高，安全边际不足")
        if fundamental.get("roe", 0) < 10:
            warnings.append("ROE偏低，企业质量存疑")

        action = self._score_to_action(score, 0.6)
        confidence = min(score / 100, 0.9)

        factors = []
        if fundamental.get("roe", 0) > 15:
            factors.append("高ROE优质企业")
        if valuation.get("has_margin_of_safety"):
            factors.append("存在安全边际")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=self._generate_reasoning(score, fundamental, valuation, action),
            key_factors=factors,
            risk_warnings=warnings,
        )

    def _generate_reasoning(self, score, fundamental, valuation, action):
        parts = []
        roe = fundamental.get("roe", 0)
        pe = valuation.get("pe", 0)
        if roe > 15:
            parts.append(f"ROE={roe:.1f}%显示企业质量优秀")
        elif roe < 8:
            parts.append(f"ROE={roe:.1f}%偏低，需关注盈利能力")
        if pe and pe < 15:
            parts.append(f"PE={pe:.1f}处于历史低位，估值有吸引力")
        elif pe and pe > 30:
            parts.append(f"PE={pe:.1f}偏高，需确认成长性能否支撑")
        return "；".join(parts) if parts else f"综合评分{score:.1f}分，建议{action}"


buffett_config = PhilosophyConfig(
    agent_id="buffett",
    name="巴菲特 (价值投资)",
    archetype=Archetype.VALUE,
    system_prompt=BUFFETT_PROMPT,
    description="秉承沃伦·巴菲特的投资哲学：寻找具有持久护城河的优质企业，以合理价格买入并长期持有",
    temperature=0.5,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.40, "technical": 0.10, "fund_flow": 0.10, "valuation": 0.30, "sentiment": 0.10},
    risk_tolerance=0.6,
    holding_horizon="long",
)

buffett_philosophy = BuffettPhilosophy(buffett_config)
