"""投资研报分析 — Flask Blueprint（异步 + 进度轮询）。"""
import threading
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


def _get_engine() -> AnalyzerEngine:
    global _engine
    if _engine is None:
        _engine = AnalyzerEngine()
    return _engine


def _run_analysis(task_id: str, sectors: list, top_n: int):
    """后台执行分析任务。"""
    try:
        with _tasks_lock:
            _tasks[task_id] = {"status": "processing", "progress": 0, "message": "正在初始化..."}

        eng = _get_engine()

        with _tasks_lock:
            _tasks[task_id]["message"] = f"正在分析板块: {', '.join(sectors)}"
            _tasks[task_id]["progress"] = 10

        result = eng.analyze(sectors=sectors, top_n=top_n)
        result["task_id"] = task_id

        with _tasks_lock:
            _tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "分析完成",
                "result": result,
            }

        # 保存到 MongoDB
        try:
            from config.database import DatabaseConfig
            from .config import ResearchConfig
            db = DatabaseConfig.get_database()
            db[ResearchConfig.RESULTS_COLLECTION].insert_one({
                "task_id": task_id,
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
            _tasks[task_id] = {"status": "failed", "progress": 0, "message": str(e)}


@research_bp.route("/research-analysis", methods=["POST"])
@login_required
def research_analysis():
    """启动投资研报分析（异步）。返回 task_id，前端轮询进度。"""
    data = request.get_json(silent=True) or {}
    sectors = data.get("sectors", [])
    top_n = int(data.get("top_n", 10))

    if not sectors:
        return jsonify({"success": False, "error": "请至少指定一个行业板块"}), 400
    if not isinstance(sectors, list):
        sectors = [sectors]
    if len(sectors) > 10:
        return jsonify({"success": False, "error": "单次最多分析10个板块"}), 400

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
