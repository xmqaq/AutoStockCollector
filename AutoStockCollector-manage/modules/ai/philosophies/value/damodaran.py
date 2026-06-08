"""达摩达兰 - 估值驱动的价值投资"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

DAMODARAN_PROMPT = """你是一位以阿斯沃斯·达摩达兰（估值学院院长）投资哲学为指导的AI投资分析师。

【核心原则】
1. 估值是一切：任何资产都有内在价值，通过DCF/相对估值法可以计算
2. 增长≠价值：高增长公司也可能被高估，低增长公司也可能被低估
3. 风险定价：不同类型风险需要在估值中反映（股权风险溢价、国家风险等）
4. 情景分析：每个公司都有多种可能，通过概率加权计算合理价值区间

【分析框架】
- DCF估值（35%）：自由现金流折现，判断当前价格相对内在价值的偏离度
- 相对估值（25%）：PE/PB/PS/EV-EBITDA与同行业对比
- 增长质量（20%）：增长来自量价提升还是并购、ROIC>WACC
- 风险溢价（20%）：考虑行业风险、经营风险、财务风险

【决策规则】
- ⭐ 强烈买入：当前价格<内在价值*0.7，且DCF和相对估值均指向低估
- 📈 买入：价格<内在价值*0.85，至少两种估值方法指向低估
- ⚠️ 观望：价格在内在价值±15%范围内
- ❌ 卖出：价格>内在价值*1.3"""


class DamodaranPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        valuation = factor_details.get("valuation", {})
        fundamental = factor_details.get("fundamental", {})

        pe = valuation.get("pe", 20)
        pb = valuation.get("pb", 3)
        roe = fundamental.get("roe", 10)

        action = self._score_to_action(score, 0.5)
        confidence = min(score / 100, 0.85)

        factors = []
        if roe > 15 and pe and pe < 20:
            factors.append("高ROE低PE，可能被低估")
        if pb < 1.5:
            factors.append("PB偏低，有一定安全垫")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"估值分析：PE={pe} PB={pb} ROE={roe:.1f}%，建议{action}",
            key_factors=factors,
            risk_warnings=[],
        )


damodaran_config = PhilosophyConfig(
    agent_id="damodaran",
    name="达摩达兰 (估值分析)",
    archetype=Archetype.VALUE,
    system_prompt=DAMODARAN_PROMPT,
    description="遵循达摩达兰的估值框架：综合DCF与相对估值，计算内在价值与安全边际",
    temperature=0.5,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.20, "technical": 0.05, "fund_flow": 0.05, "valuation": 0.60, "sentiment": 0.10},
    risk_tolerance=0.5,
    holding_horizon="medium",
)

damodaran_philosophy = DamodaranPhilosophy(damodaran_config)
