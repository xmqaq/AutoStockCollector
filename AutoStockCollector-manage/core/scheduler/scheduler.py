"""
任务调度模块
- 任务状态机与进度追踪
- 股票级别并发（ThreadPoolExecutor per task）
- 8 种数据类型全覆盖调度
- TaskMetrics 运行时指标
- 超时任务自动取消
"""
import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from .enums import TaskStatus, TaskType
from core.storage.mongo_storage import TaskStorage, KlineStorage, StockInfoStorage
from config.settings import Settings
from utils.logger import get_logger, init_task_logger
from utils.helpers import get_trading_days


logger = get_logger(__name__)

# 任务超时（秒）：超过此时间的 RUNNING 任务会被强制取消
_TASK_TIMEOUT_SECONDS = 3600


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
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.logger = None

    def create(self) -> str:
        self.storage.create_task(self.task_id, self.task_type, self.params)
        return self.task_id

    def _persist(self, status: str, **kwargs):
        """存储操作失败时只记录 warning，不影响内存任务状态"""
        try:
            self.storage.update_task_status(self.task_id, status, **kwargs)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"Task persist skipped (no DB): {e}")

    def start(self):
        self.status = TaskStatus.RUNNING
        self.start_time = datetime.now()
        self.logger = init_task_logger(self.task_id)
        self._persist("running", progress=self.progress, total=self.total)
        self.logger.info(f"Task {self.task_id} started")

    def update_progress(self, current: int, total: int, success: int = 0, failed: int = 0):
        self.total = total
        self.progress = current
        self.success = success
        self.failed = failed
        self._persist("running", progress=current, total=total, success=success, failed=failed)
        if self.logger:
            pct = current / total * 100 if total > 0 else 0
            self.logger.info(
                f"Progress {current}/{total} ({pct:.1f}%) "
                f"success={success} failed={failed}"
            )

    def complete(self, success_count: int = 0, failed_count: int = 0):
        self.status = TaskStatus.COMPLETED
        self.end_time = datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        self.progress = self.total
        self.success = success_count
        self.failed = failed_count
        self._persist(
            "completed",
            progress=self.total, total=self.total,
            success=success_count, failed=failed_count
        )
        if self.logger:
            self.logger.info(
                f"Task {self.task_id} completed "
                f"success={success_count} failed={failed_count} elapsed={elapsed:.1f}s"
            )

    def fail(self, error_message: str):
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.end_time = datetime.now()
        self._persist("failed", error_message=error_message)
        if self.logger:
            self.logger.error(f"Task {self.task_id} failed: {error_message}")

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.end_time = datetime.now()
        self._persist("cancelled")
        if self.logger:
            self.logger.info(f"Task {self.task_id} cancelled")

    def get_stats(self) -> Dict[str, Any]:
        elapsed = 0.0
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
            "error_message": self.error_message,
        }


