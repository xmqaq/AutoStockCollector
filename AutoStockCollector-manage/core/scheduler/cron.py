"""进程内定时调度：工作日盘后自动触发数据采集任务。
用纯 Python threading 实现，无需外部 schedule 库。
同类型任务在前一次未完成时自动跳过（防止重叠执行）。
"""
import time
import threading
import datetime
from collections import deque as _deque
from zoneinfo import ZoneInfo
from utils.logger import get_logger

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _now() -> datetime.datetime:
    """北京时间 naive datetime，不依赖系统时区。"""
    return datetime.datetime.now(_BEIJING_TZ).replace(tzinfo=None)

logger = get_logger(__name__)

_started = False
_schedule_lock = threading.Lock()

_job_history: dict = {}
_history_lock = threading.Lock()

# 注册的任务列表（start_daily_jobs 后填充）
_registered_jobs: list = []
_jobs_lock = threading.Lock()

_SCHEDULE_COLLECTION = "cron_schedule"
_STATUS_COLLECTION = "cron_job_status"


def _get_cron_collection():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()[_SCHEDULE_COLLECTION]


def _get_status_collection():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()[_STATUS_COLLECTION]


def _persist_cron_status(task_type: str, last_run: str, last_ok: bool, last_msg: str,
                         inc_count: bool = False):
    """将定时任务的执行状态独立存储到 cron_job_status，不依赖 task_history。
    inc_count=True 时才递增 run_count（仅在任务真正完成时调用一次）。
    """
    try:
        col = _get_status_collection()
        update = {"$set": {
            "task_type": task_type,
            "last_run": last_run,
            "last_ok": last_ok,
            "last_msg": last_msg,
            "updated_at": _now().isoformat(),
        }}
        if inc_count:
            update["$inc"] = {"run_count": 1}
        col.update_one({"task_type": task_type}, update, upsert=True)
    except Exception as e:
        logger.warning(f"[cron] persist cron status failed: {e}")


def _load_cron_status(task_type: str) -> dict:
    """从 cron_job_status 读取独立保存的状态（用于 task_history 被清空后回退）。"""
    try:
        col = _get_status_collection()
        return col.find_one({"task_type": task_type}, {"_id": 0}) or {}
    except Exception:
        return {}


def get_all_cron_run_counts() -> dict:
    """批量读取所有 task_type 的 run_count，减少查询次数。"""
    try:
        col = _get_status_collection()
        return {doc["task_type"]: doc for doc in col.find({}, {"_id": 0})}
    except Exception:
        return {}


def _persist_schedule():
    """将当前调度状态写入 MongoDB，服务重启后可恢复。
    使用 upsert 逐条更新，避免 delete_many+insert_many 的竞态和 duplicate key 错误。
    """
    try:
        col = _get_cron_collection()
        with _jobs_lock:
            if not _registered_jobs:
                return
            docs = [{
                "label": j["label"],
                "kind": j["kind"],
                "hour": j["hour"],
                "minute": j["minute"],
                "interval_minutes": j.get("interval_minutes", 0),
                "next_run": j["next_run"].isoformat(),
                "task_type": j.get("task_type", ""),
            } for j in _registered_jobs]
        for doc in docs:
            col.replace_one({"label": doc["label"]}, doc, upsert=True)
    except Exception as e:
        logger.warning(f"[cron] persist schedule failed: {e}")


def _restore_next_run():
    """从 MongoDB 恢复各任务的 next_run，使重启后调度状态不丢失。
    如果恢复的时间已经过去，则重新计算下次执行时间，防止加载到陈旧值。
    """
    try:
        col = _get_cron_collection()
        saved = {doc["label"]: doc for doc in col.find({})}
        if not saved:
            return
        now = _now()
        with _jobs_lock:
            restored = 0
            for job in _registered_jobs:
                entry = saved.get(job["label"])
                if entry:
                    try:
                        saved_time = datetime.datetime.fromisoformat(entry["next_run"])
                        if saved_time > now:
                            job["next_run"] = saved_time
                        else:
                            _advance_next_run(job)
                        restored += 1
                    except Exception:
                        pass
        if restored:
            logger.info(f"[cron] restored next_run for {restored} jobs from DB")
    except Exception as e:
        logger.warning(f"[cron] restore schedule failed: {e}")


