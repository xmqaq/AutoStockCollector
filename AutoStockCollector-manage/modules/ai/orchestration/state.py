from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
import operator


class AnalystOutput:
    agent_id: str
    agent_name: str
    content: str
    score: float
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float

    def __init__(self, agent_id: str = "", agent_name: str = "", content: str = "",
                 score: float = 50.0, signal: str = "neutral", confidence: float = 0.5):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.content = content
        self.score = score
        self.signal = signal
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "content": self.content[:500],
            "score": self.score,
            "signal": self.signal,
            "confidence": self.confidence,
        }


class DebateEntry:
    round_number: int
    bull_argument: str
    bear_argument: str
    bull_score: float
    bear_score: float

    def __init__(self, round_number: int = 0, bull_argument: str = "",
                 bear_argument: str = "", bull_score: float = 0.0, bear_score: float = 0.0):
        self.round_number = round_number
        self.bull_argument = bull_argument
        self.bear_argument = bear_argument
        self.bull_score = bull_score
        self.bear_score = bear_score


class RiskEntry:
    agent_id: str
    stance: str
    argument: str
    risk_score: float

    def __init__(self, agent_id: str = "", stance: str = "neutral",
                 argument: str = "", risk_score: float = 0.0):
        self.agent_id = agent_id
        self.stance = stance
        self.argument = argument
        self.risk_score = risk_score


class TradingState:
    stock_code: str
    stock_data: Dict[str, Any]
    factor_results: Dict[str, Any]
    enriched_context: str

    analyst_outputs: Dict[str, AnalystOutput]
    debate_history: List[DebateEntry]
    debate_round: int
    max_debate_rounds: int

    bull_analysis: str
    bear_analysis: str
    bull_score: float
    bear_score: float

    research_summary: str
    trader_decision: str
    trader_confidence: float

    risk_discuss_history: List[RiskEntry]
    risk_round: int
    max_risk_rounds: int
    risk_assessments: Dict[str, str]

    final_decision: Dict[str, Any]
    errors: List[str]
    stream_events: List[Dict[str, Any]]

    def __init__(self, stock_code: str = ""):
        self.stock_code = stock_code
        self.stock_data = {}
        self.factor_results = {}
        self.enriched_context = ""
        self.analyst_outputs = {}
        self.debate_history = []
        self.debate_round = 0
        self.max_debate_rounds = 3
        self.bull_analysis = ""
        self.bear_analysis = ""
        self.bull_score = 50.0
        self.bear_score = 50.0
        self.research_summary = ""
        self.trader_decision = ""
        self.trader_confidence = 0.0
        self.risk_discuss_history = []
        self.risk_round = 0
        self.max_risk_rounds = 2
        self.risk_assessments = {}
        self.final_decision = {}
        self.errors = []
        self.stream_events = []

    def add_event(self, event_type: str, data: Dict[str, Any]):
        self.stream_events.append({"event": event_type, "data": data, "timestamp": datetime.now().isoformat()})
