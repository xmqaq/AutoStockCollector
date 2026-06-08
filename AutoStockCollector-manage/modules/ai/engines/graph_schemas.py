"""图编排引擎 - 节点/边/信号定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Literal


class GraphNodeType(Enum):
    DATA = "data"
    FACTOR = "factor"
    AGENT = "agent"
    AGGREGATE = "aggregate"
    PORTFOLIO = "portfolio"
    SIGNAL = "signal"


@dataclass
class GraphNode:
    id: str
    type: GraphNodeType
    config: Dict[str, Any] = field(default_factory=dict)
    agent_philosophy: Optional[str] = None
    status: str = "pending"
    result: Any = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "config": self.config,
            "agent_philosophy": self.agent_philosophy,
            "status": self.status,
        }


@dataclass
class GraphEdge:
    source: str
    target: str

    def to_dict(self) -> Dict:
        return {"source": self.source, "target": self.target}


@dataclass
class ConsensusResult:
    """多 Agent 共识结果"""
    tendency: float  # -1 ~ 1, 负=偏空 正=偏多
    consensus_level: float  # 0-1, 越高越一致
    confidence: float  # 0-1
    high_conviction: bool
    agent_signals: List[Dict] = field(default_factory=list)
    bull_weight: float = 0.5
    bear_weight: float = 0.5


@dataclass
class PortfolioDecision:
    """投资组合决策"""
    action: Literal["strong_buy", "buy", "hold", "watch", "sell", "strong_sell"]
    position_size: str  # "full" / "half" / "quarter" / "none"
    reasoning: str
    risk_level: str  # "low" / "medium" / "high" / "extreme"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
