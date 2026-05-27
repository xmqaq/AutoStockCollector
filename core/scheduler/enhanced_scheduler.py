"""
增强的任务调度模块
包含状态监控、异常重试、超时熔断机制
"""
import uuid
import time
import threading
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from .enums import TaskStatus, TaskType
from .scheduler import TaskScheduler, Task
from core.collector.base import BaseCollector
from core.storage.mongo_storage import TaskStorage, KlineStorage, StockInfoStorage
from core.logs.chain_logger import chain_logger, LogLevel, LogStage
from utils.logger import get_logger, init_task_logger
from utils.helpers import get_trading_days


logger = get_logger(__name__)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0, reset_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"
        self._mutex = threading.Lock()

    def record_success(self):
        with self._mutex:
            self.failures = 0
            if self.state == "half_open":
                self.state = "closed"
                logger.info("Circuit breaker reset to closed state")

    def record_failure(self):
        with self._mutex:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.warning(f"Circuit breaker opened after {self.failures} failures")

    def can_execute(self) -> bool:
        with self._mutex:
            if self.state == "closed":
                return True

            if self.state == "open":
                if self.last_failure_time and (time.time() - self.last_failure_time) >= self.timeout:
                    self.state = "half_open"
                    logger.info("Circuit breaker entering half-open state")
                    return True
                return False

            if self.state == "half_open":
                return True

        return False


class TaskMetrics:
    def __init__(self):
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_duration = 0.0
        self.api_calls = 0
        self.api_failures = 0
        self._mutex = threading.Lock()

    def record_task_completion(self, duration: float, success: bool):
        with self._mutex:
            self.total_tasks += 1
            self.total_duration += duration
            if success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1

    def record_api_call(self, success: bool):
        with self._mutex:
            self.api_calls += 1
            if not success:
                self.api_failures += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._mutex:
            return {
                "total_tasks": self.total_tasks,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "success_rate": self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0,
                "avg_duration": self.total_duration / self.total_tasks if self.total_tasks > 0 else 0,
                "api_calls": self.api_calls,
                "api_failures": self.api_failures,
                "api_success_rate": (self.api_calls - self.api_failures) / self.api_calls if self.api_calls > 0 else 0
            }


class EnhancedTask(Task):
    def __init__(
        self,
        task_id: str,
        task_type: str,
        params: Dict[str, Any],
        storage: TaskStorage,
        max_retries: int = 3
    ):
        super().__init__(task_id, task_type, params, storage)
        self.max_retries = max_retries
        self.retry_count = 0
        self.circuit_breaker = CircuitBreaker()
        self.request_id = None
        self.start_time = None
        self.end_time = None

    def start(self):
        self.status = TaskStatus.RUNNING
        self.start_time = datetime.now()
        self.retry_count = 0
        self.request_id = chain_logger.start_chain(self.task_id, self.task_type, self.params)
        self.logger = init_task_logger(self.task_id)
        self.storage.update_task_status(
            self.task_id,
            "running",
            progress=self.progress,
            total=self.total
        )
        self.logger.info(f"Task {self.task_id} started (request_id: {self.request_id})")

    def retry(self) -> bool:
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = TaskStatus.PENDING
            self.logger.info(f"Retrying task {self.task_id} (attempt {self.retry_count}/{self.max_retries})")
            return True
        return False

    def complete(self, success_count: int = 0, failed_count: int = 0):
        self.status = TaskStatus.COMPLETED
        self.end_time = datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() if self.start_time else 0

        self.storage.update_task_status(
            self.task_id,
            "completed",
            progress=self.total,
            total=self.total,
            success=success_count,
            failed=failed_count
        )

        chain_logger.end_chain(
            self.request_id,
            success=True,
            stats={"elapsed": elapsed, "success": success_count, "failed": failed_count}
        )

        if self.logger:
            self.logger.info(
                f"Task {self.task_id} completed: "
                f"Success={success_count}, Failed={failed_count}, "
                f"Elapsed={elapsed:.2f}s"
            )

    def fail(self, error_message: str):
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.end_time = datetime.now()

        self.storage.update_task_status(
            self.task_id,
            "failed",
            error_message=error_message
        )

        chain_logger.end_chain(
            self.request_id,
            success=False,
            error_message=error_message
        )

        if self.logger:
            self.logger.error(f"Task {self.task_id} failed: {error_message}")


