"""彼得·林奇 - 成长投资：在日常生活中发现十倍股"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

LYNCH_PROMPT = """你是一位以彼得·林奇投资哲学为指导的AI投资分析师。

【核心原则】
1. 生活发现法：在日常生活中观察哪些公司的产品或服务越来越受欢迎
2. 六类公司分类法：缓慢增长型/稳定增长型/快速增长型/周期型/困境反转型/隐蔽资产型
3. PEG为王：市盈率/增长率<1是理想买入点
4. 人弃我取：关注被基金忽视的小公司、冷门行业

【分析框架】
- 增长类型识别（20%）：确定公司属于哪一类型，不同类型用不同估值方法
- PEG比率（30%）：PE/净利润增速<1为好，<0.5为极好
- 业务简单性（15%）：业务模式容易理解、产品贴近日常生活
- 机构关注度（15%）：机构持股比例低、分析师覆盖少
- 现金流（20%）：自由现金流充足、负债合理

【决策规则】
- ⭐ 强烈买入：快速增长型 + PEG<0.5 + 机构关注低
- 📈 买入：PEG<1 + 业务模式清晰 + 有增长空间
- ⚠️ 观望：PEG>1.5或增长趋势不明朗
- ❌ 卖出：PEG>2或增长明显放缓或公司类型转变"""


class LynchPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        fundamental = factor_details.get("fundamental", {})
        valuation = factor_details.get("valuation", {})

        revenue_growth = fundamental.get("revenue_growth", 0)
        profit_growth = fundamental.get("profit_growth", 0)
        pe = valuation.get("pe", 20)

        peg = pe / max(profit_growth, 1) if profit_growth > 0 else 999
        if peg < 0.5:
            score = min(score + 20, 95)
        elif peg < 1:
            score = min(score + 10, 90)

        action = self._score_to_action(score, 0.5)
        confidence = min(score / 100, 0.8)

        factors = []
        if peg < 1:
            factors.append(f"PEG={peg:.2f}<1，估值与增长匹配")
        if revenue_growth > 15:
            factors.append(f"营收高增长({revenue_growth:.1f}%)")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"PEG分析：PE={pe} 增长率={profit_growth:.1f}% PEG={peg:.2f}，建议{action}",
            key_factors=factors,
            risk_warnings=["需确认增长可持续性"],
        )


lynch_config = PhilosophyConfig(
    agent_id="lynch",
    name="彼得·林奇 (十倍股)",
    archetype=Archetype.GROWTH,
    system_prompt=LYNCH_PROMPT,
    description="如同彼得·林奇：在日常生活中发现十倍股的足迹，用PEG筛选高成长公司",
    temperature=0.6,
    max_tokens=2000,
    weight_dimensions={"fundamental": 0.35, "technical": 0.10, "fund_flow": 0.15, "valuation": 0.25, "sentiment": 0.15},
    risk_tolerance=0.5,
    holding_horizon="long",
)

lynch_philosophy = LynchPhilosophy(lynch_config)
