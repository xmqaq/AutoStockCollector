"""辩论系统数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal


@dataclass
class ResearchReport:
    """单个 Agent 的研究产出"""
    agent_id: str
    agent_name: str
    archetype: str
    data_sources: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    signal: Literal["bullish", "bearish", "neutral"] = "neutral"
    confidence: float = 0.5
    evidence: Dict[str, Any] = field(default_factory=dict)
    raw_analysis: str = ""

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "archetype": self.archetype,
            "data_sources": self.data_sources,
            "key_findings": self.key_findings,
            "signal": self.signal,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "raw_analysis": self.raw_analysis[:500] if self.raw_analysis else "",
        }


@dataclass
class DebateArgument:
    """辩论论点"""
    agent_id: str
    agent_name: str
    stance: Literal["bullish", "bearish"]
    argument: str
    evidence: List[str] = field(default_factory=list)
    rebuttal_target: Optional[str] = None  # 反驳对象的 agent_id


@dataclass
class DebateRound:
    """单轮辩论记录"""
    round_number: int
    arguments: List[DebateArgument] = field(default_factory=list)
    agent_persuasions: Dict[str, float] = field(default_factory=dict)  # 说服力评分
    consensus_shift: float = 0.0  # 本轮共识变化


@dataclass
class BattleResult:
    """辩论最终结果"""
    final_tendency: float
    consensus_level: float
    confidence: float
    winning_side: Literal["bullish", "bearish", "neutral"]
    key_insights: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    rounds: List[DebateRound] = field(default_factory=list)