class EnhancedTaskScheduler(TaskScheduler):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            super().__init__()
            self._initialized = True
            self.metrics = TaskMetrics()
            self._circuit_breakers: Dict[str, CircuitBreaker] = {}
            self._task_timeout = 3600.0
            self._monitor_interval = 60.0
            self._start_monitoring()

    def _get_circuit_breaker(self, task_type: str) -> CircuitBreaker:
        if task_type not in self._circuit_breakers:
            self._circuit_breakers[task_type] = CircuitBreaker()
        return self._circuit_breakers[task_type]

    def _start_monitoring(self):
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        while True:
            try:
                self._check_overdue_tasks()
                self._log_metrics()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            time.sleep(self._monitor_interval)

    def _check_overdue_tasks(self):
        with self._lock:
            now = datetime.now()
            for task_id, task in self._tasks.items():
                if task.status == TaskStatus.RUNNING and task.start_time:
                    elapsed = (now - task.start_time).total_seconds()
                    if elapsed > self._task_timeout:
                        logger.warning(f"Task {task_id} overdue ({elapsed:.0f}s), cancelling")
                        task.cancel()

    def _log_metrics(self):
        stats = self.metrics.get_stats()
        logger.info(f"Scheduler metrics: {stats}")

    def create_enhanced_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> str:
        task_id = f"{task_type}_{int(time.time() * 1000)}"
        storage = TaskStorage()
        task = EnhancedTask(task_id, task_type, params, storage, max_retries)
        task.create()

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"Created enhanced task: {task_id} ({task_type})")
        return task_id

    def start_enhanced_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        if not task.circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker open for task {task_id}")
            return False

        return self.start_task(task_id)

    def _execute_enhanced_kline_task(self, task: EnhancedTask):
        task.start()
        codes = task.params.get("codes", [])
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        adjust = task.params.get("adjust", "qfq")

        if not codes:
            codes = self._collectors.get("kline").get_all_stock_codes()

        total = len(codes)
        success_count = 0
        failed_count = 0

        collector = self._collectors.get("kline")
        start_time = time.time()

        for i, code in enumerate(codes):
            if task.status == TaskStatus.CANCELLED:
                break

            api_start = time.time()
            try:
                result = collector.execute_with_retry(
                    collector.collect_single,
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                api_duration = time.time() - api_start

                chain_logger.log_api_call(
                    task.request_id,
                    "kline_collector",
                    {"code": code},
                    api_duration,
                    success=bool(result)
                )

                if result:
                    self.kline_storage.save_kline_batch(result)
                    success_count += 1
                else:
                    failed_count += 1

                task.circuit_breaker.record_success()
                self.metrics.record_api_call(success=True)

            except Exception as e:
                api_duration = time.time() - api_start
                failed_count += 1

                chain_logger.log_api_call(
                    task.request_id,
                    "kline_collector",
                    {"code": code},
                    api_duration,
                    success=False,
                    error=str(e)
                )

                task.circuit_breaker.record_failure()
                self.metrics.record_api_call(success=False)
                logger.error(f"Failed to collect kline for {code}: {e}")

            task.update_progress(i + 1, total, success_count, failed_count)

        duration = time.time() - start_time
        self.metrics.record_task_completion(duration, success=(failed_count < total))

        if failed_count > 0 and task.retry_count < task.max_retries:
            if task.retry():
                self.start_enhanced_task(task_id)

        task.complete(success_count, failed_count)

    def get_scheduler_stats(self) -> Dict[str, Any]:
        task_stats = self.list_tasks()
        running = sum(1 for t in task_stats if t.get("status") == "running")
        pending = sum(1 for t in task_stats if t.get("status") == "pending")
        completed = sum(1 for t in task_stats if t.get("status") == "completed")
        failed = sum(1 for t in task_stats if t.get("status") == "failed")

        return {
            "scheduler_metrics": self.metrics.get_stats(),
            "task_counts": {
                "running": running,
                "pending": pending,
                "completed": completed,
                "failed": failed,
                "total": len(task_stats)
            },
            "circuit_breakers": {
                task_type: {
                    "state": cb.state,
                    "failures": cb.failures
                }
                for task_type, cb in self._circuit_breakers.items()
            }
        }


enhanced_scheduler = EnhancedTaskScheduler()