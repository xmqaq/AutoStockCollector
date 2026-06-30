"""投资研报分析 — Flask Blueprint（异步 + 进度轮询）。"""
import threading
import time
import uuid
from datetime import datetime
from typing import Optional
from flask import Blueprint, jsonify, request
from api.auth_utils import login_required
from utils.logger import get_logger

from .engine import AnalyzerEngine

logger = get_logger(__name__)

research_bp = Blueprint("research", __name__, url_prefix="/api/v1/ai")

_engine: Optional[AnalyzerEngine] = None
_tasks: dict = {}
_tasks_lock = threading.Lock()
_TASK_TTL = 300  # 任务完成/失败后保留秒数


def _evict_stale_tasks():
    """清理过期任务，防止内存泄漏。"""
    now = time.time()
    with _tasks_lock:
        stale = [tid for tid, t in list(_tasks.items())
                 if t.get("completed_at", 0) and now - t["completed_at"] > _TASK_TTL]
        for tid in stale:
            del _tasks[tid]
        if stale:
            logger.info(f"[Research] Evicted {len(stale)} stale tasks")


def _get_engine() -> AnalyzerEngine:
    global _engine
    if _engine is None:
        _engine = AnalyzerEngine()
    return _engine


def _run_analysis(task_id: str, sectors: list, top_n: int):
    """后台执行分析任务。"""
    try:
        _evict_stale_tasks()
        with _tasks_lock:
            _tasks[task_id] = {"status": "processing", "progress": 0, "message": "正在初始化..."}

        eng = _get_engine()

        def progress_cb(pct: int, sector: str):
            with _tasks_lock:
                t = _tasks.get(task_id)
                if t and t.get("status") == "cancelled":
                    return
                _tasks[task_id]["progress"] = pct
                _tasks[task_id]["message"] = f"正在分析: {sector}" if sector else f"进度 {pct}%"

        def cancel_check() -> bool:
            with _tasks_lock:
                return _tasks.get(task_id, {}).get("status") == "cancelled"

        with _tasks_lock:
            _tasks[task_id]["message"] = f"正在分析板块: {', '.join(sectors)}"
            _tasks[task_id]["progress"] = 10

        result = eng.analyze(
            sectors=sectors, top_n=top_n, max_workers=min(len(sectors), 4),
            progress_callback=progress_cb, cancel_check=cancel_check,
        )
        result["task_id"] = task_id

        with _tasks_lock:
            if _tasks.get(task_id, {}).get("status") == "cancelled":
                return
            _tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "分析完成",
                "result": result,
                "completed_at": time.time(),
            }

        # 保存到 MongoDB
        try:
            from config.database import DatabaseConfig
            from .config import ResearchConfig
            db = DatabaseConfig.get_database()
            db[ResearchConfig.RESULTS_COLLECTION].insert_one({
                "task_id": task_id,
                "source": "manual",
                "sectors": sectors,
                "top_n": top_n,
                "result": result,
                "created_at": datetime.now(),
            })
        except Exception as e:
            logger.warning(f"[ResearchAnalyzer] Save result failed: {e}")

    except Exception as e:
        logger.error(f"[ResearchAnalyzer] Task {task_id} failed: {e}")
        with _tasks_lock:
            _tasks[task_id] = {"status": "failed", "progress": 0, "message": str(e), "completed_at": time.time()}


@research_bp.route("/research-analysis", methods=["POST"])
@login_required
def research_analysis():
    """启动投资研报分析（异步）。返回 task_id，前端轮询进度。"""
    data = request.get_json(silent=True) or {}
    sectors = data.get("sectors", [])
    if not sectors or not isinstance(sectors, list):
        return jsonify({"success": False, "error": "请至少指定一个行业板块"}), 400
    if len(sectors) > 10:
        return jsonify({"success": False, "error": "单次最多分析10个板块"}), 400

    try:
        top_n = int(data.get("top_n", 10))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "top_n 必须为整数"}), 400
    if not (5 <= top_n <= 100):
        return jsonify({"success": False, "error": "top_n 范围 5-100"}), 400

    # 缓存命中检查 — 同行业+同日期已完成的直接返回
    try:
        from datetime import date
        from config.database import DatabaseConfig
        from .config import ResearchConfig
        db = DatabaseConfig.get_database()
        today = date.today().isoformat()[:10]
        existing = db[ResearchConfig.RESULTS_COLLECTION].find_one(
            {"sectors": sorted(sectors), "created_at": {"$gte": today}},
            sort=[("created_at", -1)],
        )
        if existing and existing.get("result"):
            existing.pop("_id", None)
            return jsonify({
                "success": True,
                "task_id": existing.get("task_id", ""),
                "message": "命中缓存，直接返回",
                "data": existing["result"],
                "cached": True,
            })
    except Exception:
        pass

    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "progress": 0, "message": "任务已提交"}

    thread = threading.Thread(target=_run_analysis, args=(task_id, sectors, top_n), daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "分析任务已提交，请轮询进度",
    })


@research_bp.route("/research-analysis/result/<task_id>", methods=["GET"])
@login_required
def get_result(task_id: str):
    """轮询分析进度 / 获取结果。"""
    with _tasks_lock:
        task = _tasks.get(task_id)

    if task is None:
        return jsonify({"success": False, "error": "任务不存在或已过期"}), 404

    resp = {
        "success": True,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "message": task.get("message", ""),
    }
    if task["status"] == "completed" and "result" in task:
        resp["data"] = task["result"]

    return jsonify(resp)


