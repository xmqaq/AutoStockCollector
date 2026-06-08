"""投资哲学注册表 - 集中管理所有 Agent 注册与发现"""
from typing import Any, Dict, List, Optional
from modules.ai.philosophies.base import (
    Archetype, InvestmentPhilosophy, PhilosophyConfig,
)


class PhilosophyRegistry:
    """投资哲学注册表 - 管理所有投资哲学 Agent 的注册与查询"""

    _philosophies: Dict[str, InvestmentPhilosophy] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, philosophy: InvestmentPhilosophy):
        cls._philosophies[philosophy.agent_id] = philosophy

    @classmethod
    def get(cls, agent_id: str) -> Optional[InvestmentPhilosophy]:
        return cls._philosophies.get(agent_id)

    @classmethod
    def get_all(cls) -> List[InvestmentPhilosophy]:
        return list(cls._philosophies.values())

    @classmethod
    def get_by_archetype(cls, archetype: Archetype) -> List[InvestmentPhilosophy]:
        return [
            p for p in cls._philosophies.values()
            if p.config.archetype == archetype
        ]

    @classmethod
    def get_by_archetype_value(cls, archetype: str) -> List[InvestmentPhilosophy]:
        try:
            at = Archetype(archetype)
            return cls.get_by_archetype(at)
        except ValueError:
            return []

    @classmethod
    def get_ids(cls) -> List[str]:
        return list(cls._philosophies.keys())

    @classmethod
    def get_all_registry_entries(cls) -> List[Dict[str, Any]]:
        return [p.to_registry_entry() for p in cls._philosophies.values()]

    @classmethod
    def init_default(cls):
        """注册默认的所有投资哲学 Agent"""
        if cls._initialized:
            return
        cls._register_value_agents()
        cls._register_growth_agents()
        cls._register_technical_agents()
        cls._register_macro_agent()
        cls._register_quant_agent()
        cls._register_hot_money_agent()
        cls._register_risk_agent()
        cls._register_sentiment_agent()
        cls._initialized = True

    @classmethod
    def _register_value_agents(cls):
        from modules.ai.philosophies.value.buffett import buffett_philosophy
        from modules.ai.philosophies.value.graham import graham_philosophy
        from modules.ai.philosophies.value.burry import burry_philosophy
        from modules.ai.philosophies.value.damodaran import damodaran_philosophy
        for p in [buffett_philosophy, graham_philosophy, burry_philosophy, damodaran_philosophy]:
            if p:
                cls.register(p)

    @classmethod
    def _register_growth_agents(cls):
        from modules.ai.philosophies.growth.fisher import fisher_philosophy
        from modules.ai.philosophies.growth.lynch import lynch_philosophy
        for p in [fisher_philosophy, lynch_philosophy]:
            if p:
                cls.register(p)

    @classmethod
    def _register_technical_agents(cls):
        from modules.ai.philosophies.technical.trend import trend_philosophy
        from modules.ai.philosophies.technical.momentum import momentum_philosophy
        for p in [trend_philosophy, momentum_philosophy]:
            if p:
                cls.register(p)

    @classmethod
    def _register_macro_agent(cls):
        from modules.ai.philosophies.macro.dalio import dalio_philosophy
        if dalio_philosophy:
            cls.register(dalio_philosophy)

    @classmethod
    def _register_quant_agent(cls):
        from modules.ai.philosophies.quant.simons import simons_philosophy
        if simons_philosophy:
            cls.register(simons_philosophy)

    @classmethod
    def _register_hot_money_agent(cls):
        from modules.ai.philosophies.hot_money.dragon import dragon_philosophy
        if dragon_philosophy:
            cls.register(dragon_philosophy)

    @classmethod
    def _register_risk_agent(cls):
        from modules.ai.philosophies.risk.risk_manager import risk_philosophy
        if risk_philosophy:
            cls.register(risk_philosophy)

    @classmethod
    def _register_sentiment_agent(cls):
        from modules.ai.philosophies.risk.sentiment import sentiment_philosophy
        if sentiment_philosophy:
            cls.register(sentiment_philosophy)
