"""投资哲学基类"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


class Archetype(Enum):
    """投资流派"""
    VALUE = "value"                  # 价值投资
    GROWTH = "growth"                # 成长投资
    TECHNICAL = "technical"          # 技术分析
    MACRO = "macro"                  # 宏观驱动
    QUANT = "quant"                  # 量化策略
    HOT_MONEY = "hot_money"          # 游资策略
    RISK = "risk"                    # 风控
    SENTIMENT = "sentiment"          # 情绪分析


SignalAction = Literal[
    "strong_buy", "buy", "hold", "watch", "sell", "strong_sell"
]


@dataclass
class AgentSignal:
    """单个 Agent 的输出信号"""
    agent_id: str
    philosophy: str
    archetype: Archetype
    action: SignalAction
    confidence: float       # 0-1
    score: float            # 0-100
    reasoning: str
    key_factors: List[str] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "philosophy": self.philosophy,
            "archetype": self.archetype.value,
            "action": self.action,
            "confidence": self.confidence,
            "score": self.score,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "risk_warnings": self.risk_warnings,
        }


@dataclass
class PhilosophyConfig:
    """投资哲学配置"""
    agent_id: str
    name: str
    archetype: Archetype
    system_prompt: str
    description: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    weight_dimensions: Dict[str, float] = field(default_factory=lambda: {
        "fundamental": 0.25, "technical": 0.25,
        "fund_flow": 0.20, "valuation": 0.15, "sentiment": 0.15,
    })
    risk_tolerance: float = 0.5
    holding_horizon: str = "medium"


class InvestmentPhilosophy:
    """投资哲学 - 决定 Agent 如何解读因子和分析数据"""

    def __init__(self, config: PhilosophyConfig):
        self.config = config

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def system_prompt(self) -> str:
        return self.config.system_prompt

    def interpret_signal(
        self,
        factor_scores: Dict[str, float],
        factor_details: Dict[str, Any],
    ) -> AgentSignal:
        """根据投资哲学解读因子评分，生成交易信号"""
        raise NotImplementedError

    def get_weighted_score(self, factor_scores: Dict[str, float]) -> float:
        weights = self.config.weight_dimensions
        total = 0.0
        weight_sum = 0.0
        for dim, score in factor_scores.items():
            w = weights.get(dim, 0.1)
            total += score * w
            weight_sum += w
        return total / weight_sum if weight_sum > 0 else 50.0

    def _score_to_action(self, score: float, risk_tolerance: float) -> SignalAction:
        if score >= 80:
            return "strong_buy"
        elif score >= 65:
            return "buy"
        elif score >= 45:
            return "hold"
        elif score >= 30:
            return "watch"
        elif score >= 15:
            return "sell"
        else:
            return "strong_sell"

    def to_registry_entry(self) -> Dict:
        return {
            "agent_id": self.config.agent_id,
            "name": self.config.name,
            "archetype": self.config.archetype.value,
            "description": self.config.description,
            "system_prompt": self.config.system_prompt,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "risk_tolerance": self.config.risk_tolerance,
            "holding_horizon": self.config.holding_horizon,
            "weight_dimensions": self.config.weight_dimensions,
        }