def _record_result(label: str, ok: bool, msg: str = "") -> None:
    with _history_lock:
        if label not in _job_history:
            _job_history[label] = _deque(maxlen=5)
        _job_history[label].append({
            "time": _now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": ok,
            "msg": msg,
        })


def _parse_ts(task_id: str) -> int:
    """从 task_id（如 kline_1779931587433）提取毫秒时间戳用于排序。"""
    try:
        return int(task_id.rsplit("_", 1)[-1])
    except Exception:
        return 0


def _fmt_task_time(raw) -> str:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw[:19].replace('T', ' ')
    if hasattr(raw, "strftime"):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    return str(raw)[:19].replace('T', ' ')


def get_cron_status() -> list:
    """返回所有定时任务的当前状态（供 API 调用）。
    优先从 scheduler 读取最近任务结果；若任务历史已被清空，
    回退到 cron_job_status（独立存储，不随任务历史清空）。
    """
    with _jobs_lock:
        jobs_snapshot = list(_registered_jobs)

    # 从 scheduler（MongoDB）查询各类型最近任务（按 task_id 时间戳倒序）
    tasks_by_type: dict = {}
    try:
        from core.scheduler.scheduler import scheduler
        all_tasks = scheduler.list_tasks(limit=500)
        for task in all_tasks:
            ttype = task.get("task_type")
            if not ttype:
                continue
            tasks_by_type.setdefault(ttype, []).append(task)
        for lst in tasks_by_type.values():
            lst.sort(key=lambda t: _parse_ts(t.get("task_id", "")), reverse=True)
    except Exception:
        pass

    saved_status = get_all_cron_run_counts()

    result = []
    for job in jobs_snapshot:
        label = job["label"]
        task_type = job.get("task_type", "")
        type_tasks = tasks_by_type.get(task_type, []) if task_type else []

        # 计算连续失败次数（基于最近 5 次已完成的任务）
        finished = [t for t in type_tasks if t.get("status") in ("completed", "failed")]
        consecutive_failures = 0
        for t in finished[:5]:
            if t.get("status") == "failed":
                consecutive_failures += 1
            else:
                break

        last_run = None
        last_ok = None
        last_msg = ""
        run_count = 0

        latest = finished[0] if finished else (type_tasks[0] if type_tasks else None)
        if latest:
            status = latest.get("status", "")
            success = latest.get("success", 0)
            failed_cnt = latest.get("failed", 0)
            last_run = _fmt_task_time(latest.get("update_time") or latest.get("end_time") or latest.get("create_time"))

            if status == "completed":
                last_ok = True
                if success == 0:
                    if task_type == "dragon_tiger":
                        last_msg = "今日无龙虎榜数据（非触发日）"
                    elif task_type == "news":
                        last_msg = "该时段暂无新闻"
                    else:
                        last_msg = "今日无数据"
                else:
                    last_msg = f"成功{success}条"
                    if failed_cnt > 0:
                        last_msg += f"，失败{failed_cnt}条"
            elif status == "failed":
                last_ok = False
                last_msg = (latest.get("error_message") or "任务失败")[:80]
            elif status == "running":
                last_ok = None
                progress = latest.get("progress", 0)
                total = latest.get("total", 0)
                last_msg = f"运行中 {progress}/{total}"
            else:
                last_ok = None
                last_msg = ""

            if status in ("completed", "failed") and task_type:
                _persist_cron_status(task_type, last_run, last_ok, last_msg)
        else:
            # 任务历史已清空 → 回退到独立存储的 cron_job_status
            saved = saved_status.get(task_type, {})
            if saved:
                last_run = saved.get("last_run")
                last_ok = saved.get("last_ok")
                last_msg = saved.get("last_msg", "")
            else:
                # 最终回退：内存历史（仅服务启动后首次调用时有用）
                with _history_lock:
                    history = list(_job_history.get(label, []))
                last_hist = history[-1] if history else None
                if last_hist:
                    last_run = last_hist["time"]
                    last_ok = last_hist["ok"]
                    last_msg = last_hist.get("msg", "")

        rc = saved_status.get(task_type, {}).get("run_count", 0)
        run_count = rc if rc else 0

        next_run = job.get("next_run")
        result.append({
            "label": label,
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None,
            "last_run": last_run,
            "last_ok": last_ok,
            "last_msg": last_msg,
            "run_count": run_count,
            "consecutive_failures": consecutive_failures,
            "alert": consecutive_failures >= 2,
        })
    return result


