"""
选股工作流数据模型与存储
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import json
from core.storage.mongo_storage import MongoStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class NodeType(Enum):
    START = "start"
    END = "end"
    FILTER = "filter"
    SCORE = "score"
    AI_AGENT = "ai_agent"
    COMBINE = "combine"
    RISK_CONTROL = "risk_control"


class FilterType(Enum):
    PRICE_RANGE = "price_range"
    VOLUME_RATIO = "volume_ratio"
    PE_RANGE = "pe_range"
    PB_RANGE = "pb_range"
    TREND = "trend"
    FUND_FLOW = "fund_flow"
    SECTOR = "sector"
    MARKET_CAP = "market_cap"
    NEWS_SENTIMENT = "news_sentiment"


class ScoreType(Enum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    FUND_FLOW = "fund_flow"
    SENTIMENT = "sentiment"
    WEIGHTED = "weighted"


@dataclass
class WorkflowNode:
    id: str
    type: str
    label: str
    x: float
    y: float
    config: Dict[str, Any] = field(default_factory=dict)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowNode':
        return cls(
            id=data.get('id', ''),
            type=data.get('type', ''),
            label=data.get('label', ''),
            x=data.get('x', 0),
            y=data.get('y', 0),
            config=data.get('config', {}),
            inputs=data.get('inputs', []),
            outputs=data.get('outputs', [])
        )


@dataclass
class WorkflowEdge:
    id: str
    source: str
    target: str
    label: str = ""
    sourceHandle: str = ""
    targetHandle: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEdge':
        return cls(
            id=data.get('id', ''),
            source=data.get('source', ''),
            target=data.get('target', ''),
            label=data.get('label', ''),
            sourceHandle=data.get('sourceHandle', ''),
            targetHandle=data.get('targetHandle', '')
        )


@dataclass
class Workflow:
    id: str
    name: str
    description: str = ""
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    last_run_at: Optional[str] = None
    run_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_at": self.last_run_at,
            "run_count": self.run_count,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            nodes=[WorkflowNode.from_dict(n) for n in data.get('nodes', [])],
            edges=[WorkflowEdge.from_dict(e) for e in data.get('edges', [])],
            enabled=data.get('enabled', True),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            last_run_at=data.get('last_run_at'),
            run_count=data.get('run_count', 0),
            tags=data.get('tags', [])
        )


class WorkflowStorage(MongoStorage):
    def __init__(self):
        super().__init__("workflow")

    def save_workflow(self, workflow: Workflow) -> bool:
        workflow.updated_at = datetime.now().isoformat()
        if not workflow.created_at:
            workflow.created_at = workflow.updated_at
        return self.upsert_one({"id": workflow.id}, workflow.to_dict())

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        doc = self.find_one({"id": workflow_id})
        if doc:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            return Workflow.from_dict(doc)
        return None

    def list_workflows(self, enabled: Optional[bool] = None) -> List[Workflow]:
        filter_doc = {}
        if enabled is not None:
            filter_doc["enabled"] = enabled
        docs = self.find_many(filter_doc, sort=[("updated_at", -1)])
        workflows = []
        for doc in docs:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            workflows.append(Workflow.from_dict(doc))
        return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        return self.delete_one({"id": workflow_id})

    def update_last_run(self, workflow_id: str) -> bool:
        return self.update_one(
            {"id": workflow_id},
            {
                "last_run_at": datetime.now().isoformat(),
                "$inc": {"run_count": 1}
            }
        ) > 0
