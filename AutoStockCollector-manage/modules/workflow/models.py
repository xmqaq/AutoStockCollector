"""
选股工作流数据模型与存储
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
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
    workflow_type: str = ""

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
            "tags": self.tags,
            "workflow_type": self.workflow_type
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
            tags=data.get('tags', []),
            workflow_type=data.get('workflow_type', '')
        )


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class ExecutionStep:
    node_id: str
    node_label: str
    node_type: str
    status: str
    step: str = ""
    detail: str = ""
    stocks_count: int = 0
    progress: float = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionStep':
        return cls(
            node_id=data.get('node_id', ''),
            node_label=data.get('node_label', ''),
            node_type=data.get('node_type', ''),
            status=data.get('status', 'pending'),
            step=data.get('step', ''),
            detail=data.get('detail', ''),
            stocks_count=data.get('stocks_count', 0),
            progress=data.get('progress', 0),
            timestamp=data.get('timestamp', '')
        )


@dataclass
class WorkflowExecution:
    id: str
    workflow_id: str
    status: str
    progress: float = 0
    current_node: str = ""
    current_step: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str = ""
    finished_at: Optional[str] = None
    paused_node_idx: int = 0
    paused_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowExecution':
        return cls(
            id=data.get('id', ''),
            workflow_id=data.get('workflow_id', ''),
            status=data.get('status', ExecutionStatus.PENDING.value),
            progress=data.get('progress', 0),
            current_node=data.get('current_node', ''),
            current_step=data.get('current_step', ''),
            steps=data.get('steps', []),
            result=data.get('result'),
            error=data.get('error'),
            started_at=data.get('started_at', ''),
            finished_at=data.get('finished_at'),
            paused_node_idx=data.get('paused_node_idx', 0),
            paused_codes=data.get('paused_codes', [])
        )


@dataclass
class WorkflowTemplate:
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    is_public: bool = True
    owner_id: Optional[str] = None
    category: str = "custom"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "is_public": self.is_public,
            "owner_id": self.owner_id,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowTemplate':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            nodes=[WorkflowNode.from_dict(n) for n in data.get('nodes', [])],
            edges=[WorkflowEdge.from_dict(e) for e in data.get('edges', [])],
            is_public=data.get('is_public', True),
            owner_id=data.get('owner_id'),
            category=data.get('category', 'custom'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
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
        try:
            result = self.collection.update_one(
                {"id": workflow_id},
                {
                    "$set": {"last_run_at": datetime.now().isoformat()},
                    "$inc": {"run_count": 1}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Update last run failed: {e}")
            return False


class WorkflowExecutionStorage(MongoStorage):
    def __init__(self):
        super().__init__("workflow_execution")

    def create_execution(self, execution: WorkflowExecution) -> bool:
        return self.upsert_one({"id": execution.id}, execution.to_dict())

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        doc = self.find_one({"id": execution_id})
        if doc:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            return WorkflowExecution.from_dict(doc)
        return None

    def get_running_execution(self, workflow_id: str) -> Optional[WorkflowExecution]:
        docs = self.find_many(
            {"workflow_id": workflow_id, "status": {"$in": [
                ExecutionStatus.PENDING.value,
                ExecutionStatus.RUNNING.value,
                ExecutionStatus.PAUSED.value
            ]}},
            sort=[("started_at", -1)],
            limit=1
        )
        if docs:
            doc = docs[0]
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            return WorkflowExecution.from_dict(doc)
        return None

    def update_progress(
        self,
        execution_id: str,
        progress: float,
        current_node: str,
        current_step: str,
        step: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            update_doc: Dict[str, Any] = {
                "$set": {
                    "progress": progress,
                    "current_node": current_node,
                    "current_step": current_step,
                    "status": ExecutionStatus.RUNNING.value
                }
            }
            if step:
                update_doc["$push"] = {"steps": step}
            result = self.collection.update_one({"id": execution_id}, update_doc)
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Update progress failed: {e}")
            return False

    def complete_execution(self, execution_id: str, result: Dict[str, Any]) -> bool:
        return self.update_one(
            {"id": execution_id},
            {
                "status": ExecutionStatus.COMPLETED.value,
                "progress": 100,
                "result": result,
                "finished_at": datetime.now().isoformat()
            }
        ) > 0

    def fail_execution(self, execution_id: str, error: str) -> bool:
        short_error = (error or "未知错误")[:120]
        return self.update_one(
            {"id": execution_id},
            {
                "status": ExecutionStatus.FAILED.value,
                "error": error,
                "current_step": f"执行失败: {short_error}",
                "finished_at": datetime.now().isoformat()
            }
        ) > 0

    def cancel_execution(self, execution_id: str) -> bool:
        return self.update_one(
            {"id": execution_id},
            {
                "status": ExecutionStatus.CANCELLED.value,
                "finished_at": datetime.now().isoformat()
            }
        ) > 0

    def pause_execution(self, execution_id: str, node_idx: int, codes: List[str]) -> bool:
        try:
            result = self.collection.update_one(
                {"id": execution_id},
                {"$set": {
                    "status": ExecutionStatus.PAUSED.value,
                    "paused_node_idx": node_idx,
                    "paused_codes": codes,
                    "current_step": f"已暂停（将从第 {node_idx + 1} 步继续）",
                    "finished_at": datetime.now().isoformat()
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Pause execution failed: {e}")
            return False

    def resume_execution(self, execution_id: str) -> bool:
        try:
            result = self.collection.update_one(
                {"id": execution_id},
                {"$set": {
                    "status": ExecutionStatus.RUNNING.value,
                    "current_step": "恢复执行中...",
                    "finished_at": None,
                    "error": None
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Resume execution failed: {e}")
            return False

    def list_executions(self, workflow_id: str, limit: int = 20) -> List[WorkflowExecution]:
        docs = self.find_many(
            {"workflow_id": workflow_id},
            sort=[("started_at", -1)],
            limit=limit
        )
        executions = []
        for doc in docs:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            executions.append(WorkflowExecution.from_dict(doc))
        return executions

    def delete_executions(self, workflow_id: str) -> bool:
        return self.delete_many({"workflow_id": workflow_id})

    def delete_execution(self, execution_id: str) -> bool:
        return self.delete_one({"id": execution_id})

    def delete_executions_batch(self, execution_ids: List[str]) -> int:
        if not execution_ids:
            return 0
        return self.delete_many({"id": {"$in": execution_ids}})

    def cleanup_stale_executions(self, max_age_minutes: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).isoformat()
        try:
            result = self.collection.update_many(
                {"status": {"$in": [ExecutionStatus.RUNNING.value, ExecutionStatus.PENDING.value]},
                 "started_at": {"$lt": cutoff}},
                {"$set": {
                    "status": ExecutionStatus.FAILED.value,
                    "error": f"执行超时（超过{max_age_minutes}分钟），已自动终止",
                    "current_step": f"执行失败: 超时自动终止",
                    "finished_at": datetime.now().isoformat()
                }}
            )
            return result.modified_count
        except Exception as e:
            logger.error(f"Cleanup stale executions failed: {e}")
            return 0


class WorkflowTemplateStorage(MongoStorage):
    def __init__(self):
        super().__init__("workflow_template")

    def save_template(self, template: WorkflowTemplate) -> bool:
        template.updated_at = datetime.now().isoformat()
        if not template.created_at:
            template.created_at = template.updated_at
        return self.upsert_one({"id": template.id}, template.to_dict())

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        doc = self.find_one({"id": template_id})
        if doc:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            return WorkflowTemplate.from_dict(doc)
        return None

    def list_templates(
        self,
        owner_id: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_public: bool = True
    ) -> List[WorkflowTemplate]:
        filter_doc: Dict[str, Any] = {}
        or_conditions: List[Dict[str, Any]] = []

        if include_public:
            or_conditions.append({"is_public": True})

        if owner_id:
            or_conditions.append({"owner_id": owner_id})

        if or_conditions:
            filter_doc["$or"] = or_conditions
        elif not include_public:
            return []

        if category:
            filter_doc["category"] = category

        if tags:
            filter_doc["tags"] = {"$all": tags}

        docs = self.find_many(filter_doc, sort=[("created_at", -1)])
        templates = []
        for doc in docs:
            doc.pop("_id", None)
            doc.pop("_updated_at", None)
            templates.append(WorkflowTemplate.from_dict(doc))
        return templates

    def delete_template(self, template_id: str) -> bool:
        return self.delete_one({"id": template_id})

    def list_categories(self) -> List[str]:
        docs = self.distinct("category")
        return [c for c in docs if c]

    def list_all_tags(self) -> List[str]:
        tags = set()
        docs = self.find_many({})
        for doc in docs:
            for tag in doc.get("tags", []):
                tags.add(tag)
        return list(tags)
