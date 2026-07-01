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


# ─── 指数 K 线 ────────────────────────────────────────────────────────────────

def job_index_kline():
    """采集主流指数日K(上证/深成指/创业板/沪深300)入 kline 集合，供市场状态检测读库。
    工作日盘后 16:10 运行（早于融合选股 16:20）。数据量小，每指数仅保留最近 ~500 条。
    走轻量执行(同估值缓存)，不经 scheduler，状态存 cron_job_status 供采集中心展示。
    """
    if not _is_weekday():
        return
    try:
        import akshare as ak
        from pymongo import UpdateOne
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        # 存库 code 用大写带前缀(与个股一致)；新浪接口 symbol 用小写
        indices = {
            "SH000001": "sh000001",  # 上证指数
            "SZ399001": "sz399001",  # 深证成指
            "SZ399006": "sz399006",  # 创业板指
            "SH000300": "sh000300",  # 沪深300
        }
        total = 0
        for store_code, sina in indices.items():
            try:
                df = ak.stock_zh_index_daily(symbol=sina)
                if df is None or df.empty:
                    continue
                ops = []
                for _, r in df.tail(500).iterrows():
                    d = r.get("date")
                    try:
                        dt = datetime.datetime(d.year, d.month, d.day)
                    except Exception:
                        dt = datetime.datetime.fromisoformat(str(d)[:10])
                    doc = {
                        "code": store_code, "date": dt,
                        "open": float(r.get("open") or 0),
                        "close": float(r.get("close") or 0),
                        "high": float(r.get("high") or 0),
                        "low": float(r.get("low") or 0),
                        "volume": float(r.get("volume") or 0),
                    }
                    ops.append(UpdateOne({"code": store_code, "date": dt},
                                         {"$set": doc}, upsert=True))
                if ops:
                    db["kline"].bulk_write(ops, ordered=False)
                    total += len(ops)
            except Exception as e:
                logger.warning(f"[cron] 指数采集失败 {store_code}: {e}")
        logger.info(f"[cron] 指数K线采集完成，{total} 条")
        _record_result("指数K线 16:10", True, f"采集{total}条")
        _persist_cron_status("index_kline", _now().isoformat(), True, f"采集{total}条", inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 指数K线采集失败: {e}")
        _record_result("指数K线 16:10", False, str(e))
        _persist_cron_status("index_kline", _now().isoformat(), False, str(e)[:100])


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
        # 多用户：给每个有模拟盘账户的 user_id 各记一次快照，单用户失败不影响其他
        uids = account._col.distinct("user_id") or ["default"]
        ok = 0
        for uid in uids:
            try:
                snapshot.record(uid, account, engine)
                ok += 1
            except Exception as e:
                logger.warning(f"[cron] 净值快照失败 user={uid}: {e}")
        msg = f"快照记录完成 {ok}/{len(uids)} 用户"
        logger.info(f"[cron] {msg}")
        _record_result("净值快照 16:30", True, msg)
        _persist_cron_status("portfolio_snapshot", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.warning(f"[cron] 净值快照失败: {e}")
        _record_result("净值快照 16:30", False, str(e))
        _persist_cron_status("portfolio_snapshot", _now().isoformat(), False, str(e))


def job_monitor_intraday_refresh():
    """盘中买卖点刷新：只更新持仓 + 自选股的深度分析，跳过智选追踪/过期清理
    （那两步每天智选完成后级联跑一次即可，盘中不必重复）。逐用户隔离失败。"""
    try:
        from modules.monitor.engine import MonitorEngine
        from config.database import DatabaseConfig
        engine = MonitorEngine()
        uids = DatabaseConfig.get_database()["paper_account"].distinct("user_id") or ["default"]
        ok = 0
        for uid in uids:
            try:
                engine.refresh_all(uid, sync_fusion=False)
                ok += 1
            except Exception as e:
                logger.error(f"[cron] 监控盘中刷新失败 user={uid}: {e}")
        logger.info(f"[cron] 监控盘中刷新完成 {ok}/{len(uids)} 用户")
    except Exception as e:
        logger.error(f"[cron] 监控盘中刷新失败: {e}")


def job_strategy_pick():
    """定时策略选股：交易日 08:55 / 12:00 / 14:30 自动运行所有选股策略。"""
    if not _is_weekday():
        return
    try:
        from modules.ai.strategies.storage import StrategyStorage
        storage = StrategyStorage()
        strategies = storage.list_by_type("selection", enabled_only=True)
        strategy_ids = [str(s["_id"]) for s in strategies]
        if not strategy_ids:
            logger.info("[cron] 定时策略选股: 无可用选股策略，跳过")
            return

        from api.routes.strategy_pick import _acquire_run_lock, _run_pipeline
        if not _acquire_run_lock():
            logger.info("[cron] 定时策略选股: 已有任务运行中，跳过本次")
            return

        import threading
        t = threading.Thread(
            target=_run_pipeline,
            args=(strategy_ids, 20, 15, [], [], "default"),
            daemon=True,
        )
        t.start()
        logger.info(f"[cron] 定时策略选股已启动: {len(strategy_ids)} 个策略")
    except Exception as e:
        logger.error(f"[cron] 定时策略选股失败: {e}")


# ─── 融合选股 ────────────────────────────────────────────────────────────────

def job_fusion_pick_daily():
    """每日盘后完整版融合选股，16:20 运行（K线和资金流向采集完成后）"""
    if not _is_weekday():
        return
    try:
        from modules.ai.fusion.engine import FusionPickerEngine
        from modules.ai.fusion.progress import acquire_run_lock
        if not acquire_run_lock():
            logger.info("[cron] 融合选股已有任务运行中，跳过")
            return
        engine = FusionPickerEngine()
        engine.run(top_n=10, candidate_pool=50, mode="full")
        logger.info("[cron] 融合选股完成")
        _persist_cron_status("fusion_pick", _now().isoformat(), True, "完成")
        # 智选完成后级联刷新监控：同步智选追踪 + 过期清理 + 全量买卖点
        try:
            from modules.monitor.engine import MonitorEngine
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            user_ids = db["paper_account"].distinct("user_id") or ["default"]
            mengine = MonitorEngine()
            for uid in user_ids:
                try:
                    mengine.refresh_all(uid)
                except Exception as e:
                    logger.error(f"[cron] 监控刷新失败 user={uid}: {e}")
        except Exception as e:
            logger.error(f"[cron] 智选级联监控刷新失败: {e}")
    except Exception as e:
        logger.error(f"[cron] 融合选股失败: {e}")
        _persist_cron_status("fusion_pick", _now().isoformat(), False, str(e)[:80])


def job_fusion_pick_quick():
    """盘中快速版融合选股，检测到资金异动时触发"""
    if not _is_weekday():
        return
    now = _now()
    hour_min = now.hour * 100 + now.minute
    # 只在交易时间内运行
    if not (930 <= hour_min <= 1130 or 1300 <= hour_min <= 1500):
        return
    try:
        from config.database import DatabaseConfig
        import numpy as np
        db = DatabaseConfig.get_database()
        # 检测今日是否有大量资金异动（Z-score > 2 的股票数 > 30）
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        pipe = [
            {"$match": {"date": {"$gte": cutoff}}},
            {"$sort": {"date": -1}},
            {"$group": {
                "_id": "$code",
                "nets": {"$push": "$main_net_inflow"},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gte": 2}}},
        ]
        anomaly_count = 0
        for doc in db["fund_flow"].aggregate(pipe, allowDiskUse=True):
            nets = [float(x or 0) for x in doc["nets"] if x is not None]
            if len(nets) < 2:
                continue
            avg = sum(nets) / len(nets)
            std = (sum((x - avg)**2 for x in nets) / len(nets)) ** 0.5
            if std > 0 and abs((nets[0] - avg) / std) > 2:
                anomaly_count += 1
        # 异动股票数 > 30 才触发快速选股
        if anomaly_count < 30:
            return
        logger.info(f"[cron] 检测到 {anomaly_count} 只股票资金异动，触发快速融合选股")
        from modules.ai.fusion.engine import FusionPickerEngine
        from modules.ai.fusion.progress import acquire_run_lock
        if not acquire_run_lock():
            return
        engine = FusionPickerEngine()
        engine.run(top_n=5, candidate_pool=20, mode="quick")
        _persist_cron_status("fusion_pick_quick", _now().isoformat(),
                             True, f"异动触发，{anomaly_count}只异动股")
    except Exception as e:
        logger.error(f"[cron] 快速融合选股失败: {e}")


def job_fusion_weight_optimize():
    """每周一凌晨 3:00 运行一次权重优化"""
    if _now().weekday() != 0:
        return
    try:
        from modules.ai.fusion.weight_optimizer import WeightOptimizer
        result = WeightOptimizer().run()
        if result.get("skipped"):
            logger.info(f"[cron] 融合选股权重优化跳过: {result.get('reason')}")
        else:
            logger.info(f"[cron] 融合选股权重优化完成: {result.get('states_updated')}")
        _persist_cron_status("fusion_weight_optimize",
                             _now().isoformat(), True, str(result.get("states_updated", [])))
    except Exception as e:
        logger.error(f"[cron] 融合选股权重优化失败: {e}")


# ─── 个股新闻舆情 + 热点发现 ──────────────────────────────────────────────────

def job_collect_watchlist_news():
    """交易日 09:00 / 11:30 / 13:00 / 15:30 对监控名单做个股精确新闻/公告采集。
    轻量执行（不经 scheduler），状态存 cron_job_status 供采集中心展示。"""
    if not _is_weekday():
        return
    try:
        from core.collector.news_collector import NewsCollector
        collector = NewsCollector()
        codes = collector.watchlist_codes()
        if not codes:
            logger.info("[cron] 个股新闻采集：监控名单为空，跳过")
            _persist_cron_status("watchlist_news", _now().isoformat(), True, "名单为空", inc_count=True)
            return
        ann = collector.collect_watchlist_announcements(codes)
        news = collector.collect_watchlist_stock_news(codes)
        msg = f"{len(codes)}只，公告{len(ann)}条/新闻{len(news)}条"
        logger.info(f"[cron] 个股新闻采集完成：{msg}")
        _record_result("个股新闻采集", True, msg)
        _persist_cron_status("watchlist_news", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 个股新闻采集失败: {e}")
        _record_result("个股新闻采集", False, str(e))
        _persist_cron_status("watchlist_news", _now().isoformat(), False, str(e)[:100])


def job_monitor_realtime_refresh():
    """盘中每 3 分钟刷新池中股票实时行情 + 即时资金流，写 monitor_realtime。
    仅连续竞价时段执行（非交易时段无实时数据）。"""
    try:
        from modules.monitor.realtime import RealtimeRefresher
        from modules.monitor.engine import MonitorEngine
        from modules.paper_trading.account import PaperAccount
        from config.database import DatabaseConfig
        from utils.helpers import is_trading_day, beijing_now
        if not is_trading_day(beijing_now()):
            return
        db = DatabaseConfig.get_database()
        uids = db["paper_account"].distinct("user_id") or ["default"]
        total = 0
        for uid in uids:
            try:
                r = RealtimeRefresher().refresh(uid)
                total += r.get("refreshed", 0)
            except Exception as e:
                logger.warning(f"[cron] realtime refresh user={uid} failed: {e}")
        if total:
            msg = f"实时数据刷新{total}只"
            logger.info(f"[cron] {msg}")
            _record_result("监控实时刷新", True, msg)
    except Exception as e:
        logger.error(f"[cron] 监控实时刷新失败: {e}")
        _record_result("监控实时刷新", False, str(e))


def job_monitor_ai_predict():
    """盘中对池中股票做 LLM 预测：开盘(9:35)/收盘(14:50) 各触发一次，
    对持仓+异动股生成 AI 买卖建议（控成本：当日同股缓存 + 每日 limit）。"""
    try:
        from modules.monitor.ai_advisor import LLMAiAdvisor
        from modules.monitor.engine import MonitorEngine
        from modules.paper_trading.account import PaperAccount
        from config.database import DatabaseConfig
        from utils.helpers import is_trading_day, beijing_now
        if not is_trading_day(beijing_now()):
            return
        db = DatabaseConfig.get_database()
        uids = db["paper_account"].distinct("user_id") or ["default"]
        predicted = 0
        for uid in uids:
            try:
                stocks = MonitorEngine()._collect_stocks(uid)
                # 优先预测持仓股 + 智选/投研股（成本可控）
                codes = [s["code"] for s in stocks
                         if {"position", "fusion_pick", "research"} & set(s.get("sources") or [])]
                codes = codes[:20]  # 单次上限，控成本
                r = LLMAiAdvisor().predict_pool(codes, trigger="cron")
                predicted += r.get("predicted", 0)
            except Exception as e:
                logger.warning(f"[cron] ai predict user={uid} failed: {e}")
        msg = f"AI预测{predicted}只"
        logger.info(f"[cron] {msg}")
        _record_result("监控AI预测", True, msg)
        _persist_cron_status("monitor_ai_predict", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 监控AI预测失败: {e}")
        _record_result("监控AI预测", False, str(e))
        _persist_cron_status("monitor_ai_predict", _now().isoformat(), False, str(e)[:100])


# ─── 价格行为学全市场扫描 ────────────────────────────────────────────────────

def job_pa_intraday_scan():
    """盘中每 30 分钟扫描 PA 信号（9:35-15:00）。"""
    if not _is_weekday():
        return
    now = _now()
    hour_min = now.hour * 100 + now.minute
    if not (935 <= hour_min <= 1130 or 1300 <= hour_min <= 1500):
        return
    try:
        from modules.price_action_advisor.api import _SCAN_UNIVERSE, _run_scan
        import uuid
        scan_id = uuid.uuid4().hex[:12]
        threading.Thread(
            target=_run_scan,
            args=(scan_id, _SCAN_UNIVERSE, "30m", 0.02, 100000),
            daemon=True,
        ).start()
        msg = "PA盘中扫描已启动（30m周期）"
        logger.info(f"[cron] {msg}")
        _record_result("PA盘中扫描", True, msg)
        _persist_cron_status("pa_intraday_scan", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] PA盘中扫描失败: {e}")
        _record_result("PA盘中扫描", False, str(e))
        _persist_cron_status("pa_intraday_scan", _now().isoformat(), False, str(e)[:100])


def job_pa_scan():
    """每日盘后扫描全市场 PA 信号。"""
    if not _is_weekday():
        return
    try:
        from modules.price_action_advisor.api import _SCAN_UNIVERSE, _run_scan
        import uuid
        scan_id = uuid.uuid4().hex[:12]
        threading.Thread(
            target=_run_scan,
            args=(scan_id, _SCAN_UNIVERSE, "daily", 0.02, 100000),
            daemon=True,
        ).start()
        msg = "PA全市场扫描已启动"
        logger.info(f"[cron] {msg}")
        _record_result("PA全市场扫描", True, msg)
        _persist_cron_status("pa_scan", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] PA扫描失败: {e}")
        _record_result("PA全市场扫描", False, str(e))
        _persist_cron_status("pa_scan", _now().isoformat(), False, str(e)[:100])


# ─── 投资研报每日全板块扫描 ────────────────────────────────────────────────────

def job_research_daily():
    """每日盘后自动扫描所有板块研报，汇总落库（后台线程执行，不阻塞调度循环）。"""
    if not _is_weekday():
        return
    try:
        threading.Thread(target=_run_research_daily, daemon=True).start()
        msg = "研报全板块扫描已启动（后台）"
        logger.info(f"[cron] {msg}")
        _record_result("研报全板块扫描", True, msg)
        # 触发时只标记"后台执行中"（last_ok=None），真正结果由 _run_research_daily
        # 成功落库后写 True / 失败写 False。避免触发即 True 导致前端误判"生成中"。
        _persist_cron_status("research_daily", _now().isoformat(), None, msg, inc_count=False)
    except Exception as e:
        logger.error(f"[cron] 研报扫描启动失败: {e}")
        _record_result("研报全板块扫描", False, str(e))
        _persist_cron_status("research_daily", _now().isoformat(), False, str(e)[:100])


def _today_beijing() -> str:
    """北京时间日期字符串 YYYY-MM-DD，与 _now() 落库时区一致，避免幂等/查询错位。"""
    return _now().strftime("%Y-%m-%d")


def _run_research_daily():
    """后台执行：27 板块分批分析 → 跨批合并 → 落库 research_analysis_results(source=cron_daily)。

    幂等：今日已生成则跳过。失败板块跳过、汇总可用结果。
    """
    try:
        from config.database import DatabaseConfig
        from modules.ai_research_report_analyzer.supply_chain import SupplyChainAggregator
        from modules.ai_research_report_analyzer.engine import AnalyzerEngine
        from modules.ai_research_report_analyzer.config import ResearchConfig

        today = _today_beijing()
        db = DatabaseConfig.get_database()

        # 幂等：今日已有 cron_daily 汇总则跳过
        existing = db[ResearchConfig.RESULTS_COLLECTION].find_one(
            {"source": "cron_daily", "created_at": {"$gte": today}},
        )
        if existing:
            logger.info("[cron] 研报扫描：今日已生成汇总，跳过")
            return

        # 前置检查：今日新研报入库数（注意 research_report_collect 18:00 才跑，
        # 17:30 本任务主要依赖历史 90 天窗口；此处仅记录新鲜度，不阻断产出）
        try:
            today_new = db["research_reports"].count_documents({"date": today})
            logger.info(f"[cron] 研报扫描：今日新研报 {today_new} 条（历史窗口 90 天）")
        except Exception:
            pass

        agg = SupplyChainAggregator()
        sectors = [s["name"] for s in agg.list_sectors()]
        if not sectors:
            logger.info("[cron] 研报扫描：无可用板块，跳过")
            return

        batch_size = 5
        batch_results = []
        eng = AnalyzerEngine()
        # max_workers=3 板块内并发降耗时；synthesize=False 跳过批内简报（合并阶段统一合成，省 6 次 LLM）
        for i in range(0, len(sectors), batch_size):
            batch = sectors[i:i + batch_size]
            try:
                result = eng.analyze(
                    sectors=batch, top_n=10, max_workers=3,
                    synthesize=False, enrich=False,
                )
                batch_results.append(result)
                logger.info(f"[cron] 研报扫描完成批次 {i//batch_size+1}: {', '.join(batch)}")
            except Exception as e:
                logger.warning(f"[cron] 研报扫描批次失败 {batch}: {e}")

        if not batch_results:
            logger.warning("[cron] 研报扫描：所有批次失败，无汇总")
            _persist_cron_status("research_daily", _now().isoformat(), False, "所有批次失败")
            return

        # 跨批合并
        merged = eng.merge_batch_results(batch_results, top_n=30)
        failed = merged.get("failed_sectors", [])
        ok_count = len(sectors) - len(failed)
        task_id = f"daily_{today.replace('-', '')}"

        try:
            db[ResearchConfig.RESULTS_COLLECTION].insert_one({
                "task_id": task_id,
                "source": "cron_daily",
                "sectors": ["全市场"],
                "top_n": 30,
                "result": merged,
                "created_at": _now(),
            })
        except Exception as dup_err:
            # task_id 唯一索引冲突（今日已有同名文档，如手动触发过）视为幂等成功，不算失败
            if "duplicate key" in str(dup_err).lower() or "E11000" in str(dup_err):
                logger.info(f"[cron] 研报扫描：今日文档已存在({task_id})，幂等跳过")
            else:
                raise

        msg = f"扫描 {len(sectors)} 板块完成(成功{ok_count}/失败{len(failed)})，候选 {merged.get('candidate_count', 0)} 只"
        logger.info(f"[cron] {msg}")
        _record_result("研报全板块扫描", True, msg)
        _persist_cron_status("research_daily", _now().isoformat(), True, msg, inc_count=True)

        # 级联：投研候选落库后刷新监控（让 research 来源股票进入监控池），仿 fusion_pick_daily
        try:
            from modules.monitor.engine import MonitorEngine
            from config.database import DatabaseConfig
            for uid in DatabaseConfig.get_database()["paper_account"].distinct("user_id") or ["default"]:
                try:
                    MonitorEngine().refresh_all(uid)
                except Exception as ce:
                    logger.warning(f"[cron] research→monitor cascade user={uid} failed: {ce}")
        except Exception as ce:
            logger.warning(f"[cron] research→monitor cascade failed: {ce}")
    except Exception as e:
        logger.error(f"[cron] 研报扫描后台任务失败: {e}")
        _record_result("研报全板块扫描", False, str(e))
        _persist_cron_status("research_daily", _now().isoformat(), False, str(e)[:100])


def job_research_report_collect():
    """每日盘后采集全量研报并存入 research_reports 集合。"""
    if not _is_weekday():
        return
    try:
        from modules.research_report_collector import collect_all_reports
        result = collect_all_reports()
        msg = f"采集 {result.get('total_fetched', 0)} 条研报，新保存 {result.get('total_saved', 0)} 条"
        logger.info(f"[cron] {msg}")
        _record_result("研报数据采集", True, msg)
        _persist_cron_status("research_report_collect", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 研报数据采集失败: {e}")
        _record_result("研报数据采集", False, str(e))
        _persist_cron_status("research_report_collect", _now().isoformat(), False, str(e)[:100])


def job_research_report_summarize():
    """盘中持续摘要未处理的研报，每次处理 10 篇。"""
    try:
        from modules.research_report_collector.summarizer import summarize_pending_reports
        result = summarize_pending_reports(max_reports=20, delay=12)
        msg = f"摘要 {result.get('summarized', 0)} / {result.get('total', 0)} 篇"
        logger.info(f"[cron] {msg}")
        _record_result("研报AI摘要", True, msg)
        _persist_cron_status("research_report_summarize", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 研报AI摘要失败: {e}")
        _record_result("研报AI摘要", False, str(e))
        _persist_cron_status("research_report_summarize", _now().isoformat(), False, str(e)[:100])


def job_auction_radar():
    """每日 9:25 盘前竞价雷达扫描。"""
    if not _is_weekday():
        return
    from utils.helpers import is_trading_day
    if not is_trading_day(_now()):
        logger.info("[cron] 今日非交易日，跳过竞价雷达扫描")
        return
    try:
        from modules.pre_market_call_auction.radar_service import run_auction_scan
        import threading
        threading.Thread(target=run_auction_scan, daemon=True).start()
        msg = "盘前竞价雷达已启动"
        logger.info(f"[cron] {msg}")
        _record_result("盘前竞价雷达", True, msg)
        _persist_cron_status("auction_radar", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 盘前竞价雷达失败: {e}")
        _record_result("盘前竞价雷达", False, str(e))
        _persist_cron_status("auction_radar", _now().isoformat(), False, str(e)[:100])


def job_auction_auto_close():
    """14:50 自动平仓今日竞价雷达买入的仓位。"""
    if not _is_weekday():
        return
    from utils.helpers import is_trading_day
    if not is_trading_day(_now()):
        logger.info("[cron] 今日非交易日，跳过自动平仓")
        return
    try:
        # 14:50 委托 auto_trading.run_cycle：DecisionEngine 的 eod_close_intraday 分支
        # 会对竞价日内持仓强制平仓（force 豁免 T+1）。auto_trading 不可用时回退到 signal_emitter。
        try:
            from modules.auto_trading.executor import UnifiedAutoTrader
            result = UnifiedAutoTrader().run_cycle()
            closed = result.get("sells", 0)
        except Exception:
            from modules.pre_market_call_auction.signal_emitter import auto_close_positions
            closed = auto_close_positions()
        msg = f"竞价雷达自动平仓{closed}笔"
        logger.info(f"[cron] {msg}")
        _record_result("竞价雷达自动平仓", True, msg)
        _persist_cron_status("auction_auto_close", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 竞价雷达自动平仓失败: {e}")
        _record_result("竞价雷达自动平仓", False, str(e))
        _persist_cron_status("auction_auto_close", _now().isoformat(), False, str(e)[:100])


def job_auction_intraday_refresh():
    """盘中每 3 分钟刷新竞价雷达追踪股票的实时盈亏（bug2 修复：原仅 API 懒触发）。"""
    if not _is_weekday():
        return
    now = _now()
    hour_min = now.hour * 100 + now.minute
    # 仅连续竞价时段：9:35-11:30 / 13:00-14:55
    if not (935 <= hour_min <= 1130 or 1300 <= hour_min <= 1455):
        return
    from utils.helpers import is_trading_day
    if not is_trading_day(now):
        return
    try:
        from modules.pre_market_call_auction.intraday_pricer import IntradayPricer
        updated = IntradayPricer().update_realtime()
        msg = f"竞价盘中刷新{updated}条"
        if updated:
            logger.info(f"[cron] {msg}")
            _record_result("竞价盘中刷新", True, msg)
            _persist_cron_status("auction_intraday_refresh", now.isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 竞价盘中刷新失败: {e}")
        _record_result("竞价盘中刷新", False, str(e))
        _persist_cron_status("auction_intraday_refresh", now.isoformat(), False, str(e)[:100])


def job_paper_match_pending():
    """模拟盘盘中撮合：扫所有 pending 订单，取实时价成交。仅连续竞价时段生效。"""
    try:
        from modules.paper_trading.trade_engine import TradeEngine, is_trading_time
        if not is_trading_time():
            return
        engine = TradeEngine()
        matched = engine._match_pending_orders()
        if matched:
            msg = f"模拟盘撮合成交{matched}笔"
            logger.info(f"[cron] {msg}")
            _record_result("模拟盘盘中撮合", True, msg)
            _persist_cron_status("paper_match", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 模拟盘盘中撮合失败: {e}")
        _record_result("模拟盘盘中撮合", False, str(e))


def job_paper_market_close_settle():
    """模拟盘收盘清算：15:00 撤所有未成交挂单并解冻资金。"""
    try:
        from utils.helpers import is_trading_day, beijing_now
        if not is_trading_day(beijing_now()):
            return
        from modules.paper_trading.trade_engine import TradeEngine
        engine = TradeEngine()
        cancelled = engine._market_close_settle()
        msg = f"模拟盘收盘清算撤单{cancelled}笔"
        logger.info(f"[cron] {msg}")
        _record_result("模拟盘收盘清算", True, msg)
        _persist_cron_status("paper_close_settle", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 模拟盘收盘清算失败: {e}")
        _record_result("模拟盘收盘清算", False, str(e))
        _persist_cron_status("paper_close_settle", _now().isoformat(), False, str(e)[:100])


def job_auto_trading_cycle():
    """自动交易融合轮询 30min。"""
    if not _is_weekday():
        return
    from utils.helpers import is_trading_day
    if not is_trading_day(_now()):
        logger.info("[cron] 今日非交易日，跳过自动交易轮询")
        return
    now = _now()
    if now.hour < 9 or (now.hour == 9 and now.minute < 35) or now.hour >= 15:
        logger.info("[cron] 非盘中时段，跳过自动交易轮询")
        return
    try:
        from modules.auto_trading.executor import UnifiedAutoTrader
        result = UnifiedAutoTrader().run_cycle()
        buys = result.get("buys", 0)
        sells = result.get("sells", 0)
        adds = result.get("adds", 0)
        errors = result.get("errors", 0)
        msg = f"自动交易轮询: {buys}买/{sells}卖/{adds}加仓, {errors}错误"
        logger.info(f"[cron] {msg}")
        _record_result("自动交易", True, msg)
        _persist_cron_status("auto_trading", _now().isoformat(), True, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] 自动交易轮询失败: {e}")
        _record_result("自动交易", False, str(e))
        _persist_cron_status("auto_trading", _now().isoformat(), False, str(e)[:100])


# ─── Agent 信号刷新 ──────────────────────────────────────────────────────────

AGENT_SIGNAL_MAX_CODES = 30  # 单轮 LLM 成本硬上限：TradingGraph 单只 8-10 次调用


def job_agent_signal_refresh():
    """盘前/盘中刷新 agent 信号 → agent_signals 集合（后台线程，不阻塞调度循环）。

    错峰于 auto_trading(:00/:30) 与 monitor(10:00/13:30/14:45)：9:05 给当日首信号，
    13:05 盘中刷新一次。每日 2 轮 × 最多 30 只，成本可控。
    """
    if not _is_weekday():
        return
    from utils.helpers import is_trading_day
    if not is_trading_day(_now()):
        logger.info("[cron] 今日非交易日，跳过 Agent 信号刷新")
        return
    now = _now()
    # 9:00 前太早（数据未就绪），15:00 后盘后不再刷新（次日再说）
    if now.hour < 9 or now.hour >= 15:
        logger.info("[cron] 非盘中时段，跳过 Agent 信号刷新")
        return
    try:
        threading.Thread(target=_run_agent_signal_refresh, daemon=True).start()
        msg = "Agent 信号刷新已启动（后台）"
        logger.info(f"[cron] {msg}")
        _record_result("Agent信号刷新", True, msg)
        _persist_cron_status("agent_signal", _now().isoformat(), None, msg, inc_count=False)
    except Exception as e:
        logger.error(f"[cron] Agent 信号刷新启动失败: {e}")
        _record_result("Agent信号刷新", False, str(e))
        _persist_cron_status("agent_signal", _now().isoformat(), False, str(e)[:100])


def _collect_agent_signal_codes(trade_date: str):
    """收集待刷新 code 列表：竞价雷达 top + 持仓 + 融合选股 top，去重，截断 30。"""
    from config.database import DatabaseConfig
    from modules.paper_trading.trade_engine import TradeEngine
    from modules.pre_market_call_auction.radar_utils import strip_prefix_from_code as _strip_prefix_from_code

    db = DatabaseConfig.get_database()
    codes = []

    # 1) 竞价雷达当日 top 20
    try:
        result = db["auction_results"].find_one(
            {"date": trade_date}, sort=[("created_at", -1)]
        )
        for s in (result.get("top_stocks", []) or [])[:20]:
            code = _strip_prefix_from_code(s.get("symbol", ""))
            if code:
                codes.append(code)
    except Exception as e:
        logger.warning(f"[cron] agent signal: auction codes fetch failed: {e}")

    # 2) 当前持仓
    try:
        engine = TradeEngine()
        positions, _ = engine.get_positions("default")
        for p in positions or []:
            code = _strip_prefix_from_code(p.get("code", ""))
            if code:
                codes.append(code)
    except Exception as e:
        logger.warning(f"[cron] agent signal: positions fetch failed: {e}")

    # 3) 融合选股当日 top 10
    try:
        fp = db["fusion_pick_results"].find_one(
            {}, sort=[("created_at", -1)]
        )
        for pick in (fp.get("picks", []) or [])[:10]:
            code = _strip_prefix_from_code(pick.get("code", ""))
            if code:
                codes.append(code)
    except Exception as e:
        logger.warning(f"[cron] agent signal: fusion_pick codes fetch failed: {e}")

    # 去重保序，截断硬上限
    seen, unique = set(), []
    for c in codes:
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
        if len(unique) >= AGENT_SIGNAL_MAX_CODES:
            break
    return unique


def _run_agent_signal_refresh():
    """后台执行：对收集到的 code 逐只跑 TradingGraph，写 agent_signals。

    单只失败跳过不阻断；幂等（upsert by code+trade_date）。
    """
    try:
        from modules.ai.orchestration.graph import TradingGraph
        from modules.ai.orchestration.agent_signal_writer import write_agent_signal

        trade_date = _today_beijing()
        codes = _collect_agent_signal_codes(trade_date)
        if not codes:
            msg = "Agent 信号刷新：无可刷新 code（竞价/持仓/选股均空）"
            logger.info(f"[cron] {msg}")
            _record_result("Agent信号刷新", True, msg)
            _persist_cron_status("agent_signal", _now().isoformat(), True, msg)
            return

        graph = TradingGraph()
        ok, fail = 0, 0
        for code in codes:
            try:
                result = graph.run(code)
                write_agent_signal(
                    result.get("verdict") or {},
                    result.get("final_decision") or {},
                    trade_date,
                )
                ok += 1
            except Exception as e:
                fail += 1
                logger.warning(f"[cron] agent signal: {code} failed: {e}")

        msg = f"Agent 信号刷新完成：{ok} 成功 / {fail} 失败 / 共 {len(codes)} 只"
        logger.info(f"[cron] {msg}")
        _record_result("Agent信号刷新", fail == 0, msg)
        _persist_cron_status("agent_signal", _now().isoformat(), fail == 0, msg, inc_count=True)
    except Exception as e:
        logger.error(f"[cron] Agent 信号刷新后台执行失败: {e}")
        _record_result("Agent信号刷新", False, str(e))
        _persist_cron_status("agent_signal", _now().isoformat(), False, str(e)[:100])


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

    jobs = [
        _make_job("K线增量 16:05",       job_kline_incremental,   "daily", 16, 5,  task_type="kline"),
        _make_job("K线缺口回补 17:30",    job_kline_gap_backfill,  "daily", 17, 30, task_type="kline"),
        _make_job("K线缺口回补 21:45",    job_kline_gap_backfill,  "daily", 21, 45, task_type="kline"),
        _make_job("龙虎榜 19:00",         job_dragon_tiger,        "daily", 19, 0,  task_type="dragon_tiger"),
        _make_job("资金流向 16:15",       job_fund_flow,           "daily", 16, 15, task_type="fund_flow"),
        _make_job("融资融券 21:30",       job_margin,              "daily", 21, 30, task_type="margin"),
        _make_job("板块数据 16:25",       job_sector,              "daily", 16, 25, task_type="sector"),
        _make_job("指数K线 16:10",        job_index_kline,         "daily", 16, 10, task_type="index_kline"),
        _make_job("新闻增量 整点",        job_news_incremental,    "hourly", 0,  0,  task_type="news"),
        _make_job("股票信息 周一09:00",   job_stock_info_weekly,   "daily",  9,  0,  task_type="stock_info"),
        _make_job("财务数据 季度09:30",   job_financial_quarterly, "daily",  9, 30, task_type="financial"),
        _make_job(f"AI选股 {ai_time}",   _ai_pick_wrapper,        "daily", ai_hour, ai_minute, task_type="ai_pick"),
        _make_job("净值快照 16:30",       job_portfolio_snapshot,  "daily", 16, 30, task_type="portfolio_snapshot"),
        _make_job("估值缓存 5min",       job_valuation_cache,     "interval", interval_minutes=5, task_type="valuation_cache"),
        _make_job("任务清理 03:30",      job_task_cleanup,        "daily",  3, 30, task_type="task_cleanup"),
        _make_job("监控盘中刷新 10:00", job_monitor_intraday_refresh, "daily", 10, 0,  task_type="monitor_intraday"),
        _make_job("监控盘中刷新 13:30", job_monitor_intraday_refresh, "daily", 13, 30, task_type="monitor_intraday"),
        _make_job("监控盘中刷新 14:45", job_monitor_intraday_refresh, "daily", 14, 45, task_type="monitor_intraday"),
        # 策略选股 08:55/12:00/14:30 已下线：前端入口与页面移除，输出仅该页面消费，停掉定时空跑。
        # job_strategy_pick 函数体暂留，待旧选股系统整体退役时一并清理。
        _make_job("融合选股 16:20",      job_fusion_pick_daily,    "daily",    16, 20,
                  task_type="fusion_pick"),
        _make_job("融合选股 快速盘中",   job_fusion_pick_quick,    "interval",
                  interval_minutes=15, task_type="fusion_pick_quick"),
        _make_job("融合选股 权重优化",   job_fusion_weight_optimize, "daily",   3, 0,
                  task_type="fusion_weight_optimize"),
        _make_job("个股新闻采集 09:00", job_collect_watchlist_news, "daily",  9,  0, task_type="watchlist_news"),
        _make_job("个股新闻采集 11:30", job_collect_watchlist_news, "daily", 11, 30, task_type="watchlist_news"),
        _make_job("个股新闻采集 13:00", job_collect_watchlist_news, "daily", 13,  0, task_type="watchlist_news"),
        _make_job("个股新闻采集 15:30", job_collect_watchlist_news, "daily", 15, 30, task_type="watchlist_news"),
        _make_job("监控实时刷新 3min", job_monitor_realtime_refresh, "interval",
                  interval_minutes=3, task_type="monitor_realtime"),
        _make_job("监控AI预测 09:35", job_monitor_ai_predict, "daily", 9, 35, task_type="monitor_ai_predict"),
        _make_job("监控AI预测 14:50", job_monitor_ai_predict, "daily", 14, 50, task_type="monitor_ai_predict"),
        _make_job("PA盘中扫描 30min",  job_pa_intraday_scan,        "interval", interval_minutes=30, task_type="pa_intraday_scan"),
        _make_job("PA全市场扫描 17:00", job_pa_scan,                "daily", 17,  0, task_type="pa_scan"),
        _make_job("研报全板块扫描 17:30", job_research_daily,       "daily", 17, 30, task_type="research_daily"),
        _make_job("研报原始数据采集 16:30", job_research_report_collect, "daily", 16, 30, task_type="research_report_collect"),
        _make_job("研报AI摘要 30min",       job_research_report_summarize, "interval", interval_minutes=30, task_type="research_report_summarize"),
        _make_job("盘前竞价雷达 09:32",     job_auction_radar,           "daily", 9, 32, task_type="auction_radar"),
        _make_job("竞价自动平仓 14:50",     job_auction_auto_close,      "daily", 14, 50, task_type="auction_auto_close"),
        _make_job("竞价盘中刷新 3min",      job_auction_intraday_refresh, "interval", interval_minutes=3, task_type="auction_intraday_refresh"),
        _make_job("模拟盘盘中撮合 1min",    job_paper_match_pending,     "interval", interval_minutes=1, task_type="paper_match"),
        _make_job("模拟盘收盘清算 15:00",   job_paper_market_close_settle, "daily", 15, 0, task_type="paper_close_settle"),
        _make_job("自动交易轮询 30min",     job_auto_trading_cycle,       "interval",
                  interval_minutes=30, task_type="auto_trading"),
        _make_job("Agent信号刷新 09:05", job_agent_signal_refresh, "daily", 9, 5, task_type="agent_signal"),
        _make_job("Agent信号刷新 13:05", job_agent_signal_refresh, "daily", 13, 5, task_type="agent_signal"),
    ]

    # cron_trigger_lock 跨进程触发锁：建 TTL 索引，锁文档 1 天后自动过期，避免无限增长。
    try:
        from config.database import DatabaseConfig
        DatabaseConfig.get_database()["cron_trigger_lock"].create_index("at", expireAfterSeconds=86400)
    except Exception as e:
        logger.debug(f"[cron] trigger_lock TTL index skipped: {e}")

    # agent_signals 集合 TTL：7 天自动过期，防止历史信号无限堆积。
    try:
        from config.database import DatabaseConfig
        DatabaseConfig.get_database()["agent_signals"].create_index(
            "updated_at", expireAfterSeconds=7 * 86400
        )
    except Exception as e:
        logger.debug(f"[cron] agent_signals TTL index skipped: {e}")

    with _jobs_lock:
        _registered_jobs.clear()
        _registered_jobs.extend(jobs)

    # 从 MongoDB 恢复调度状态，使重启后 next_run 不丢失
    _restore_next_run()

    labels = " / ".join(j["label"] for j in jobs)
    logger.info(f"[cron] 定时任务已注册: {labels}")

    t = threading.Thread(target=_scheduler_loop, daemon=True, name="data-cron")
    t.start()
