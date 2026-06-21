"""价格行为学 — Flask Blueprint（异步 + 进度轮询）。"""
import threading
import uuid
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request
from api.auth_utils import login_required
from utils.logger import get_logger

logger = get_logger(__name__)

pa_bp = Blueprint("price_action", __name__, url_prefix="/api/v1/ai")

_engine = None
_engine_lock = threading.Lock()
_tasks = {}
_tasks_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from .price_action_engine import PriceActionEngine
                _engine = PriceActionEngine()
    return _engine


def _run_analysis(task_id: str, symbols: list, timeframe: str, risk_pct: float, balance: float, use_ai: bool = False):
    try:
        with _tasks_lock:
            _tasks[task_id] = {"status": "processing", "progress": 0, "message": "正在初始化..."}

        engine = _get_engine()
        total = len(symbols)

        results = []
        for i, symbol in enumerate(symbols):
            def make_callback(sym: str):
                def cb(pct: int, msg: str):
                    overall = int((i / total) * 70 + (pct / total) * 0.7)
                    with _tasks_lock:
                        _tasks[task_id]["progress"] = min(overall, 98)
                        _tasks[task_id]["message"] = f"[{sym}] {msg}"
                return cb

            try:
                sig = engine.analyze(
                    symbol, timeframe=timeframe, risk_pct=risk_pct,
                    account_balance=balance, use_ai=use_ai,
                    progress_callback=make_callback(symbol),
                )
                results.append(sig)
            except Exception as e:
                logger.warning(f"[PA] analyze error {symbol}: {e}")
                results.append({"symbol": symbol, "signal": "ERROR", "error": str(e)})

        with _tasks_lock:
            _tasks[task_id]["progress"] = 98
            _tasks[task_id]["message"] = "保存结果..."

        try:
            from config.database import DatabaseConfig
            from .config import PAConfig
            db = DatabaseConfig.get_database()
            db[PAConfig.RESULTS_COLLECTION].insert_one({
                "task_id": task_id,
                "symbols": symbols,
                "timeframe": timeframe,
                "results": results,
                "created_at": datetime.now(),
            })
        except Exception as e:
            logger.warning(f"[PA] save result error: {e}")

        with _tasks_lock:
            _tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "分析完成",
                "results": results,
            }
    except Exception as e:
        logger.error(f"[PA] task {task_id} failed: {e}")
        with _tasks_lock:
            _tasks[task_id] = {"status": "failed", "progress": 0, "message": str(e)}


def _analyze_single_sync(symbol: str, timeframe: str, risk_pct: float, balance: float, use_ai: bool = False) -> dict:
    """同步分析单只股票（用于单股 API）。"""
    engine = _get_engine()
    return engine.analyze(symbol, timeframe=timeframe, risk_pct=risk_pct, account_balance=balance, use_ai=use_ai)


@pa_bp.route("/price-action", methods=["POST"])
@login_required
def price_action_batch():
    """批量分析 — 异步，返回 task_id。"""
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols", [])
    timeframe = data.get("timeframe", "daily")
    risk_pct = float(data.get("account_risk", 0.02))
    balance = float(data.get("account_balance", 100000))
    use_ai = data.get("use_ai", False)

    if not symbols:
        return jsonify({"success": False, "error": "请至少指定一个股票代码"}), 400
    if len(symbols) > 50:
        return jsonify({"success": False, "error": "单次最多分析50只股票"}), 400

    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "progress": 0, "message": "任务已提交"}

    thread = threading.Thread(
        target=_run_analysis,
        args=(task_id, symbols, timeframe, risk_pct, balance, use_ai),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "message": "分析任务已提交，请轮询进度"})


@pa_bp.route("/price-action/result/<task_id>", methods=["GET"])
@login_required
def get_result(task_id: str):
    """轮询分析进度。"""
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
    if task["status"] == "completed" and "results" in task:
        resp["data"] = task["results"]
    return jsonify(resp)


@pa_bp.route("/price-action/single", methods=["GET"])
@login_required
def price_action_single():
    """单股分析（同步，用于前端实时查看）。"""
    symbol = request.args.get("symbol", "")
    timeframe = request.args.get("timeframe", "daily")
    risk_pct = float(request.args.get("risk", 0.02))
    balance = float(request.args.get("balance", 100000))
    use_ai = request.args.get("use_ai", "").lower() == "true"

    if not symbol:
        return jsonify({"success": False, "error": "symbol is required"}), 400

    try:
        result = _analyze_single_sync(symbol, timeframe, risk_pct, balance, use_ai)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"[PA] single analyze error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@pa_bp.route("/price-action/history", methods=["GET"])
@login_required
def get_history():
    """获取最近的分析历史。"""
    try:
        from config.database import DatabaseConfig
        from .config import PAConfig
        db = DatabaseConfig.get_database()
        docs = list(
            db[PAConfig.RESULTS_COLLECTION]
            .find({}, {"results": 0})
            .sort("created_at", -1)
            .limit(20)
        )
        for d in docs:
            d.pop("_id", None)
        return jsonify({"success": True, "count": len(docs), "data": docs})
    except Exception as e:
        logger.warning(f"[PA] history error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
