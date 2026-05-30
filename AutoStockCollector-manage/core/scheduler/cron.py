"""进程内每日定时调度：工作日盘后自动触发 AI 选股(ai_pick)任务。
用 schedule 库 + 后台 daemon 线程。job 逻辑与线程分离便于测试。
"""
import os
import time
import threading
from utils.logger import get_logger

logger = get_logger(__name__)

_started = False


def get_cron_time() -> str:
    """每日触发时间，默认 15:30（A股盘后），env AI_PICK_CRON_TIME 可覆盖。"""
    return os.environ.get("AI_PICK_CRON_TIME", "15:30")


def run_ai_pick_job(scheduler=None) -> None:
    """创建并启动一个 ai_pick 任务。失败不抛出（避免崩溃定时线程）。"""
    try:
        if scheduler is None:
            from core.scheduler.scheduler import scheduler as _sched
            scheduler = _sched
        task_id = scheduler.create_task("ai_pick", {"strategy": "default", "top_n": 10, "candidate_pool": 50})
        scheduler.start_task(task_id)
        logger.info(f"Daily ai_pick task triggered: {task_id}")
    except Exception as e:
        logger.warning(f"Daily ai_pick job failed: {e}")


def _is_weekday() -> bool:
    import datetime
    return datetime.datetime.now().weekday() < 5  # 0-4 = 周一到周五


def _job_wrapper() -> None:
    if _is_weekday():
        run_ai_pick_job()


def start_daily_jobs() -> None:
    """启动后台 daemon 线程，每日定时跑 ai_pick。幂等（重复调用只启动一次）。"""
    global _started
    if _started:
        return
    _started = True

    import schedule
    cron_time = get_cron_time()
    schedule.every().day.at(cron_time).do(_job_wrapper)
    logger.info(f"Daily ai_pick scheduler registered at {cron_time} (weekdays)")

    def _loop():
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.warning(f"schedule.run_pending error: {e}")
            time.sleep(30)

    t = threading.Thread(target=_loop, daemon=True, name="ai-pick-cron")
    t.start()
