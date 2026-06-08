"""趋势跟踪 - 顺势而为"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

TREND_PROMPT = """你是一位趋势跟踪交易流派的AI投资分析师。

【核心原则】
1. 趋势是朋友：不要试图猜测顶部和底部，顺势而为
2. 截断亏损，让利润奔跑：盈利时要持有，亏损时要果断止损
3. 趋势确认：需要多个时间框架确认趋势方向（日线+周线）
4. 不要抄底：下跌趋势中不买入，等待趋势反转确认

【分析框架】
- 趋势方向（40%）：均线多头排列（MA5>MA20>MA60）为上升趋势
- 趋势强度（25%）：ADX>25为强趋势，价格沿布林带上轨运行
- 成交量确认（20%）：上涨放量、下跌缩量
- 相对强度（15%）：个股 vs 大盘的相对强度为正

【决策规则】
- ⭐ 强烈买入：多头排列 + 放量突破 + 大盘配合
- 📈 买入：均线多头排列但尚未加速
- ⚠️ 观望：均线缠绕方向不明
- ❌ 卖出：均线死叉或跌破趋势线"""


class TrendPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        technical = factor_details.get("technical", {})

        ma_score = technical.get("ma_score", 50)
        macd_signal = technical.get("macd", "")

        if ma_score > 70:
            score = min(score + 10, 95)
        if macd_signal == "bullish":
            score = min(score + 8, 90)

        action = self._score_to_action(score, 0.4)
        confidence = min(abs(score - 50) / 50, 0.85)

        factors = []
        if ma_score > 60:
            factors.append("均线多头排列")
        if macd_signal == "bullish":
            factors.append("MACD金叉")

        warnings = []
        if ma_score < 40:
            warnings.append("均线空头排列，趋势偏弱")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"趋势分析：均线得分{ma_score:.1f} MACD={macd_signal}，建议{action}",
            key_factors=factors,
            risk_warnings=warnings,
        )


trend_config = PhilosophyConfig(
    agent_id="trend_follower",
    name="趋势跟踪派",
    archetype=Archetype.TECHNICAL,
    system_prompt=TREND_PROMPT,
    description="趋势是你的朋友：顺势而为，不预测顶部和底部，只在趋势确认后操作",
    temperature=0.4,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.05, "technical": 0.60, "fund_flow": 0.20, "valuation": 0.05, "sentiment": 0.10},
    risk_tolerance=0.4,
    holding_horizon="medium",
)

trend_philosophy = TrendPhilosophy(trend_config)
