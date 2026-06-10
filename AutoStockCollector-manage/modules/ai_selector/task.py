"""
异步任务系统
支持选股任务异步化、批量化、断点续跑
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from utils.helpers import beijing_now
from enum import Enum
from threading import Thread, Lock
from queue import Queue
import time
import uuid
from utils.logger import get_logger


logger = get_logger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    task_type: str
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    total: int = 0
    completed: int = 0
    failed: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AsyncTaskQueue:
    def __init__(self, max_workers: int = 3):
        self._queue: Queue = Queue()
        self._tasks: Dict[str, Task] = {}
        self._max_workers = max_workers
        self._workers: List[Thread] = []
        self._running = False
        self._lock = Lock()

    def start(self):
        self._running = True
        for i in range(self._max_workers):
            t = Thread(target=self._worker, daemon=True, name=f"TaskWorker-{i}")
            t.start()
            self._workers.append(t)
        logger.info(f"Started {self._max_workers} task workers")

    def stop(self):
        self._running = False
        for t in self._workers:
            t.join(timeout=5)
        self._workers.clear()
        logger.info("Task workers stopped")

    def submit(
        self,
        task_type: str,
        params: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> str:
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            task_type=task_type,
            params=params,
            status=TaskStatus.PENDING,
            total=params.get("total", 0),
            created_at=beijing_now()
        )

        with self._lock:
            self._tasks[task_id] = task

        self._queue.put((task_id, callback))
        logger.info(f"Task {task_id} submitted: {task_type}")

        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_progress(
        self,
        task_id: str,
        completed: int = 0,
        failed: int = 0,
        progress: float = 0.0
    ):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.completed += completed
                task.failed += failed
                task.progress = progress
                task.updated_at = beijing_now()

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.updated_at = beijing_now()
                logger.info(f"Task {task_id} cancelled")
                return True
        return False

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        with self._lock:
            tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        return [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status.value,
                "progress": t.progress,
                "completed": t.completed,
                "failed": t.failed,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat()
            }
            for t in tasks
        ]

    def _worker(self):
        while self._running:
            try:
                task_id, callback = self._queue.get(timeout=1)

                with self._lock:
                    task = self._tasks.get(task_id)

                if not task or task.status == TaskStatus.CANCELLED:
                    continue

                task.status = TaskStatus.RUNNING
                task.started_at = beijing_now()
                task.updated_at = beijing_now()

                try:
                    result = self._execute_task(task)

                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = beijing_now()

                    if task.total > 0:
                        task.progress = 1.0

                    logger.info(f"Task {task_id} completed")

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = beijing_now()
                    logger.error(f"Task {task_id} failed: {e}")

                task.updated_at = beijing_now()

                if callback:
                    try:
                        callback(task)
                    except Exception as e:
                        logger.error(f"Task callback failed: {e}")

            except Exception:
                continue

    def _execute_task(self, task: Task) -> Any:
        task_type = task.task_type
        params = task.params

        if task_type == "selection":
            return self._execute_selection_task(task, params)
        elif task_type == "backtest":
            return self._execute_backtest_task(task, params)
        elif task_type == "batch_analysis":
            return self._execute_batch_analysis_task(task, params)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    def _execute_selection_task(self, task: Task, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from .strategies import (
            SentimentDrivenStrategy,
            FundFlowStrategy,
            ValueStrategy,
            SectorRotationStrategy
        )

        strategy_map = {
            "sentiment": SentimentDrivenStrategy,
            "fund_flow": FundFlowStrategy,
            "value": ValueStrategy,
            "sector": SectorRotationStrategy
        }

        strategy_name = params.get("strategy", "fund_flow")
        codes = params.get("codes", [])
        top_n = params.get("top_n", 20)
        min_score = params.get("min_score", 60.0)

        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        strategy = strategy_class()
        results = strategy.select(codes, top_n=top_n, min_score=min_score)

        task.total = len(codes)
        task.completed = len(results)

        return [r.to_dict() for r in results]

    def _execute_backtest_task(self, task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
        from .backtest import ai_backtest, SignalGenerator

        codes = params.get("codes", [])
        start_date = params.get("start_date", "")
        end_date = params.get("end_date", "")
        signal_type = params.get("signal_type", "ma_cross")

        signal_funcs = {
            "ma_cross": SignalGenerator.ma_cross_signals,
            "momentum": SignalGenerator.momentum_signals,
            "rsi": SignalGenerator.rsi_signals,
            "volume": SignalGenerator.volume_breakout_signals
        }

        signal_func = signal_funcs.get(signal_type, SignalGenerator.ma_cross_signals)

        result = ai_backtest.backtest_strategy(
            codes=codes,
            signals_func=signal_func,
            start_date=start_date,
            end_date=end_date
        )

        return result

    def _execute_batch_analysis_task(self, task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
        from .models import llm_router, StockSelectionSchema

        codes = params.get("codes", [])
        analysis_type = params.get("analysis_type", "comprehensive")

        results = {}
        schema = StockSelectionSchema.get_analysis_schema()

        for i, code in enumerate(codes):
            try:
                prompt = self._build_analysis_prompt(code, analysis_type)
                response = llm_router.chat(prompt, schema=schema)

                if response.success:
                    import json
                    try:
                        results[code] = json.loads(response.content)
                    except json.JSONDecodeError:
                        results[code] = {"raw": response.content}

                task.completed = i + 1
                task.progress = (i + 1) / len(codes)
                task.updated_at = beijing_now()

            except Exception as e:
                task.failed += 1
                logger.error(f"Analysis failed for {code}: {e}")

        return results

    def _build_analysis_prompt(self, code: str, analysis_type: str) -> str:
        if analysis_type == "comprehensive":
            return f"""分析股票 {code} 的投资价值。

请输出JSON格式：
{{"score": 评分0-100, "recommendation": "推荐/观望/回避", "reasons": ["理由"], "summary": "总结"}}"""
        elif analysis_type == "technical":
            return f"""分析股票 {code} 的技术面。

请输出JSON格式：
{{"score": 评分0-100, "trend": "趋势判断", "support": 支撑位, "resistance": 压力位}}"""
        else:
            return f"""简要分析股票 {code}。

请输出JSON格式：
{{"score": 评分0-100, "recommendation": "建议"}}"""


task_queue = AsyncTaskQueue(max_workers=3)
task_queue.start()