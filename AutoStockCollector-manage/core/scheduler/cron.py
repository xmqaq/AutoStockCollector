"""进程内定时调度：工作日盘后自动触发数据采集任务。
用 schedule 库 + 后台 daemon 线程。所有任务均写入 task 集合，在采集中心任务历史中可见。
同类型任务在前一次未完成时自动跳过（防止重叠执行）。
"""
import os
import time
import threading
import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

_started = False
_schedule_lock = threading.Lock()

# 每个定时任务的执行结果记录 (label → deque of {"time": str, "ok": bool, "msg": str})
from collections import deque as _deque
_job_history: dict = {}   # label → deque(maxlen=5)
_history_lock = threading.Lock()


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
    try:
        import schedule as _sch
        jobs = _sch.get_jobs()
    except Exception:
        return []

    result = []
    with _history_lock:
        for job in jobs:
            label = next(iter(job.tags), "unknown") if job.tags else "unknown"
            history = list(_job_history.get(label, []))
            last = history[-1] if history else None
            # 判断连续失败次数
            consecutive_failures = 0
            for h in reversed(history):
                if not h["ok"]:
                    consecutive_failures += 1
                else:
                    break
            result.append({
                "label": label,
                "next_run": job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else None,
                "last_run": last["time"] if last else None,
                "last_ok": last["ok"] if last else None,
                "last_msg": last.get("msg", "") if last else "",
                "consecutive_failures": consecutive_failures,
                "alert": consecutive_failures >= 2,
            })
    return result


def _is_weekday() -> bool:
    return datetime.datetime.now().weekday() < 5  # 周一~周五


def _is_task_running(task_type: str) -> bool:
    """检查指定类型是否有任务正在运行或等待中。"""
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
    """创建并启动一个采集任务，已有同类运行中则跳过，记录执行结果。"""
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


# ─── 每日盘后任务 ───────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


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
    """每小时增量抓取新闻。"""
    _trigger_task("news", {"max_pages": 5, "with_content": True}, "新闻增量")


def job_stock_info_weekly():
    """每周一全量刷新股票信息。"""
    if not _is_weekday():
        return
    if datetime.datetime.now().weekday() != 0:  # 只在周一
        return
    _trigger_task("stock_info", {"mode": "full"}, "股票信息全量刷新")


def job_financial_quarterly():
    """季报发布月（1/4/8/10月）触发财务数据采集。"""
    if not _is_weekday():
        return
    now = datetime.datetime.now()
    if now.month not in (1, 4, 8, 10):
        return
    # 只在月份首个工作日触发（day <= 7 且是工作日）
    if now.day > 7:
        return
    end_date = now.strftime("%Y-%m-%d")
    start_date = f"{now.year - 1}-01-01"  # 补近一年季报
    _trigger_task("financial", {
        "report_type": "annual",
        "start_date": start_date,
        "end_date": end_date,
    }, "财务数据季度采集")


# ─── AI 选股任务（原有逻辑保留）────────────────────────────────────────────

def get_cron_time() -> str:
    return os.environ.get("AI_PICK_CRON_TIME", "15:30")


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


# ─── 启动函数 ─────────────────────────────────────────────────────────────

def start_daily_jobs() -> None:
    """启动后台 daemon 线程，注册所有定时任务。幂等（重复调用只启动一次）。"""
    global _started
    with _schedule_lock:
        if _started:
            return
        _started = True

    import schedule

    # 每日盘后（工作日）
    schedule.every().day.at("16:05").do(job_kline_incremental).tag("K线增量 16:05")
    schedule.every().day.at("16:10").do(job_dragon_tiger).tag("龙虎榜 16:10")
    schedule.every().day.at("16:15").do(job_fund_flow).tag("资金流向 16:15")
    schedule.every().day.at("16:20").do(job_margin).tag("融资融券 16:20")
    schedule.every().day.at("16:25").do(job_sector).tag("板块数据 16:25")

    # 低频任务
    schedule.every().hour.at(":00").do(job_news_incremental).tag("新闻增量 整点")
    schedule.every().day.at("09:00").do(job_stock_info_weekly).tag("股票信息 周一09:00")
    schedule.every().day.at("09:30").do(job_financial_quarterly).tag("财务数据 季度09:30")

    # AI 选股（原有）
    ai_time = get_cron_time()
    schedule.every().day.at(ai_time).do(_ai_pick_wrapper).tag(f"AI选股 {ai_time}")

    logger.info(
        f"[cron] 定时任务已注册: K线16:05 / 龙虎榜16:10 / 资金流向16:15 / "
        f"融资融券16:20 / 板块16:25 / 新闻整点 / 股票信息周一09:00 / "
        f"财务季度09:30 / AI选股{ai_time}"
    )

    def _loop():
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.warning(f"schedule.run_pending error: {e}")
            time.sleep(30)

    t = threading.Thread(target=_loop, daemon=True, name="data-cron")
    t.start()
