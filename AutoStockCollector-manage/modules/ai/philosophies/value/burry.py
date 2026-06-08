"""迈克尔·巴里 - 深度价值/逆向投资"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

BURRY_PROMPT = """你是一位以迈克尔·巴里（《大空头》原型）投资哲学为指导的AI投资分析师。

【核心原则】
1. 深度逆向：在市场最不看好的地方寻找机会，敢于与主流观点对立
2. 深度价值：寻找被极度低估、被市场遗忘的"墙角"标的
3. 催化剂识别：找到能触发价值回归的事件（管理层变动、行业拐点等）
4. 耐心持有：价值回归可能需要时间，但一旦来临涨幅巨大

【分析框架】
- 低估程度（40%）：PE<10、PB<1、市值低于净资产
- 市场情绪（25%）：被主流研报忽视、机构持仓低、负面新闻多
- 催化剂（20%）：行业反转信号、管理层更换、资产重组
- 安全边际（15%）：即使最坏情况下也有资产兜底

【决策规则】
- ⭐ 强烈买入：极度低估 + 市场情绪极差 + 明确催化剂
- 📈 买入：低估但催化剂尚不明确，适合分批建仓
- ⚠️ 观望：估值合理或已充分反映利空
- ❌ 卖出：估值修复完成或基本面进一步恶化"""


class BurryPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        valuation = factor_details.get("valuation", {})
        pe = valuation.get("pe", 100)
        pb = valuation.get("pb", 10)

        if pe < 10:
            score = min(score + 15, 95)
        if pb < 1:
            score = min(score + 20, 95)

        action = self._score_to_action(score, 0.8)
        confidence = min(score / 100, 0.8)

        factors = []
        if pb and pb < 1:
            factors.append("破净标的，深度价值区间")
        if pe and pe < 10:
            factors.append("PE<10，极度低估")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"逆向价值分析：PE={pe} PB={pb}，市场关注度低，建议{action}",
            key_factors=factors,
            risk_warnings=["深度价值修复可能需要较长时间"],
        )


burry_config = PhilosophyConfig(
    agent_id="burry",
    name="迈克尔·巴里 (逆向价值)",
    archetype=Archetype.VALUE,
    system_prompt=BURRY_PROMPT,
    description="如同《大空头》原型迈克尔·巴里：在市场最不看好的角落寻找被极度低估的投资机会",
    temperature=0.6,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.20, "technical": 0.10, "fund_flow": 0.15, "valuation": 0.40, "sentiment": 0.15},
    risk_tolerance=0.8,
    holding_horizon="long",
)

burry_philosophy = BurryPhilosophy(burry_config)
