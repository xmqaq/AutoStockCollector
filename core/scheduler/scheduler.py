"""
任务调度模块
实现任务状态机、进度监控、断点续采
"""
import uuid
import time
import threading
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from .enums import TaskStatus, TaskType
from core.collector.base import BaseCollector
from core.storage.mongo_storage import TaskStorage, KlineStorage, StockInfoStorage
from utils.logger import get_logger, init_task_logger
from utils.helpers import get_trading_days


logger = get_logger(__name__)


class Task:
    def __init__(
        self,
        task_id: str,
        task_type: str,
        params: Dict[str, Any],
        storage: TaskStorage
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.params = params
        self.storage = storage

        self.status = TaskStatus.PENDING
        self.progress = 0
        self.total = 0
        self.success = 0
        self.failed = 0
        self.error_message = ""
        self.start_time = None
        self.end_time = None
        self.logger = None

    def create(self) -> str:
        self.storage.create_task(
            self.task_id,
            self.task_type,
            self.params
        )
        return self.task_id

    def start(self):
        self.status = TaskStatus.RUNNING
        self.start_time = datetime.now()
        self.logger = init_task_logger(self.task_id)
        self.storage.update_task_status(
            self.task_id,
            "running",
            progress=self.progress,
            total=self.total
        )
        self.logger.info(f"Task {self.task_id} started")

    def update_progress(
        self,
        current: int,
        total: int,
        success: int = 0,
        failed: int = 0
    ):
        self.total = total
        self.progress = current
        self.success = success
        self.failed = failed

        self.storage.update_task_status(
            self.task_id,
            "running",
            progress=current,
            total=total,
            success=success,
            failed=failed
        )

        if self.logger:
            progress_pct = (current / total * 100) if total > 0 else 0
            self.logger.info(
                f"Progress: {current}/{total} ({progress_pct:.1f}%), "
                f"Success: {success}, Failed: {failed}"
            )

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

        if self.logger:
            self.logger.error(f"Task {self.task_id} failed: {error_message}")

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.end_time = datetime.now()

        self.storage.update_task_status(self.task_id, "cancelled")

        if self.logger:
            self.logger.info(f"Task {self.task_id} cancelled")

    def get_stats(self) -> Dict[str, Any]:
        elapsed = 0
        if self.start_time:
            end = self.end_time or datetime.now()
            elapsed = (end - self.start_time).total_seconds()

        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "progress_percent": (self.progress / self.total * 100) if self.total > 0 else 0,
            "elapsed_time": elapsed,
            "error_message": self.error_message
        }


