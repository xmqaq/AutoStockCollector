"""投资哲学层 - 多智能体投资哲学模拟"""
from modules.ai.philosophies.base import (
    Archetype, AgentSignal, InvestmentPhilosophy, PhilosophyConfig,
)
from modules.ai.philosophies.registry import PhilosophyRegistry

__all__ = [
    "Archetype", "AgentSignal", "InvestmentPhilosophy", "PhilosophyConfig",
    "PhilosophyRegistry",
]
