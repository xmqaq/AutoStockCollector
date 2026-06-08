"""年轮记忆系统数据模型"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    working_ttl_minutes: int = 30
    episodic_retention_days: int = 365
    pattern_analysis_interval_hours: int = 24
    max_conversation_history: int = 20


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    risk_level: Literal["conservative", "balanced", "aggressive"] = "balanced"
    preferred_industries: List[str] = field(default_factory=list)
    preferred_strategies: List[str] = field(default_factory=list)
    holding_horizon: Literal["short", "medium", "long"] = "medium"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "UserProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class HoldingRecord:
    """持仓记录"""
    user_id: str
    code: str
    stock_name: str
    buy_date: str
    buy_price: float
    shares: int
    sell_date: Optional[str] = None
    sell_price: Optional[float] = None
    pnl: Optional[float] = None
    reason: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "HoldingRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AnalysisHistory:
    """分析记录"""
    user_id: str
    code: str
    analysis_date: str
    analysis_type: str
    verdict: str
    recommendation: str
    user_feedback: Optional[Literal["agree", "disagree"]] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "AnalysisHistory":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class InvestmentPattern:
    """投资规律（长期知识库自动挖掘）"""
    user_id: str
    pattern_type: str
    description: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    discovered_at: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "InvestmentPattern":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionContext:
    """工作记忆 - 当前会话上下文"""
    user_id: str
    last_interaction: Optional[datetime] = None
    current_stock: Optional[str] = None
    conversation_history: List[Dict] = field(default_factory=list)
    pending_actions: List[str] = field(default_factory=list)


@dataclass
class MemoryStats:
    """记忆统计数据"""
    working_memory_active: bool = False
    holding_count: int = 0
    analysis_count: int = 0
    pattern_count: int = 0
    last_interaction: Optional[str] = None
    memory_usage_days: int = 0


@dataclass
class UserContext:
    """完整用户上下文 - 由 MemorySynthesizer 合成"""
    user_id: str = ""
    profile: Optional[UserProfile] = None
    current_holdings: Dict[str, Any] = field(default_factory=dict)
    recent_views: List[str] = field(default_factory=list)
    previous_analyses: List[Dict] = field(default_factory=list)
    patterns: List[InvestmentPattern] = field(default_factory=list)
    last_interaction: Optional[str] = None
    session_stock: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "profile": self.profile.to_dict() if self.profile else None,
            "current_holdings": self.current_holdings,
            "recent_views": self.recent_views,
            "previous_analyses": self.previous_analyses,
            "patterns": [p.to_dict() for p in self.patterns],
            "last_interaction": self.last_interaction,
            "session_stock": self.session_stock,
        }
