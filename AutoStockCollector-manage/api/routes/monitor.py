"""
AI 实时监控 API 路由 — 主力资金流量 + 研报分析，长短线投资建议
"""
import threading
from flask import Blueprint, jsonify, request

from modules.monitor.storage import MonitorStorage
from utils.logger import get_logger

logger = get_logger(__name__)

monitor_bp = Blueprint("monitor", __name__, url_prefix="/api/v1/monitor")

_engine = None
_engine_lock = threading.Lock()
_refresh_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from modules.monitor.engine import MonitorEngine
                _engine = MonitorEngine()
    return _engine


@monitor_bp.route("/signals", methods=["GET"])
def get_signals():
    try:
        storage = MonitorStorage()
        signals = storage.get_all_signals()
        return jsonify({"success": True, "count": len(signals), "data": signals})
    except Exception as e:
        logger.error(f"Get signals failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/signals/<code>", methods=["GET"])
def get_signal(code: str):
    try:
        storage = MonitorStorage()
        signal = storage.get_signal(code)
        if not signal:
            return jsonify({"success": False, "error": "未找到该股票信号"}), 404
        return jsonify({"success": True, "data": signal})
    except Exception as e:
        logger.error(f"Get signal {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/signals/<code>/history", methods=["GET"])
def get_signal_history(code: str):
    try:
        days = int(request.args.get("days", 30))
        storage = MonitorStorage()
        history = storage.get_history(code, days)
        return jsonify({"success": True, "count": len(history), "data": history})
    except Exception as e:
        logger.error(f"Get history for {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/refresh", methods=["POST"])
def refresh_all():
    if _refresh_lock.locked():
        return jsonify({"success": False, "error": "刷新任务正在运行中，请稍候再试"}), 429

    def _run():
        with _refresh_lock:
            try:
                _get_engine().refresh_all()
            except Exception as e:
                logger.error(f"Refresh all failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "刷新任务已启动，请稍后查询结果"})


@monitor_bp.route("/refresh/<code>", methods=["POST"])
def refresh_stock(code: str):
    try:
        result = _get_engine().refresh_stock(code)
        if not result:
            return jsonify({"success": False, "error": "分析失败"}), 500
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Refresh {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/scan", methods=["GET"])
def scan_once():
    try:
        result = _get_engine().refresh_all()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/backtest/<code>", methods=["GET"])
def get_backtest(code: str):
    """获取单只股票信号回测结果"""
    try:
        from modules.monitor.backtest import SignalBacktest
        days = int(request.args.get("days", 60))
        result = SignalBacktest().evaluate(code, days)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Backtest {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/backtest", methods=["GET"])
def get_backtest_all():
    """获取所有信号回测结果"""
    try:
        from modules.monitor.backtest import SignalBacktest
        results = SignalBacktest().evaluate_all()
        return jsonify({"success": True, "count": len(results), "data": results})
    except Exception as e:
        logger.error(f"Backtest all failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