def _is_weekday() -> bool:
    return _now().weekday() < 5


_STALE_TASK_SECONDS = 3600


def _is_task_running(task_type: str) -> bool:
    """检查是否有同类型任务正在运行。
    超过 _STALE_TASK_SECONDS 的 running 任务视为僵尸，不阻塞新任务。
    """
    try:
        from core.scheduler.scheduler import scheduler
        now = _now()
        tasks = scheduler.list_tasks(limit=200)
        for t in tasks:
            if t.get("task_type") != task_type:
                continue
            if t.get("status") not in ("running", "pending"):
                continue
            create_iso = t.get("start_time") or t.get("create_time")
            if create_iso:
                try:
                    create_dt = datetime.datetime.fromisoformat(str(create_iso).replace("Z", "+00:00"))
                    if create_dt.tzinfo:
                        create_dt = create_dt.replace(tzinfo=None)
                    elapsed = (now - create_dt).total_seconds()
                    if elapsed > _STALE_TASK_SECONDS:
                        _cancel_stale_task(scheduler, t.get("task_id"), elapsed)
                        continue
                except Exception:
                    pass
            return True
        return False
    except Exception:
        return False


def _cancel_stale_task(sched, task_id: str, elapsed: float) -> None:
    """将超时的僵尸任务标记为 cancelled，释放后续触发。"""
    try:
        sched.cancel_task(task_id)
        logger.warning(f"[cron] 自动取消僵尸任务 {task_id}（已运行 {elapsed:.0f}s）")
    except Exception as e:
        logger.debug(f"[cron] 取消僵尸任务 {task_id} 失败: {e}")


def _claim_trigger_slot(task_type: str) -> bool:
    """跨进程原子抢占触发槽：同一 task_type 在同一分钟桶内只允许一个进程触发。

    用 MongoDB `_id` 唯一键 insert 实现——重复 insert 触发 DuplicateKeyError，
    即说明本时段已被另一进程/线程抢占（覆盖热重载双进程、多 worker 等场景）。
    `_is_task_running` 依赖"创建→列表里显示 running"非原子，有竞态窗口；
    本方法在创建任务之前先抢锁，把竞态彻底关闭。
    DB 不可用时返回 True（退化为单机 best-effort，不阻塞触发）。
    """
    try:
        from pymongo.errors import DuplicateKeyError
        from config.database import DatabaseConfig
        col = DatabaseConfig.get_database()["cron_trigger_lock"]
        slot = _now().strftime("%Y%m%d%H%M")
        try:
            col.insert_one({"_id": f"{task_type}:{slot}", "at": _now()})
            return True
        except DuplicateKeyError:
            return False
    except Exception:
        return True


def _trigger_task(task_type: str, params: dict, label: str = "") -> None:
    _label = label or task_type
    try:
        if not _claim_trigger_slot(task_type):
            logger.info(f"[cron] {_label} 本分钟已由其他进程/线程触发，跳过")
            _record_result(_label, ok=True, msg="skipped: slot already claimed")
            return
        if _is_task_running(task_type):
            logger.info(f"[cron] {_label} 已有任务运行中，跳过")
            _record_result(_label, ok=True, msg="skipped: already running")
            return
        from core.scheduler.scheduler import scheduler
        task_id = scheduler.create_task(task_type, params)
        scheduler.start_task(task_id)
        logger.info(f"[cron] {_label} 任务已触发: {task_id}")
        _record_result(_label, ok=True, msg=f"triggered: {task_id}")
        _persist_cron_status(task_type, _now().isoformat(), None, "任务已触发")
    except Exception as e:
        logger.error(f"[cron] {_label} 触发失败: {e}")
        _record_result(_label, ok=False, msg=str(e))
        _persist_cron_status(task_type, _now().isoformat(), False, str(e)[:100])