class TaskMetrics:
    """运行时统计，内存中维护，不写 DB"""

    def __init__(self):
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_duration = 0.0
        self._lock = threading.Lock()

    def record_completion(self, duration: float, success: bool):
        with self._lock:
            self.total_tasks += 1
            self.total_duration += duration
            if success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            n = self.total_tasks
            return {
                "total_tasks": n,
                "completed_tasks": self.completed_tasks,
                "failed_tasks": self.failed_tasks,
                "success_rate": self.completed_tasks / n if n > 0 else 0.0,
                "avg_duration_s": self.total_duration / n if n > 0 else 0.0,
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
            self._executor = ThreadPoolExecutor(max_workers=10)
            self._running = False
            self._scheduler_thread = None
            self._collectors: Dict[str, Any] = {}
            self.metrics = TaskMetrics()

            self._start_monitor()
            logger.info("TaskScheduler initialized")

    # ------------------------------------------------------------------ #
    # Collector 懒加载工厂                                                  #
    # ------------------------------------------------------------------ #

    def _get_collector(self, task_type: str):
        """按需创建 collector，避免启动时全量导入"""
        if task_type in self._collectors:
            return self._collectors[task_type]

        from core.collector.kline_collector import KlineCollector
        from core.collector.stock_info_collector import StockInfoCollector
        from core.collector.financial_collector import FinancialCollector
        from core.collector.news_collector import NewsCollector
        from core.collector.fund_flow_collector import (
            FundFlowCollector, DragonTigerCollector,
        )
        from core.collector.index_collector import IndexCollector

        from core.collector.fund_flow_collector import MarginCollector
        from core.collector.block_collector import BlockCollector

        mapping = {
            TaskType.KLINE_COLLECTION.value: KlineCollector,
            TaskType.INCREMENTAL_COLLECTION.value: KlineCollector,
            TaskType.BACKFILL_COLLECTION.value: KlineCollector,
            TaskType.STOCK_INFO_COLLECTION.value: StockInfoCollector,
            TaskType.FINANCIAL_COLLECTION.value: FinancialCollector,
            TaskType.NEWS_COLLECTION.value: NewsCollector,
            TaskType.FUND_FLOW_COLLECTION.value: FundFlowCollector,
            TaskType.DRAGON_TIGER_COLLECTION.value: DragonTigerCollector,
            TaskType.INDEX_COLLECTION.value: IndexCollector,
            TaskType.MARGIN_COLLECTION.value: MarginCollector,
            TaskType.BLOCK_COLLECTION.value: BlockCollector,
        }

        cls = mapping.get(task_type)
        if cls:
            collector = cls()
            self._collectors[task_type] = collector
            return collector
        return None

    def register_collector(self, task_type: str, collector):
        """手动注册（向后兼容）"""
        self._collectors[task_type] = collector
        logger.info(f"Registered collector for task type: {task_type}")

    # ------------------------------------------------------------------ #
    # Task CRUD                                                            #
    # ------------------------------------------------------------------ #

    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        task_id = f"{task_type}_{int(time.time() * 1000)}"
        task = Task(task_id, task_type, params, self.task_storage)
        try:
            task.create()
        except Exception as e:
            logger.warning(f"Task persistence unavailable, running in-memory only: {e}")
        with self._lock:
            self._tasks[task_id] = task
        logger.info(f"Created task: {task_id}")
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
                "error_message": db_task.get("error_message", ""),
            }
        return None

    def list_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        # 先从内存中拿运行中的任务
        in_memory = [t.get_stats() for t in self._tasks.values()]

        # 再从 DB 拿历史任务
        query = {"status": status} if status else {}
        db_tasks = self.task_storage.find_many(
            query, sort=[("create_time", -1)], limit=limit
        )
        db_list = [
            {
                "task_id": t.get("task_id"),
                "task_type": t.get("task_type"),
                "status": t.get("status"),
                "progress": t.get("progress", 0),
                "total": t.get("total", 0),
                "create_time": t.get("create_time"),
            }
            for t in db_tasks
        ]

        # 合并，内存版优先（状态最新）
        db_ids = {t["task_id"] for t in db_list}
        merged = in_memory + [t for t in db_list if t["task_id"] not in {x["task_id"] for x in in_memory}]
        return merged[:limit]

    def start_task(self, task_id: str) -> bool:
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
            logger.warning(f"Task {task_id} already running")
            return False

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            task.status = TaskStatus.PENDING
            task.progress = 0
            task.success = 0
            task.failed = 0
            task.error_message = ""

        if task.status != TaskStatus.PENDING:
            logger.warning(f"Task {task_id} cannot start from status: {task.status.value}")
            return False

        future = self._executor.submit(self._execute_task, task)
        future.add_done_callback(lambda f: self._on_task_done(task_id, f))
        return True

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
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
            logger.warning(f"Cannot retry task {task_id}: status={task.status.value}")
            return False

        task.status = TaskStatus.PENDING
        task.progress = 0
        task.success = 0
        task.failed = 0
        task.error_message = ""
        task.start_time = None
        task.end_time = None
        self.task_storage.update_task_status(task_id, "pending")  # 修正：task_storage 不是 storage
        return self.start_task(task_id)

    # ------------------------------------------------------------------ #
    # Task 分发                                                             #
    # ------------------------------------------------------------------ #

    def _execute_task(self, task: Task):
        task.start()
        start_ts = time.time()
        try:
            dispatch = {
                TaskType.KLINE_COLLECTION.value: self._execute_kline_task,
                TaskType.INCREMENTAL_COLLECTION.value: self._execute_incremental_task,
                TaskType.BACKFILL_COLLECTION.value: self._execute_backfill_task,
                TaskType.STOCK_INFO_COLLECTION.value: self._execute_stock_info_task,
                TaskType.FINANCIAL_COLLECTION.value: self._execute_financial_task,
                TaskType.NEWS_COLLECTION.value: self._execute_news_task,
                TaskType.FUND_FLOW_COLLECTION.value: self._execute_fund_flow_task,
                TaskType.INDEX_COLLECTION.value: self._execute_index_task,
                TaskType.DRAGON_TIGER_COLLECTION.value: self._execute_dragon_tiger_task,
                TaskType.SECTOR_COLLECTION.value: self._execute_sector_task,
                TaskType.MARGIN_COLLECTION.value: self._execute_margin_task,
                TaskType.BLOCK_COLLECTION.value: self._execute_block_task,
            }
            handler = dispatch.get(task.task_type)
            if handler is None:
                raise ValueError(f"Unknown task type: {task.task_type}")
            handler(task)
        except Exception as e:
            logger.error(f"Task {task.task_id} execution error: {e}")
            task.fail(str(e))
        finally:
            duration = time.time() - start_ts
            self.metrics.record_completion(duration, task.status == TaskStatus.COMPLETED)

    # ------------------------------------------------------------------ #
    # 并发采集辅助                                                           #
    # ------------------------------------------------------------------ #

    def _parallel_collect(
        self,
        task: Task,
        codes: List[str],
        collect_fn,       # (code) -> List[dict] | dict | None
        save_fn,          # (records) -> None
        progress_every: int = 10,
    ):
        """
        通用并发采集框架：
        - 每个股票起一个线程，并发上限由 RiskController.ConcurrentController 控制
        - 每 progress_every 只或末尾更新一次进度
        """
        total = len(codes)
        cnt = {"done": 0, "success": 0, "failed": 0}
        lock = threading.Lock()

        def collect_one(code):
            if task.status == TaskStatus.CANCELLED:
                return
            saved = False
            try:
                result = collect_fn(code)
                if result:
                    save_fn(result)   # MongoDB 写入在锁外，pymongo 连接池线程安全
                    saved = True
            except Exception as e:
                logger.error(f"collect {code} failed: {e}")
            with lock:
                cnt["success" if saved else "failed"] += 1
                cnt["done"] += 1
                if cnt["done"] % progress_every == 0 or cnt["done"] == total:
                    task.update_progress(cnt["done"], total, cnt["success"], cnt["failed"])

        max_workers = Settings.get_max_concurrent()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(collect_one, codes))

        task.complete(cnt["success"], cnt["failed"])

    # ------------------------------------------------------------------ #
    # K 线                                                                  #
    # ------------------------------------------------------------------ #

    def _execute_kline_task(self, task: Task):
        codes = task.params.get("codes", [])
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        adjust = task.params.get("adjust", "qfq")
        priority_watchlist = task.params.get("priority_watchlist", False)

        collector = self._get_collector(TaskType.KLINE_COLLECTION.value)
        if not codes:
            codes = collector.get_all_stock_codes()

        if priority_watchlist:
            try:
                from modules.watchlist.watchlist import WatchlistManager
                wl_codes = {s.get("code") for s in WatchlistManager().get_watchlist(
                    user_id=task.params.get("user_id", "default")
                )}
                codes = [c for c in codes if c in wl_codes] + [c for c in codes if c not in wl_codes]
            except Exception as e:
                logger.error(f"Watchlist priority error: {e}")

        def collect_fn(code):
            return collector.execute_with_retry(
                collector.collect_single, code,
                start_date=start_date, end_date=end_date, adjust=adjust
            )

        self._parallel_collect(
            task, codes,
            collect_fn=collect_fn,
            save_fn=lambda r: self.kline_storage.save_kline_batch(r),
        )

    # ------------------------------------------------------------------ #
    # 增量 K 线                                                             #
    # ------------------------------------------------------------------ #

    def _execute_incremental_task(self, task: Task):
        codes = task.params.get("codes", [])
        collector = self._get_collector(TaskType.INCREMENTAL_COLLECTION.value)
        if not codes:
            codes = collector.get_all_stock_codes()

        def collect_fn(code):
            return collector.collect_incremental(code)

        self._parallel_collect(
            task, codes,
            collect_fn=collect_fn,
            save_fn=lambda r: self.kline_storage.save_kline_batch(r),
        )

    # ------------------------------------------------------------------ #
    # 回填                                                                  #
    # ------------------------------------------------------------------ #

    def _execute_backfill_task(self, task: Task):
        codes = task.params.get("codes", [])
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")

        missing = self._identify_missing_data(codes, start_date, end_date)
        total = len(missing)
        cnt = {"done": 0, "success": 0, "failed": 0}
        lock = threading.Lock()
        collector = self._get_collector(TaskType.BACKFILL_COLLECTION.value)

        def backfill_one(item):
            code, date = item
            if task.status == TaskStatus.CANCELLED:
                return
            saved = False
            try:
                result = collector.execute_with_retry(
                    collector.collect_single, code,
                    start_date=date, end_date=date
                )
                if result:
                    self.kline_storage.save_kline_batch(result)
                    saved = True
            except Exception as e:
                logger.error(f"backfill {code} {date}: {e}")
            with lock:
                cnt["success" if saved else "failed"] += 1
                cnt["done"] += 1
                if cnt["done"] % 10 == 0 or cnt["done"] == total:
                    task.update_progress(cnt["done"], total, cnt["success"], cnt["failed"])

        max_workers = Settings.get_max_concurrent()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(backfill_one, missing))

        task.complete(cnt["success"], cnt["failed"])

    def _identify_missing_data(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> List[tuple]:
        trading_days = get_trading_days(start_date, end_date)
        missing = []

        for code in codes:
            earliest, latest = self.kline_storage.get_kline_range(code)
            if not earliest:
                missing.extend([(code, d) for d in trading_days])
                continue

            existing_dates = {
                r["date"]
                for r in self.kline_storage.find_many({"code": code})
                if "date" in r
            }
            for day in trading_days:
                if day not in existing_dates:
                    missing.append((code, day))

        return missing

    # ------------------------------------------------------------------ #
    # 股票基础信息                                                           #
    # ------------------------------------------------------------------ #

    def _execute_stock_info_task(self, task: Task):
        codes = task.params.get("codes", [])
        mode = task.params.get("mode", "incremental")  # incremental | full
        collector = self._get_collector(TaskType.STOCK_INFO_COLLECTION.value)
        if not codes:
            codes = collector.get_all_stock_codes()

        if mode == "incremental":
            existing = set(self.stock_info_storage.distinct("code"))
            before = len(codes)
            codes = [c for c in codes if c not in existing]
            logger.info(f"stock_info incremental: {before} total, {len(existing)} in DB, {len(codes)} to fetch")

        def collect_fn(code):
            return collector.execute_with_retry(collector.collect_single, code)

        self._parallel_collect(
            task, codes,
            collect_fn=collect_fn,
            save_fn=lambda r: self.stock_info_storage.save_stock_info(
                r if isinstance(r, dict) else r[0] if r else {}
            ),
        )

    # ------------------------------------------------------------------ #
    # 财务数据                                                              #
    # ------------------------------------------------------------------ #

    def _execute_financial_task(self, task: Task):
        codes = task.params.get("codes", [])
        report_type = task.params.get("report_type", "annual")
        mode = task.params.get("mode", "incremental")  # incremental | full
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        collector = self._get_collector(TaskType.FINANCIAL_COLLECTION.value)
        if not codes:
            codes = collector.get_all_stock_codes()

        from core.storage.mongo_storage import FinancialStorage
        storage = FinancialStorage()

        if mode == "incremental":
            existing = set(storage.distinct("code"))
            before = len(codes)
            codes = [c for c in codes if c not in existing]
            logger.info(f"financial incremental: {before} total, {len(existing)} in DB, {len(codes)} to fetch")

        def collect_fn(code):
            return collector.execute_with_retry(
                collector.collect_single, code,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
            )

        self._parallel_collect(
            task, codes,
            collect_fn=collect_fn,
            save_fn=lambda r: storage.save_financial_batch(r if isinstance(r, list) else [r]),
        )

    # ------------------------------------------------------------------ #
    # 新闻舆情                                                              #
    # ------------------------------------------------------------------ #

    def _execute_news_task(self, task: Task):
        limit = task.params.get("limit", 100)
        collector = self._get_collector(TaskType.NEWS_COLLECTION.value)

        from core.storage.mongo_storage import NewsStorage
        storage = NewsStorage()

        task.update_progress(0, 1, 0, 0)
        try:
            records = collector.collect(limit=limit)
            if records:
                storage.save_news_batch(records)
            task.complete(len(records), 0)
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 资金流向                                                              #
    # ------------------------------------------------------------------ #

    def _execute_fund_flow_task(self, task: Task):
        """
        资金流向采集策略（非东财，规避代理拦截）：
        1. 大单成交明细（stock_fund_flow_big_deal）— 当日全市场大单，约5000条
        2. 行业资金流（stock_fund_flow_industry "即时"）— 90个行业板块快照
        """
        import akshare as ak
        from core.storage.mongo_storage import FundFlowStorage
        from datetime import datetime
        storage = FundFlowStorage()

        task.update_progress(0, 2, 0, 0)
        success, failed = 0, 0

        # 1. 大单成交明细（字段映射：股票代码→code, 成交时间取日期部分→date）
        try:
            df = ak.stock_fund_flow_big_deal()
            if df is not None and not df.empty:
                today = datetime.now().strftime("%Y-%m-%d")
                df["code"] = df["股票代码"].astype(str) if "股票代码" in df.columns else ""
                df["date"] = df["成交时间"].astype(str).str[:10] if "成交时间" in df.columns else today
                df["_updated_at"] = datetime.now()
                records = df.to_dict("records")
                storage.save_fund_flow_batch(records)
                success += len(records)
                logger.info(f"Fund flow big deal: saved {len(records)} records")
        except Exception as e:
            failed += 1
            logger.warning(f"stock_fund_flow_big_deal failed: {e}")

        task.update_progress(1, 2, success, failed)

        # 2. 行业板块资金流
        collector = self._get_collector(TaskType.FUND_FLOW_COLLECTION.value)
        try:
            df = collector.collect_sector_flow()
            if df is not None and not df.empty:
                df["_updated_at"] = datetime.now()
                records = df.to_dict("records")
                storage.save_fund_flow_batch(records)
                success += len(records)
                logger.info(f"Fund flow sector: saved {len(records)} records")
        except Exception as e:
            failed += 1
            logger.warning(f"collect_sector_flow failed: {e}")

        task.complete(success, failed)

    # ------------------------------------------------------------------ #
    # 指数成分                                                              #
    # ------------------------------------------------------------------ #

    def _execute_index_task(self, task: Task):
        index_codes = task.params.get("index_codes")
        collector = self._get_collector(TaskType.INDEX_COLLECTION.value)
        task.update_progress(0, 1, 0, 0)
        try:
            results = collector.collect(index_codes=index_codes)
            task.complete(results.get("success", 0), results.get("failed", 0))
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 龙虎榜                                                               #
    # ------------------------------------------------------------------ #

    def _execute_dragon_tiger_task(self, task: Task):
        start_date = task.params.get("start_date")
        end_date = task.params.get("end_date")
        date = task.params.get("date")
        collector = self._get_collector(TaskType.DRAGON_TIGER_COLLECTION.value)
        task.update_progress(0, 1, 0, 0)
        try:
            records = collector.collect(date=date, start_date=start_date, end_date=end_date)
            task.complete(len(records), 0)
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 板块资金流                                                            #
    # ------------------------------------------------------------------ #

    def _execute_sector_task(self, task: Task):
        collector = self._get_collector(TaskType.FUND_FLOW_COLLECTION.value)
        from core.storage.mongo_storage import BlockStorage
        storage = BlockStorage()
        task.update_progress(0, 1, 0, 0)
        try:
            df = collector.collect_sector_flow()
            if df is not None and not df.empty:
                df["block_type"] = "sector"
                df["_updated_at"] = datetime.now()
                records = df.to_dict("records")
                for record in records:
                    storage.save_block(record)
                task.complete(len(records), 0)
            else:
                task.complete(0, 0)
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 两融数据                                                              #
    # ------------------------------------------------------------------ #

    def _execute_margin_task(self, task: Task):
        start_date = task.params.get("start_date", "20260101")
        end_date = task.params.get("end_date", datetime.now().strftime("%Y%m%d"))
        # 转换日期格式：2026-01-01 -> 20260101
        start_date = start_date.replace("-", "")
        end_date = end_date.replace("-", "")

        collector = self._get_collector(TaskType.MARGIN_COLLECTION.value)
        from core.storage.mongo_storage import MarginStorage
        storage = MarginStorage()

        task.update_progress(0, 1, 0, 0)
        try:
            records = collector.collect_detailed_margin(
                start_date=start_date,
                end_date=end_date
            )
            if records:
                storage.save_margin_batch(records)
            task.complete(len(records), 0)
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 板块数据                                                              #
    # ------------------------------------------------------------------ #

    def _execute_block_task(self, task: Task):
        collector = self._get_collector(TaskType.BLOCK_COLLECTION.value)
        task.update_progress(0, 1, 0, 0)
        try:
            records = collector.collect()
            task.complete(len(records), 0)
        except Exception as e:
            task.fail(str(e))

    # ------------------------------------------------------------------ #
    # 监控：超时任务自动取消                                                  #
    # ------------------------------------------------------------------ #

    def _start_monitor(self):
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

    def _monitor_loop(self):
        while True:
            try:
                now = datetime.now()
                with self._lock:
                    for task_id, task in list(self._tasks.items()):
                        if task.status == TaskStatus.RUNNING and task.start_time:
                            elapsed = (now - task.start_time).total_seconds()
                            if elapsed > _TASK_TIMEOUT_SECONDS:
                                logger.warning(
                                    f"Task {task_id} timed out ({elapsed:.0f}s), cancelling"
                                )
                                task.cancel()
                # 清理 7 天前已完成的任务（防内存泄漏）
                self._gc_tasks()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(60)

    def _gc_tasks(self):
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=7 * 24)
        with self._lock:
            stale = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                and t.end_time and t.end_time < cutoff
            ]
            for tid in stale:
                del self._tasks[tid]

    def _on_task_done(self, task_id: str, future: Future):
        """Future 回调：只处理未捕获的异常，不删任务对象"""
        exc = future.exception()
        if exc:
            logger.error(f"Task {task_id} future raised: {exc}")

    # ------------------------------------------------------------------ #
    # 调度器主循环（可选启动，若需要自动拉起 pending 任务）                     #
    # ------------------------------------------------------------------ #

    def start_scheduler(self):
        if self._running:
            return
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        logger.info("TaskScheduler background loop started")

    def stop_scheduler(self):
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        self._executor.shutdown(wait=False)
        logger.info("TaskScheduler stopped")

    def _run_scheduler(self):
        while self._running:
            try:
                pending_tasks = self.task_storage.get_pending_tasks()
                for task_info in pending_tasks:
                    task_id = task_info.get("task_id")
                    if task_id not in self._tasks:
                        task = Task(
                            task_id,
                            task_info.get("task_type"),
                            task_info.get("params", {}),
                            self.task_storage,
                        )
                        with self._lock:
                            self._tasks[task_id] = task
                        self.start_task(task_id)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            time.sleep(5)

    # ------------------------------------------------------------------ #
    # 统计                                                                  #
    # ------------------------------------------------------------------ #

    def get_task_statistics(self) -> Dict[str, Any]:
        in_mem = list(self._tasks.values())
        running = sum(1 for t in in_mem if t.status == TaskStatus.RUNNING)
        pending = sum(1 for t in in_mem if t.status == TaskStatus.PENDING)
        return {
            "running_tasks": running,
            "pending_tasks": pending,
            "active_tasks": len(in_mem),
            "thread_pool_max": 10,
            "concurrent_limit": Settings.get_max_concurrent(),
            "metrics": self.metrics.get_stats(),
            "timestamp": datetime.now().isoformat(),
        }


scheduler = TaskScheduler()