class TaskScheduler:
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
            self._initialized = True
            self.task_storage = TaskStorage()
            self.kline_storage = KlineStorage()
            self.stock_info_storage = StockInfoStorage()

            self._tasks: Dict[str, Task] = {}
            self._task_queue = Queue()
            self._executor = ThreadPoolExecutor(max_workers=5)
            self._running = False
            self._scheduler_thread = None

            self._collectors: Dict[str, BaseCollector] = {}

            logger.info("TaskScheduler initialized")

    def register_collector(self, task_type: str, collector: BaseCollector):
        self._collectors[task_type] = collector
        logger.info(f"Registered collector for task type: {task_type}")

    def create_task(
        self,
        task_type: str,
        params: Dict[str, Any]
    ) -> str:
        task_id = f"{task_type}_{int(time.time() * 1000)}"
        task = Task(task_id, task_type, params, self.task_storage)
        task.create()

        with self._lock:
            self._tasks[task_id] = task

        logger.info(f"Created task: {task_id} ({task_type})")
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._tasks.get(task_id)
        if task:
            return task.get_stats()

        db_task = self.task_storage.get_task(task_id)
        if db_task:
            return {
                "task_id": db_task.get("task_id"),
                "task_type": db_task.get("task_type"),
                "status": db_task.get("status"),
                "progress": db_task.get("progress", 0),
                "total": db_task.get("total", 0),
                "success": db_task.get("success", 0),
                "failed": db_task.get("failed", 0),
                "error_message": db_task.get("error_message", "")
            }

        return None

    def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        if status:
            db_tasks = self.task_storage.find_many(
                {"status": status},
                sort=[("create_time", -1)],
                limit=limit
            )
        else:
            db_tasks = self.task_storage.find_many(
                sort=[("create_time", -1)],
                limit=limit
            )

        return [
            {
                "task_id": t.get("task_id"),
                "task_type": t.get("task_type"),
                "status": t.get("status"),
                "progress": t.get("progress", 0),
                "total": t.get("total", 0),
                "create_time": t.get("create_time")
            }
            for t in db_tasks
        ]

    def start_task(self, task_id: str) -> bool:
        if not task_id:
            logger.error("task_id cannot be empty")
            return False

        task = self._tasks.get(task_id)
        if not task:
            db_task = self.task_storage.get_task(task_id)
            if db_task:
                task = Task(task_id, db_task.get("task_type"), db_task.get("params", {}), self.task_storage)
                with self._lock:
                    self._tasks[task_id] = task
            else:
                logger.error(f"Task {task_id} not found")
                return False

        if task.status == TaskStatus.RUNNING:
            logger.warning(f"Task {task_id} is already running")
            return False

        if task.status == TaskStatus.COMPLETED:
            logger.info(f"Task {task_id} is already completed, resetting for new execution")
            task.status = TaskStatus.PENDING
            task.progress = 0
            task.success = 0
            task.failed = 0
            task.error_message = ""

        if task.status == TaskStatus.CANCELLED:
            task.status = TaskStatus.PENDING

        if task.status != TaskStatus.PENDING:
            logger.warning(f"Task {task_id} cannot start from status: {task.status.value}")
            return False

        future = self._executor.submit(self._execute_task, task)
        future.add_done_callback(
            lambda f: self._on_task_done(task_id, f)
        )

        return True

    def cancel_task(self, task_id: str) -> bool:
        if not task_id:
            logger.error("task_id cannot be empty")
            return False

        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        if task.status == TaskStatus.RUNNING:
            task.cancel()
            task.storage.update_task_status(task_id, "cancelled")
            return True

        if task.status == TaskStatus.COMPLETED:
            logger.info(f"Task {task_id} is already completed, cannot cancel")
            return False

        if task.status == TaskStatus.CANCELLED:
            logger.info(f"Task {task_id} is already cancelled")
            return False

        task.cancel()
        return True

    def retry_failed_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            db_task = self.task_storage.get_task(task_id)
            if not db_task:
                logger.error(f"Task {task_id} not found for retry")
                return False
            task = Task(task_id, db_task.get("task_type"), db_task.get("params", {}), self.task_storage)
            with self._lock:
                self._tasks[task_id] = task

        if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            logger.warning(f"Cannot retry task {task_id} with status: {task.status.value}")
            return False

        task.status = TaskStatus.PENDING
        task.progress = 0
        task.success = 0
        task.failed = 0
        task.error_message = ""
        task.start_time = None
        task.end_time = None

        self.storage.update_task_status(task_id, "pending")

        return self.start_task(task_id)

    def _execute_task(self, task: Task):
        task.start()

        try:
            if task.task_type == TaskType.KLINE_COLLECTION.value:
                self._execute_kline_task(task)
            elif task.task_type == TaskType.STOCK_INFO_COLLECTION.value:
                self._execute_stock_info_task(task)
            elif task.task_type == TaskType.INCREMENTAL_COLLECTION.value:
                self._execute_incremental_task(task)
            elif task.task_type == TaskType.BACKFILL_COLLECTION.value:
                self._execute_backfill_task(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

        except Exception as e:
            logger.error(f"Task {task.task_id} execution error: {e}")
            task.fail(str(e))

    def _execute_kline_task(self, task: Task):
        codes = task.params.get("codes", [])
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        adjust = task.params.get("adjust", "qfq")
        priority_watchlist = task.params.get("priority_watchlist", False)

        watchlist_codes = set()
        if priority_watchlist:
            try:
                from modules.watchlist.watchlist import WatchlistManager
                watchlist = WatchlistManager()
                watchlist_stocks = watchlist.get_watchlist(user_id=task.params.get("user_id", "default"))
                watchlist_codes = {s.get("code") for s in watchlist_stocks}
                logger.info(f"Watchlist priority enabled: {len(watchlist_codes)} stocks in watchlist")
            except Exception as e:
                logger.error(f"Failed to get watchlist: {e}")

        if not codes:
            codes = self._collectors.get("kline").get_all_stock_codes()

        if watchlist_codes:
            priority_codes = [c for c in codes if c in watchlist_codes]
            normal_codes = [c for c in codes if c not in watchlist_codes]
            codes = priority_codes + normal_codes

        total = len(codes)
        success_count = 0
        failed_count = 0

        collector = self._collectors.get("kline")

        for i, code in enumerate(codes):
            if task.status == TaskStatus.CANCELLED:
                break

            try:
                result = collector.execute_with_retry(
                    collector.collect_single,
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )

                if result:
                    self.kline_storage.save_kline_batch(result)
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to collect kline for {code}: {e}")

            task.update_progress(i + 1, total, success_count, failed_count)

        task.complete(success_count, failed_count)

    def _execute_stock_info_task(self, task: Task):
        codes = task.params.get("codes", [])

        if not codes:
            codes = self._collectors.get("stock_info").get_all_stock_codes()

        total = len(codes)
        success_count = 0
        failed_count = 0

        collector = self._collectors.get("stock_info")

        for i, code in enumerate(codes):
            if task.status == TaskStatus.CANCELLED:
                break

            try:
                result = collector.execute_with_retry(collector.collect_single, code)
                if result:
                    self.stock_info_storage.save_stock_info(result)
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to collect stock info for {code}: {e}")

            task.update_progress(i + 1, total, success_count, failed_count)

        task.complete(success_count, failed_count)

    def _execute_incremental_task(self, task: Task):
        codes = task.params.get("codes", [])
        data_type = task.params.get("data_type", "kline")

        if not codes:
            codes = self._collectors.get("kline").get_all_stock_codes()

        total = len(codes)
        success_count = 0
        failed_count = 0

        collector = self._collectors.get("kline")

        for i, code in enumerate(codes):
            if task.status == TaskStatus.CANCELLED:
                break

            try:
                result = collector.collect_incremental(code)
                if result:
                    self.kline_storage.save_kline_batch(result)
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed incremental collect for {code}: {e}")

            task.update_progress(i + 1, total, success_count, failed_count)

        task.complete(success_count, failed_count)

    def _execute_backfill_task(self, task: Task):
        codes = task.params.get("codes", [])
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")

        missing_data = self._identify_missing_data(codes, start_date, end_date)

        total = len(missing_data)
        success_count = 0
        failed_count = 0

        for i, (code, date) in enumerate(missing_data):
            if task.status == TaskStatus.CANCELLED:
                break

            try:
                collector = self._collectors.get("kline")
                result = collector.execute_with_retry(
                    collector.collect_single,
                    code,
                    start_date=date,
                    end_date=date
                )

                if result:
                    self.kline_storage.save_kline_batch(result)
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed backfill for {code} on {date}: {e}")

            task.update_progress(i + 1, total, success_count, failed_count)

        task.complete(success_count, failed_count)

    def _identify_missing_data(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> List[tuple]:
        trading_days = get_trading_days(start_date, end_date)
        missing_data = []

        for code in codes:
            earliest, latest = self.kline_storage.get_kline_range(code)

            if not earliest:
                missing_data.extend([(code, d) for d in trading_days])
                continue

            existing_dates = set()
            records = self.kline_storage.find_many({"code": code})
            for r in records:
                if "date" in r:
                    existing_dates.add(r["date"])

            for day in trading_days:
                if day not in existing_dates:
                    missing_data.append((code, day))

        return missing_data

    def _on_task_done(self, task_id: str, future: Future):
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

    def start_scheduler(self):
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler)
        self._scheduler_thread.daemon = True
        self._scheduler_thread.start()
        logger.info("TaskScheduler started")

    def stop_scheduler(self):
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        self._executor.shutdown(wait=True)
        logger.info("TaskScheduler stopped")

    def _run_scheduler(self):
        while self._running:
            try:
                pending_tasks = self.task_storage.get_pending_tasks()

                for task_info in pending_tasks:
                    task_id = task_info.get("task_id")
                    if task_id not in self._tasks:
                        params = task_info.get("params", {})
                        task_type = task_info.get("task_type")
                        task = Task(task_id, task_type, params, self.task_storage)
                        with self._lock:
                            self._tasks[task_id] = task
                        self.start_task(task_id)

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(5)

    def get_task_statistics(self) -> Dict[str, Any]:
        running = len(self.task_storage.get_running_tasks())
        pending = len(self.task_storage.get_pending_tasks())

        return {
            "running_tasks": running,
            "pending_tasks": pending,
            "active_tasks": len(self._tasks),
            "thread_pool_size": 5,
            "timestamp": datetime.now().isoformat()
        }


scheduler = TaskScheduler()