"""
全市场热点新闻发现 API。
"""
import threading

from flask import Blueprint, request, jsonify, g

from api.auth_utils import login_required
from utils.logger import get_logger

logger = get_logger(__name__)

news_hotspot_bp = Blueprint("news_hotspot", __name__, url_prefix="/api/v1/news-hotspot")


@news_hotspot_bp.route("/hot-stocks", methods=["GET"])
def hot_stocks():
    try:
        hours = int(request.args.get("hours", 24))
        top_n = int(request.args.get("top_n", 20))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "invalid hours/top_n"}), 400
    try:
        from modules.monitor.hotspot import NewsHotspotDetector
        data = NewsHotspotDetector().detect(hours=hours, top_n=top_n)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"hot-stocks failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@news_hotspot_bp.route("/add-to-watchlist", methods=["POST"])
@login_required
def add_to_watchlist():
    code = (request.get_json(silent=True) or {}).get("code")
    if not code:
        return jsonify({"success": False, "error": "code required"}), 400
    try:
        from modules.watchlist.watchlist import WatchlistManager
        user_id = g.current_user["user_id"]
        # 复用现有逻辑：内部会触发 MonitorLifecycle.on_watchlist_added 同步监控
        ok = WatchlistManager().add_stock(user_id, code)
        return jsonify({"success": bool(ok)})
    except Exception as e:
        logger.error(f"add-to-watchlist failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@news_hotspot_bp.route("/trigger-deep-analysis", methods=["POST"])
@login_required
def trigger_deep_analysis():
    code = (request.get_json(silent=True) or {}).get("code")
    if not code:
        return jsonify({"success": False, "error": "code required"}), 400
    from utils.helpers import normalize_stock_code_flexible
    normalized = normalize_stock_code_flexible(code)
    user_id = g.current_user["user_id"]

    # 复用现有个股深度分析服务，异步生成 AI 报告，立即返回。
    def _run():
        try:
            from modules.ai.engines.deep_analysis import DeepAnalysisService
            DeepAnalysisService().ai_report(normalized, user_id=user_id)
        except Exception as e:
            logger.error(f"deep analysis {normalized} failed: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"success": True, "started": True, "code": normalized})
