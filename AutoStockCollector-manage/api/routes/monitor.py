"""AI 实时监控 API 路由 — 四来源股票池 + 实时数据 + 规则/LLM 双建议

重构后：删除 backtest/sector-sentiment/fund-flow-anomalies（噪音或重复），
新增 /realtime（池中股票实时快照）、/signals/<code>/ai-advice（单股LLM预测）。
异动检测统一走 anomaly.py，由 /portfolio 的 anomaly_alerts 返回。
"""
import threading
from flask import Blueprint, jsonify, request, g

from modules.monitor.storage import MonitorStorage
from utils.logger import get_logger
from api.auth_utils import login_required

logger = get_logger(__name__)

monitor_bp = Blueprint("monitor", __name__, url_prefix="/api/v1/monitor")

_engine = None
_engine_lock = threading.Lock()
_refresh_lock = threading.Lock()


def _get_user_stock_codes(user_id: str) -> set:
    """用户监控名单的股票代码集合（持仓 + 自选 + AI智选 + 投研分析）。"""
    try:
        return {s["code"] for s in _get_engine()._collect_stocks(user_id) if s.get("code")}
    except Exception as e:
        logger.error(f"Collect user stock codes failed: {e}")
        return set()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from modules.monitor.engine import MonitorEngine
                _engine = MonitorEngine()
    return _engine


@monitor_bp.route("/signals", methods=["GET"])
@login_required
def get_signals():
    try:
        storage = MonitorStorage()
        all_signals = storage.get_all_signals()
        user_codes = _get_user_stock_codes(g.current_user["user_id"])
        if user_codes:
            signals = [s for s in all_signals if s.get("code") in user_codes]
        else:
            signals = all_signals
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


@monitor_bp.route("/signals/<code>/ai-advice", methods=["POST"])
@login_required
def get_ai_advice(code: str):
    """单股 LLM 买卖建议（按需触发，受当日缓存+limit约束）。"""
    try:
        from modules.monitor.ai_advisor import LLMAiAdvisor
        force = request.args.get("force") in ("1", "true", "True")
        advice = LLMAiAdvisor().predict(code, force=force)
        if not advice:
            return jsonify({"success": True, "data": None,
                            "message": "已达每日预测上限或数据不足，请稍后再试"})
        return jsonify({"success": True, "data": advice})
    except Exception as e:
        logger.error(f"AI advice {code} failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/realtime", methods=["GET"])
@login_required
def get_realtime():
    """池中股票的实时行情+资金流快照（来自 monitor_realtime 集合）。"""
    try:
        from modules.monitor.realtime import RealtimeRefresher
        codes = list(_get_user_stock_codes(g.current_user["user_id"]))
        if not codes:
            return jsonify({"success": True, "data": [], "count": 0})
        rt_map = RealtimeRefresher().get_realtime_map(codes)
        data = [{"code": c, **rt_map[c]} for c in codes if c in rt_map]
        return jsonify({"success": True, "count": len(data), "data": data})
    except Exception as e:
        logger.error(f"Get realtime failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/refresh", methods=["POST"])
@login_required
def refresh_all():
    if _refresh_lock.locked():
        return jsonify({"success": False, "error": "刷新任务正在运行中，请稍候再试"}), 429

    user_id = g.current_user["user_id"]

    def _run():
        with _refresh_lock:
            try:
                _get_engine().refresh_all(user_id)
            except Exception as e:
                logger.error(f"Refresh all failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "刷新任务已启动，请稍后查询结果"})


@monitor_bp.route("/refresh/<code>", methods=["POST"])
@login_required
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
@login_required
def scan_once():
    try:
        result = _get_engine().refresh_all(g.current_user["user_id"])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/lifecycle-status", methods=["GET"])
@login_required
def get_lifecycle_status():
    """当前监控名单的来源分布统计（持仓/自选/智选/投研 + 重叠 + 强化信号数）。"""
    try:
        stocks = _get_engine()._collect_stocks(g.current_user["user_id"])
        pos = {s["code"] for s in stocks if "position" in (s.get("sources") or [])}
        watch = {s["code"] for s in stocks if "watchlist" in (s.get("sources") or [])}
        fusion = {s["code"] for s in stocks if "fusion_pick" in (s.get("sources") or [])}
        research = {s["code"] for s in stocks if "research" in (s.get("sources") or [])}
        strong = sum(1 for s in stocks
                     if "fusion_pick" in (s.get("sources") or [])
                     and (s.get("consecutive_days", 0) or 0) >= 3)
        return jsonify({"success": True, "data": {
            "total": len(stocks),
            "by_source": {"position": len(pos), "watchlist": len(watch),
                          "fusion_pick": len(fusion), "research": len(research)},
            "overlap": {
                "position_and_watchlist": len(pos & watch),
                "position_and_fusion": len(pos & fusion),
                "watchlist_and_fusion": len(watch & fusion),
            },
            "strong_signal_count": strong,
        }})
    except Exception as e:
        logger.error(f"Lifecycle status failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route("/portfolio", methods=["GET"])
@login_required
def get_monitor_portfolio():
    """读最近一次 refresh_all 的调仓建议 + 组合概览 + 异动预警。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        uid = g.current_user["user_id"]
        doc = (db["monitor_signals"].find_one({"type": "portfolio_advice", "user_id": uid})
               or db["monitor_signals"].find_one({"type": "portfolio_advice", "user_id": "default"}))
        if not doc:
            return jsonify({"success": True, "data": None})
        doc.pop("_id", None)
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.error(f"Get monitor portfolio failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
