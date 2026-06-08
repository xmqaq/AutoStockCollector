"""舆情官 - 市场情绪与新闻舆情分析"""
from modules.ai.philosophies.base import (
    PhilosophyConfig, InvestmentPhilosophy, Archetype, AgentSignal,
)

SENTIMENT_PROMPT = """你是一位市场情绪分析师AI，专精于舆情解读和情绪量化。

【核心原则】
1. 情绪即短期驱动力：市场短期由情绪驱动而非理性，识别情绪转折点
2. 新闻的边际影响：关注超预期的新闻而非符合预期的
3. 媒体放大效应：媒体倾向于放大极端情绪（恐慌或贪婪）
4. 逆向指标：当所有人都看好时往往见顶，极度悲观时往往见底

【分析框架】
- 新闻情绪（30%）：近期新闻正面/负面比例、重要政策解读
- 社交媒体（25%）：股吧热度、讨论方向、散户情绪
- 资金情绪（25%）：融资融券余额变化、沪港通流向
- 恐慌/贪婪指数（20%）：波动率、看跌/看涨期权比等

【决策规则】
- ⭐ 极度恐慌：别人恐惧时我贪婪，逐步建仓机会
- 📈 偏乐观：情绪温和正面，但要注意是否过热
- ⚠️ 偏悲观：情绪偏负面，等待情绪修复
- ❌ 极度贪婪：别人贪婪时我恐惧，减仓或离场"""


class SentimentPhilosophy(InvestmentPhilosophy):
    def interpret_signal(self, factor_scores, factor_details):
        score = self.get_weighted_score(factor_scores)
        news_data = factor_details.get("sentiment_data", {})
        fund_flow = factor_details.get("fund_flow", {})

        news_sentiment = news_data.get("sentiment", 0) if isinstance(news_data, dict) else 0
        main_net = fund_flow.get("main_net_inflow", 0)

        fear_greed = 50
        if main_net and main_net > 0:
            fear_greed += min(main_net / 1e8 * 5, 20)
        elif main_net:
            fear_greed -= min(abs(main_net) / 1e8 * 5, 20)
        fear_greed = max(0, min(100, fear_greed))

        if fear_greed < 20:
            score = min(score + 20, 95)
        elif fear_greed > 80:
            score = max(score - 15, 10)

        action = self._score_to_action(score, 0.5)
        confidence = min(abs(score - 50) / 50, 0.75)

        factors = []
        if fear_greed < 20:
            factors.append("恐慌区间，逆向布局机会")
        elif fear_greed > 80:
            factors.append("贪婪区间，注意风险")

        return AgentSignal(
            agent_id=self.config.agent_id,
            philosophy=self.config.name,
            archetype=self.config.archetype,
            action=action,
            confidence=round(confidence, 2),
            score=round(score, 1),
            reasoning=f"情绪分析：恐慌贪婪指数={fear_greed:.0f} 新闻情绪={news_sentiment}，建议{action}",
            key_factors=factors,
            risk_warnings=["情绪指标是短期信号，需结合基本面"],
        )


sentiment_config = PhilosophyConfig(
    agent_id="sentiment_analyst",
    name="舆情官 (情绪分析)",
    archetype=Archetype.SENTIMENT,
    system_prompt=SENTIMENT_PROMPT,
    description="市场情绪分析师：解读新闻舆情、量化市场恐慌与贪婪程度",
    temperature=0.6,
    max_tokens=1500,
    weight_dimensions={"fundamental": 0.05, "technical": 0.15, "fund_flow": 0.25, "valuation": 0.10, "sentiment": 0.45},
    risk_tolerance=0.5,
    holding_horizon="short",
)

sentiment_philosophy = SentimentPhilosophy(sentiment_config)
