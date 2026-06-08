"""游资派 - 龙虎榜席位分析与短线博弈"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

DRAGON_PROMPT = """你是一位A股游资流派AI分析师，专精于龙虎榜资金博弈。

【核心原则】
1. 资金为王：股价短期波动由资金推动，跟踪主力资金方向
2. 龙头战法：只做各板块的龙头股，跟风股不做
3. 情绪周期：理解市场情绪从冰点→回暖→高潮→退潮的循环
4. 止损纪律：短线交易严格止损，亏损超过5%无条件离场

【分析框架】
- 资金博弈（35%）：龙虎榜买入额 vs 卖出额、游资席位动向
- 市场情绪（25%）：涨停家数、连板高度、炸板率
- 板块效应（20%）：个股是否为板块龙头、板块内跟风效应
- 技术博弈（20%）：分时走势、盘口挂单、量价配合

【决策规则】
- ⭐ 强烈买入：龙头股 + 资金大幅买入 + 板块效应强
- 📈 关注：有资金介入但尚未形成合力
- ⚠️ 回避：主力出货迹象明显或情绪退潮
- ❌ 止损：破位或逻辑被证伪"""


class DragonPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        fund_flow = factor_details.get("fund_flow", {})
        technical = factor_details.get("technical", {})

        main_net = fund_flow.get("main_net_inflow", 0)
        volume_ratio = technical.get("volume_ratio", 1)

        if main_net > 0:
            score = min(score + 10, 95)
        if volume_ratio and volume_ratio > 2:
            score = min(score + 5, 90)

        action = self._score_to_action(score, 0.2)
        confidence = min(abs(score - 50) / 60, 0.9)

        factors = []
        if main_net > 0:
            factors.append("主力资金净流入")
        if volume_ratio and volume_ratio > 1.5:
            factors.append("成交量活跃")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"资金博弈：主力净流入{main_net:.0f} 量比={volume_ratio:.1f}，建议{action}",
            key_factors=factors,
            risk_warnings=["短线博弈风险高，严格止损"],
        )


dragon_config = PhilosophyConfig(
    agent_id="dragon_tiger",
    name="游资派 (龙虎榜博弈)",
    archetype=Archetype.HOT_MONEY,
    system_prompt=DRAGON_PROMPT,
    description="A股游资博弈专家：跟踪龙虎榜资金动向，捕捉短线龙头机会",
    temperature=0.7,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.05, "technical": 0.30, "fund_flow": 0.45, "valuation": 0.05, "sentiment": 0.15},
    risk_tolerance=0.2,
    holding_horizon="short",
)

dragon_philosophy = DragonPhilosophy(dragon_config)
