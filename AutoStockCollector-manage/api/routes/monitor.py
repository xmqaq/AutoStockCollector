"""
AI 实时监控 API 路由 — 主力资金流量 + 研报分析，长短线投资建议
"""
import threading
from typing import Dict
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
    """获取用户关心的股票代码（持仓 + 自选）"""
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    codes = set()
    try:
        for p in db["positions"].find({"user_id": user_id}):
            c = p.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    try:
        for p in db["trade_records"].aggregate([
            {"$match": {"user_id": user_id, "action": "buy"}},
            {"$group": {"_id": None, "codes": {"$addToSet": "$code"}}},
        ]):
            for c in p.get("codes", []):
                codes.add(c)
    except Exception:
        pass
    try:
        for w in db["watchlist"].find({"user_id": user_id, "enabled": True}):
            c = w.get("code", "")
            if c: codes.add(c)
    except Exception:
        pass
    return codes


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


@monitor_bp.route("/refresh", methods=["POST"])
@login_required
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


@monitor_bp.route("/sector-sentiment", methods=["GET"])
def get_sector_sentiment():
    """板块舆情热度排行 — 按行业聚合新闻情感评分"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        signals = list(db["monitor_signals"].find(
            {"analysis.news_sentiment": {"$exists": True}},
            {"industry": 1, "analysis.news_sentiment": 1, "name": 1, "code": 1, "_id": 0},
        ))

        sector_map: Dict[str, Dict] = {}
        for s in signals:
            industry = s.get("industry", "") or "未知"
            ns = s.get("analysis", {}).get("news_sentiment", {})
            overall = ns.get("overall", {})
            score = overall.get("score", 50)
            pos = ns.get("positive_count", 0)
            neg = ns.get("negative_count", 0)
            total = ns.get("news_count", 0)
            bullish = overall.get("bullish", False)

            if industry not in sector_map:
                sector_map[industry] = {
                    "industry": industry,
                    "stock_count": 0,
                    "total_score": 0.0,
                    "total_news": 0,
                    "positive_news": 0,
                    "negative_news": 0,
                    "bullish_stocks": 0,
                    "top_stocks": [],
                }
            sec = sector_map[industry]
            sec["stock_count"] += 1
            sec["total_score"] += score
            sec["total_news"] += total
            sec["positive_news"] += pos
            sec["negative_news"] += neg
            if bullish:
                sec["bullish_stocks"] += 1
            if total > 0:
                sec["top_stocks"].append({
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "news_count": total,
                    "sentiment_score": round(score, 1),
                    "bullish": bullish,
                })

        result = []
        for industry, sec in sector_map.items():
            avg_score = sec["total_score"] / sec["stock_count"] if sec["stock_count"] > 0 else 50
            sec["top_stocks"].sort(key=lambda x: x["news_count"], reverse=True)
            result.append({
                "industry": industry,
                "stock_count": sec["stock_count"],
                "avg_sentiment_score": round(avg_score, 1),
                "total_news": sec["total_news"],
                "positive_news": sec["positive_news"],
                "negative_news": sec["negative_news"],
                "bullish_stock_ratio": round(sec["bullish_stocks"] / sec["stock_count"] * 100, 1) if sec["stock_count"] > 0 else 0,
                "top_stocks": sec["top_stocks"][:5],
                "signal": "bullish" if avg_score >= 60 else "bearish" if avg_score <= 40 else "neutral",
            })

        result.sort(key=lambda x: x["avg_sentiment_score"], reverse=True)
        return jsonify({"success": True, "count": len(result), "data": result})
    except Exception as e:
        logger.error(f"Sector sentiment failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