@research_bp.route("/research-analysis/cancel/<task_id>", methods=["POST"])
@login_required
def cancel_analysis(task_id: str):
    """取消正在进行的分析任务。"""
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        if task["status"] in ("completed", "failed", "cancelled"):
            return jsonify({"success": False, "error": f"任务已{task['status']}"}), 400
        task["status"] = "cancelled"
        task["message"] = "任务已取消"
    logger.info(f"[ResearchAnalyzer] Task {task_id} cancelled by user")
    return jsonify({"success": True, "message": "任务已取消"})


@research_bp.route("/research-analysis/export/<task_id>", methods=["GET"])
@login_required
def export_report(task_id: str):
    """导出研报简报为 Markdown 文件。"""
    try:
        from config.database import DatabaseConfig
        from .config import ResearchConfig
        db = DatabaseConfig.get_database()
        doc = db[ResearchConfig.RESULTS_COLLECTION].find_one(
            {"task_id": task_id},
            {"result.report_md": 1, "sectors": 1},
        )
        if not doc:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        report_md = doc.get("result", {}).get("report_md", "暂无简报内容")
        sectors = "-".join(doc.get("sectors", ["unknown"]))
        filename = f"研报简报_{sectors}.md"
        from flask import make_response
        from urllib.parse import quote
        resp = make_response(report_md)
        resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
        resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return resp
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] export error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@research_bp.route("/research-analysis/sectors", methods=["GET"])
@login_required
def list_sectors():
    """返回支持分析的行业板块列表（从 chain_templates.json 动态加载）。"""
    try:
        from .supply_chain import SupplyChainAggregator
        agg = SupplyChainAggregator()
        sectors = agg.list_sectors()
        return jsonify({"success": True, "count": len(sectors), "data": sectors})
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] list sectors error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@research_bp.route("/research-analysis/history", methods=["GET"])
@login_required
def get_history():
    """获取最近的分析历史记录。"""
    try:
        from config.database import DatabaseConfig
        from .config import ResearchConfig

        db = DatabaseConfig.get_database()
        docs = list(
            db[ResearchConfig.RESULTS_COLLECTION]
            .find()
            .sort("created_at", -1)
            .limit(20)
        )
        for d in docs:
            d.pop("_id", None)
        return jsonify({"success": True, "count": len(docs), "data": docs})
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] history error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# 今日汇总进程级缓存：cron 一天只生成 1 条，前端高频刷新时避免每次都查 Mongo+sort。
_today_cache: dict = {"payload": None, "at": 0.0, "date": ""}
_TODAY_CACHE_TTL = 60.0


@research_bp.route("/research-analysis/today", methods=["GET"])
@login_required
def get_today_summary():
    """获取今日 cron 自动汇总的研报分析结果（全市场）。

    时区统一用北京时间（与 cron 落库一致），避免非北京服务器查不到今日结果。
    带 60s 进程级缓存；无数据时区分"尚未生成"与"生成中"（查 cron_job_status）。
    """
    try:
        from config.database import DatabaseConfig
        from utils.helpers import beijing_now
        from .config import ResearchConfig

        today = beijing_now().strftime("%Y-%m-%d")

        # 缓存命中（同一天且未过期）直接返回
        now_ts = time.time()
        if (_today_cache["date"] == today
                and _today_cache["payload"] is not None
                and now_ts - _today_cache["at"] < _TODAY_CACHE_TTL):
            return jsonify(_today_cache["payload"])

        db = DatabaseConfig.get_database()
        doc = db[ResearchConfig.RESULTS_COLLECTION].find_one(
            {"source": "cron_daily", "created_at": {"$gte": today}},
            sort=[("created_at", -1)],
        )
        if doc and doc.get("result"):
            doc.pop("_id", None)
            payload = {
                "success": True,
                "data": doc["result"],
                "task_id": doc.get("task_id", ""),
                "created_at": doc.get("created_at"),
                "status": "ready",
            }
            _today_cache["payload"] = payload
            _today_cache["at"] = now_ts
            _today_cache["date"] = today
            return jsonify(payload)

        # 无结果：查 cron_job_status 判断是"还没到点/未生成"、"正在生成中"还是"生成失败"
        # （触发时写 last_ok=None 表示执行中；后台成功写 True、失败写 False）
        status = "pending"
        message = "今日汇总尚未生成，盘后 17:30 自动运行，请稍后刷新"
        try:
            js = db["cron_job_status"].find_one({"task_type": "research_daily"})
            if js and js.get("last_run"):
                last_run_day = str(js.get("last_run", ""))[:10]
                last_ok = js.get("last_ok")
                if last_run_day == today:
                    if last_ok is True:
                        # 状态显示成功但无结果文档：可能 insert 幂等跳过或缓存未刷新，视为就绪兜底
                        status = "pending"
                        message = "今日汇总尚未生成，请稍后刷新"
                    elif last_ok is False:
                        status = "failed"
                        message = "今日研报分析生成失败，请检查日志或手动触发"
                    else:  # None = 后台执行中
                        status = "running"
                        message = "今日研报分析正在生成中，请稍候刷新"
        except Exception:
            pass

        payload = {"success": True, "data": None, "status": status, "message": message}
        # running 状态缓存 60s（避免高频轮询打 Mongo）；failed/pending 不缓存，便于及时拿到重跑结果
        if status == "running":
            _today_cache["payload"] = payload
            _today_cache["at"] = now_ts
            _today_cache["date"] = today
        else:
            _today_cache["payload"] = None
        return jsonify(payload)
    except Exception as e:
        logger.warning(f"[ResearchAnalyzer] today summary error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