def _today() -> str:
    return _now().strftime("%Y-%m-%d")


# ─── 每日盘后任务 ──────────────────────────────────────────────────────────────

def job_kline_incremental():
    if not _is_weekday():
        return
    today = _today()
    _trigger_task("kline", {"start_date": today, "end_date": today, "adjust": "qfq"}, "K线增量")


def job_kline_gap_backfill():
    """K线缺口自检回补。主采集可能被部署重启打断、或数据源中途失败，
    导致只采到半个市场（2026-06-10/11 实际发生过，缺口 2000+ 只）。
    用 fund_flow（独立数据源）交叉比对，找出"今日在交易但缺今日K线"的
    股票，只对缺口触发增量采集。幂等，可重复执行。"""
    if not _is_weekday():
        return
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        today = _today()
        trading = set(db["fund_flow"].distinct("code", {"date": today}))
        if not trading:
            logger.info("[cron] K线缺口自检：今日无资金流向记录（非交易日或未采集），跳过")
            return
        today_dt = datetime.datetime.strptime(today, "%Y-%m-%d")
        have = set(db["kline"].distinct("code", {"date": today_dt}))
        missing = sorted(c for c in (trading - have) if c)
        if not missing:
            logger.info("[cron] K线缺口自检：无缺口")
            return
        start = (_now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        logger.warning(f"[cron] K线缺口自检：{len(missing)} 只在交易但缺今日K线，触发回补")
        _trigger_task(
            "kline",
            {"codes": missing, "start_date": start, "end_date": today, "adjust": "qfq"},
            f"K线缺口回补({len(missing)}只)",
        )
    except Exception as e:
        logger.error(f"[cron] K线缺口自检失败: {e}")


def job_task_cleanup():
    """清理7天前的已结束任务记录（completed/failed/cancelled）。
    新闻等高频任务每天产生几十条历史，不清理 task 集合会无限增长，
    前端任务历史列表也会越来越长。运行中/排队中的任务不动。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        cutoff = (_now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        res = db["task"].delete_many({
            "status": {"$in": ["completed", "failed", "cancelled"]},
            "create_time": {"$lt": cutoff},
        })
        if res.deleted_count:
            logger.info(f"[cron] 任务清理：删除 {res.deleted_count} 条7天前的已结束任务")
    except Exception as e:
        logger.error(f"[cron] 任务清理失败: {e}")


def job_dragon_tiger():
    if not _is_weekday():
        return
    today = _today()
    _trigger_task("dragon_tiger", {"start_date": today, "end_date": today}, "龙虎榜")


def job_fund_flow():
    if not _is_weekday():
        return
    today = _today()
    _trigger_task("fund_flow", {"date": today}, "资金流向")


def job_margin():
    if not _is_weekday():
        return
    today = _today()
    # 沪深交易所融资融券明细为 T+1 披露：当晚 21:30 取"今天"必为空，
    # 且次日只请求次日 → 前一交易日数据（此时才可得）永远漏采。
    # 改为回看最近 5 个自然日窗口，executor 按已存在日期去重，重复请求安全。
    start = (_now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    _trigger_task("margin", {"start_date": start, "end_date": today}, "融资融券")


def job_sector():
    if not _is_weekday():
        return
    _trigger_task("sector", {}, "板块数据")


# ─── 低频任务 ────────────────────────────────────────────────────────────────

def job_news_incremental():
    _trigger_task("news", {"max_pages": 5, "with_content": True}, "新闻增量")


def job_stock_info_weekly():
    if not _is_weekday():
        return
    if _now().weekday() != 0:
        return
    _trigger_task("stock_info", {"mode": "full"}, "股票信息全量刷新")


def job_financial_quarterly():
    if not _is_weekday():
        return
    now = _now()
    if now.month not in (1, 4, 8, 10):
        return
    # 旧逻辑只跑披露月前 7 天，但定期报告是整月陆续披露（一季报/年报截止 4-30、
    # 半年报 8-31、三季报 10-31），前 7 天几乎抓不到当季报告。
    # 改为覆盖整个披露月：executor 按"已拥有应披露最新报告期"去重，
    # 每日重跑只会拉新披露的增量，成本极低。
    end_date = now.strftime("%Y-%m-%d")
    start_date = f"{now.year - 1}-01-01"
    _trigger_task("financial", {
        "report_type": "annual",
        "start_date": start_date,
        "end_date": end_date,
    }, "财务数据季度采集")


# ─── 估值指标高频缓存 ─────────────────────────────────────────────────────────

def job_valuation_cache():
    """每5分钟刷新全市场估值指标缓存（PE/PB/ROE等），仅工作日盘中执行。"""
    if not _is_weekday():
        return
    now = _now()
    hour_min = now.hour * 100 + now.minute
    if hour_min < 925 or hour_min > 1502:
        return
    try:
        from core.collector.valuation_collector import ValuationCollector
        collector = ValuationCollector()
        count = collector.collect()
        _record_result("估值缓存 5min", True, f"刷新{count}条")
        _persist_cron_status("valuation_cache", now.isoformat(), True, f"刷新{count}条", inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 估值缓存刷新失败: {e}")
        _record_result("估值缓存 5min", False, str(e))
        _persist_cron_status("valuation_cache", now.isoformat(), False, str(e)[:100])


# ─── AI 选股 ──────────────────────────────────────────────────────────────────

import os as _os

def get_cron_time() -> str:
    # 16:15:晚于 K线增量(16:05)/资金流向(16:15)/估值缓存触发，确保选股用的是当日盘后数据。
    # （旧默认 15:30 早于一切盘后采集，选股实际用的是 T-1 数据。）
    return _os.environ.get("AI_PICK_CRON_TIME", "16:15")


def run_ai_pick_job(scheduler=None) -> None:
    try:
        if scheduler is None:
            from core.scheduler.scheduler import scheduler as _sched
            scheduler = _sched
        task_id = scheduler.create_task("ai_pick", {"strategy": "default", "top_n": 10, "candidate_pool": 50})
        scheduler.start_task(task_id)
        logger.info(f"Daily ai_pick task triggered: {task_id}")
    except Exception as e:
        logger.warning(f"Daily ai_pick job failed: {e}")


def _ai_pick_wrapper():
    if _is_weekday():
        run_ai_pick_job()


def job_portfolio_snapshot():
    if not _is_weekday():
        return
    try:
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine
        from modules.paper_trading.snapshot import PortfolioSnapshot
        account = PaperAccount()
        engine = TradeEngine()
        snapshot = PortfolioSnapshot()
        snapshot.record("default", account, engine)
        logger.info("[cron] 净值快照记录成功")
        _record_result("净值快照 16:30", True, "快照记录完成")
        _persist_cron_status("portfolio_snapshot", _now().isoformat(), True, "快照记录完成", inc_count=True)
    except Exception as e:
        logger.warning(f"[cron] 净值快照失败: {e}")
        _record_result("净值快照 16:30", False, str(e))
        _persist_cron_status("portfolio_snapshot", _now().isoformat(), False, str(e))


# ─── 选股工作流定时调度 ────────────────────────────────────────────────────────

def job_workflow_daily():
    """每日定时触发选股工作流。"""
    if not _is_weekday():
        return
    workflow_id = _os.environ.get("DAILY_WORKFLOW_ID", "")
    if not workflow_id:
        logger.info("[cron] 选股工作流: DAILY_WORKFLOW_ID 未设置，跳过")
        return
    try:
        from modules.workflow.models import (
            WorkflowStorage, WorkflowExecutionStorage, WorkflowExecution, ExecutionStatus,
        )
        from modules.workflow.executor import WorkflowExecutor
        import uuid
        from datetime import datetime

        storage = WorkflowStorage()
        workflow = storage.get_workflow(workflow_id)
        if not workflow:
            logger.warning(f"[cron] 选股工作流: workflow {workflow_id} 不存在")
            return
        if not workflow.enabled:
            logger.info(f"[cron] 选股工作流: workflow {workflow_id} 已禁用，跳过")
            return

        exec_storage = WorkflowExecutionStorage()
        existing = exec_storage.get_running_execution(workflow_id)
        if existing:
            logger.info(f"[cron] 选股工作流: workflow {workflow_id} 已有执行中任务，跳过")
            return

        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            status=ExecutionStatus.RUNNING.value,
            progress=0,
            current_node="",
            current_step="准备执行...",
            steps=[],
            started_at=_now().isoformat(),
        )
        exec_storage.create_execution(execution)

        def progress_callback(node_id, node_label, step, progress, detail=None):
            step_data = {
                "node_id": node_id,
                "node_label": node_label,
                "step": step,
                "progress": progress,
                "detail": detail or {},
                "timestamp": _now().isoformat(),
            }
            exec_storage.update_progress(execution_id, progress, node_id, step, step_data)

        def run():
            try:
                nodes = [n.to_dict() for n in workflow.nodes]
                edges = [e.to_dict() for e in workflow.edges]
                executor = WorkflowExecutor(workflow_id, execution_id, progress_callback)
                result = executor.execute(nodes, edges, {})
                if result.get("success"):
                    exec_storage.complete_execution(execution_id, result)
                    storage.update_last_run(workflow_id)
                else:
                    exec_storage.fail_execution(execution_id, result.get("error", "执行失败"))
            except Exception as e:
                import traceback
                logger.error(f"[cron] 选股工作流执行异常: {e}\n{traceback.format_exc()}")
                exec_storage.fail_execution(execution_id, str(e))

        import threading
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        logger.info(f"[cron] 选股工作流 {workflow_id} 已触发: execution_id={execution_id}")
    except Exception as e:
        logger.error(f"[cron] 选股工作流触发失败: {e}")


# ─── 纯 Python 调度核心 ───────────────────────────────────────────────────────

def _next_daily_run(hour: int, minute: int) -> datetime.datetime:
    """计算下次每日定时触发时间（HH:MM）。"""
    now = _now()
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += datetime.timedelta(days=1)
    return scheduled


def _next_hourly_run(at_minute: int) -> datetime.datetime:
    """计算下次整点 :MM 触发时间。"""
    now = _now()
    scheduled = now.replace(minute=at_minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += datetime.timedelta(hours=1)
    return scheduled


def _next_interval_run(interval_minutes: int) -> datetime.datetime:
    """计算下次 N 分钟间隔触发时间。"""
    return _now() + datetime.timedelta(minutes=interval_minutes)


def _make_job(label: str, handler, kind: str, hour: int = 0, minute: int = 0,
              task_type: str = "", interval_minutes: int = 0) -> dict:
    """构建任务描述字典。kind: 'daily' | 'hourly' | 'interval'"""
    if kind == "daily":
        next_run = _next_daily_run(hour, minute)
    elif kind == "interval":
        next_run = _next_interval_run(interval_minutes)
    else:
        next_run = _next_hourly_run(minute)
    return {
        "label": label,
        "handler": handler,
        "kind": kind,
        "hour": hour,
        "minute": minute,
        "interval_minutes": interval_minutes,
        "next_run": next_run,
        "task_type": task_type,
    }


def _advance_next_run(job: dict) -> None:
    """任务执行后更新 next_run。"""
    if job["kind"] == "daily":
        job["next_run"] = _next_daily_run(job["hour"], job["minute"])
    elif job["kind"] == "interval":
        job["next_run"] = _next_interval_run(job.get("interval_minutes", 5))
    else:
        job["next_run"] = _next_hourly_run(job["minute"])


def _scheduler_loop() -> None:
    while True:
        try:
            now = _now()
            with _jobs_lock:
                due = [j for j in _registered_jobs if j["next_run"] <= now]

            if due:
                for job in due:
                    with _jobs_lock:
                        _advance_next_run(job)
                    try:
                        job["handler"]()
                    except Exception as e:
                        logger.warning(f"[cron] {job['label']} 执行异常: {e}")
                _persist_schedule()

        except Exception as e:
            logger.warning(f"[cron] scheduler_loop error: {e}")

        time.sleep(30)


# ─── 启动函数 ─────────────────────────────────────────────────────────────────

def start_daily_jobs() -> None:
    """启动后台 daemon 线程，注册所有定时任务。幂等（重复调用只启动一次）。
    Flask debug reloader 下，主进程（无 WERKZEUG_RUN_MAIN）不启动调度线程，
    只有子进程（WERKZEUG_RUN_MAIN=true）启动，防止双进程重复触发。
    """
    global _started
    if _os.environ.get("WERKZEUG_RUN_MAIN") is None and _os.environ.get("FLASK_DEBUG", "").lower() in ("true", "1"):
        logger.info("[cron] Flask reloader 主进程，跳过调度线程启动")
        return
    with _schedule_lock:
        if _started:
            return
        _started = True

    ai_time = get_cron_time()
    try:
        ai_hour, ai_minute = map(int, ai_time.split(":"))
    except Exception:
        ai_hour, ai_minute = 15, 30

    wf_time = _os.environ.get("DAILY_WORKFLOW_TIME", "17:00")
    try:
        wf_hour, wf_minute = map(int, wf_time.split(":"))
    except Exception:
        wf_hour, wf_minute = 17, 0

    jobs = [
        _make_job("K线增量 16:05",       job_kline_incremental,   "daily", 16, 5,  task_type="kline"),
        _make_job("K线缺口回补 17:30",    job_kline_gap_backfill,  "daily", 17, 30, task_type="kline"),
        _make_job("K线缺口回补 21:45",    job_kline_gap_backfill,  "daily", 21, 45, task_type="kline"),
        _make_job("龙虎榜 19:00",         job_dragon_tiger,        "daily", 19, 0,  task_type="dragon_tiger"),
        _make_job("资金流向 16:15",       job_fund_flow,           "daily", 16, 15, task_type="fund_flow"),
        _make_job("融资融券 21:30",       job_margin,              "daily", 21, 30, task_type="margin"),
        _make_job("板块数据 16:25",       job_sector,              "daily", 16, 25, task_type="sector"),
        _make_job("新闻增量 整点",        job_news_incremental,    "hourly", 0,  0,  task_type="news"),
        _make_job("股票信息 周一09:00",   job_stock_info_weekly,   "daily",  9,  0,  task_type="stock_info"),
        _make_job("财务数据 季度09:30",   job_financial_quarterly, "daily",  9, 30, task_type="financial"),
        _make_job(f"AI选股 {ai_time}",   _ai_pick_wrapper,        "daily", ai_hour, ai_minute, task_type="ai_pick"),
        _make_job("净值快照 16:30",       job_portfolio_snapshot,  "daily", 16, 30, task_type="portfolio_snapshot"),
        _make_job("估值缓存 5min",       job_valuation_cache,     "interval", interval_minutes=5, task_type="valuation_cache"),
        _make_job("任务清理 03:30",      job_task_cleanup,        "daily",  3, 30, task_type="task_cleanup"),
    ]

    # 选股工作流：仅当 DAILY_WORKFLOW_ID 已配置时才注册，否则它每次触发都只是
    # "未设置，跳过"，是个占位空壳，徒增前端定时任务列表一行。
    if _os.environ.get("DAILY_WORKFLOW_ID", "").strip():
        jobs.append(
            _make_job(f"选股工作流 {wf_time}", job_workflow_daily, "daily", wf_hour, wf_minute, task_type="workflow")
        )

    # cron_trigger_lock 跨进程触发锁：建 TTL 索引，锁文档 1 天后自动过期，避免无限增长。
    try:
        from config.database import DatabaseConfig
        DatabaseConfig.get_database()["cron_trigger_lock"].create_index("at", expireAfterSeconds=86400)
    except Exception as e:
        logger.debug(f"[cron] trigger_lock TTL index skipped: {e}")

    with _jobs_lock:
        _registered_jobs.clear()
        _registered_jobs.extend(jobs)

    # 从 MongoDB 恢复调度状态，使重启后 next_run 不丢失
    _restore_next_run()

    labels = " / ".join(j["label"] for j in jobs)
    logger.info(f"[cron] 定时任务已注册: {labels}")

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="data-cron")
    t.start()
