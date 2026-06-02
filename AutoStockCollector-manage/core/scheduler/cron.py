"""进程内定时调度：工作日盘后自动触发数据采集任务。
用纯 Python threading 实现，无需外部 schedule 库。
同类型任务在前一次未完成时自动跳过（防止重叠执行）。
"""
import time
import threading
import datetime
from collections import deque as _deque
from utils.logger import get_logger

logger = get_logger(__name__)

_started = False
_schedule_lock = threading.Lock()

_job_history: dict = {}
_history_lock = threading.Lock()

# 注册的任务列表（start_daily_jobs 后填充）
_registered_jobs: list = []
_jobs_lock = threading.Lock()


def _record_result(label: str, ok: bool, msg: str = "") -> None:
    with _history_lock:
        if label not in _job_history:
            _job_history[label] = _deque(maxlen=5)
        _job_history[label].append({
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": ok,
            "msg": msg,
        })


def get_cron_status() -> list:
    """返回所有定时任务的当前状态（供 API 调用）。"""
    with _jobs_lock:
        jobs_snapshot = list(_registered_jobs)

    result = []
    with _history_lock:
        for job in jobs_snapshot:
            label = job["label"]
            history = list(_job_history.get(label, []))
            last = history[-1] if history else None
            consecutive_failures = 0
            for h in reversed(history):
                if not h["ok"]:
                    consecutive_failures += 1
                else:
                    break
            next_run = job.get("next_run")
            result.append({
                "label": label,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None,
                "last_run": last["time"] if last else None,
                "last_ok": last["ok"] if last else None,
                "last_msg": last.get("msg", "") if last else "",
                "consecutive_failures": consecutive_failures,
                "alert": consecutive_failures >= 2,
            })
    return result


def _is_weekday() -> bool:
    return datetime.datetime.now().weekday() < 5


def _is_task_running(task_type: str) -> bool:
    try:
        from core.scheduler.scheduler import scheduler
        tasks = scheduler.list_tasks(limit=200)
        return any(
            t.get("task_type") == task_type and t.get("status") in ("running", "pending")
            for t in tasks
        )
    except Exception:
        return False


def _trigger_task(task_type: str, params: dict, label: str = "") -> None:
    _label = label or task_type
    try:
        if _is_task_running(task_type):
            logger.info(f"[cron] {_label} 已有任务运行中，跳过")
            _record_result(_label, ok=True, msg="skipped: already running")
            return
        from core.scheduler.scheduler import scheduler
        task_id = scheduler.create_task(task_type, params)
        scheduler.start_task(task_id)
        logger.info(f"[cron] {_label} 任务已触发: {task_id}")
        _record_result(_label, ok=True, msg=f"triggered: {task_id}")
    except Exception as e:
        logger.error(f"[cron] {_label} 触发失败: {e}")
        _record_result(_label, ok=False, msg=str(e))


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


# ─── 每日盘后任务 ──────────────────────────────────────────────────────────────

def job_kline_incremental():
    if not _is_weekday():
        return
    today = _today()
    _trigger_task("kline", {"start_date": today, "end_date": today, "adjust": "qfq"}, "K线增量")


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
    _trigger_task("margin", {"start_date": today, "end_date": today}, "融资融券")


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
    if datetime.datetime.now().weekday() != 0:
        return
    _trigger_task("stock_info", {"mode": "full"}, "股票信息全量刷新")


def job_financial_quarterly():
    if not _is_weekday():
        return
    now = datetime.datetime.now()
    if now.month not in (1, 4, 8, 10):
        return
    if now.day > 7:
        return
    end_date = now.strftime("%Y-%m-%d")
    start_date = f"{now.year - 1}-01-01"
    _trigger_task("financial", {
        "report_type": "annual",
        "start_date": start_date,
        "end_date": end_date,
    }, "财务数据季度采集")


# ─── AI 选股 ──────────────────────────────────────────────────────────────────

import os as _os

def get_cron_time() -> str:
    return _os.environ.get("AI_PICK_CRON_TIME", "15:30")


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


# ─── 纯 Python 调度核心 ───────────────────────────────────────────────────────

def _next_daily_run(hour: int, minute: int) -> datetime.datetime:
    """计算下次每日定时触发时间（HH:MM）。"""
    now = datetime.datetime.now()
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += datetime.timedelta(days=1)
    return scheduled


def _next_hourly_run(at_minute: int) -> datetime.datetime:
    """计算下次整点 :MM 触发时间。"""
    now = datetime.datetime.now()
    scheduled = now.replace(minute=at_minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled += datetime.timedelta(hours=1)
    return scheduled


def _make_job(label: str, handler, kind: str, hour: int = 0, minute: int = 0) -> dict:
    """构建任务描述字典。kind: 'daily' | 'hourly'"""
    if kind == "daily":
        next_run = _next_daily_run(hour, minute)
    else:
        next_run = _next_hourly_run(minute)
    return {
        "label": label,
        "handler": handler,
        "kind": kind,
        "hour": hour,
        "minute": minute,
        "next_run": next_run,
    }


def _advance_next_run(job: dict) -> None:
    """任务执行后更新 next_run。"""
    if job["kind"] == "daily":
        job["next_run"] = _next_daily_run(job["hour"], job["minute"])
    else:
        job["next_run"] = _next_hourly_run(job["minute"])


def _scheduler_loop() -> None:
    while True:
        try:
            now = datetime.datetime.now()
            with _jobs_lock:
                due = [j for j in _registered_jobs if j["next_run"] <= now]

            for job in due:
                try:
                    job["handler"]()
                except Exception as e:
                    logger.warning(f"[cron] {job['label']} 执行异常: {e}")
                with _jobs_lock:
                    _advance_next_run(job)

        except Exception as e:
            logger.warning(f"[cron] scheduler_loop error: {e}")

        time.sleep(30)


# ─── 启动函数 ─────────────────────────────────────────────────────────────────

def start_daily_jobs() -> None:
    """启动后台 daemon 线程，注册所有定时任务。幂等（重复调用只启动一次）。"""
    global _started
    with _schedule_lock:
        if _started:
            return
        _started = True

    ai_time = get_cron_time()
    try:
        ai_hour, ai_minute = map(int, ai_time.split(":"))
    except Exception:
        ai_hour, ai_minute = 15, 30

    jobs = [
        _make_job("K线增量 16:05",       job_kline_incremental,   "daily", 16, 5),
        _make_job("龙虎榜 16:10",         job_dragon_tiger,        "daily", 16, 10),
        _make_job("资金流向 16:15",       job_fund_flow,           "daily", 16, 15),
        _make_job("融资融券 16:20",       job_margin,              "daily", 16, 20),
        _make_job("板块数据 16:25",       job_sector,              "daily", 16, 25),
        _make_job("新闻增量 整点",        job_news_incremental,    "hourly", 0,  0),
        _make_job("股票信息 周一09:00",   job_stock_info_weekly,   "daily",  9,  0),
        _make_job("财务数据 季度09:30",   job_financial_quarterly, "daily",  9, 30),
        _make_job(f"AI选股 {ai_time}",   _ai_pick_wrapper,        "daily", ai_hour, ai_minute),
    ]

    with _jobs_lock:
        _registered_jobs.clear()
        _registered_jobs.extend(jobs)

    labels = " / ".join(j["label"] for j in jobs)
    logger.info(f"[cron] 定时任务已注册: {labels}")

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="data-cron")
    t.start()
