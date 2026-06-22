"""盘前竞价雷达 — Flask Blueprint。"""
from datetime import datetime

from flask import Blueprint, jsonify
from api.auth_utils import login_required
from utils.logger import get_logger

from .config import AuctionConfig
from .radar_service import get_status, run_auction_scan

logger = get_logger(__name__)

auction_bp = Blueprint("pre_market_radar", __name__, url_prefix="/api/v1/ai")


@auction_bp.route("/pre-market-radar/status", methods=["GET"])
@login_required
def radar_status():
    """返回当日扫描状态。"""
    return jsonify({"success": True, "data": get_status()})


@auction_bp.route("/pre-market-radar/results", methods=["GET"])
@login_required
def radar_results():
    """返回当日竞价雷达结果。"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db[AuctionConfig.RESULT_COLLECTION].find_one({"date": today}, {"_id": 0})
        if not doc:
            return jsonify({"success": False, "error": "今日尚未扫描"}), 404
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.warning(f"[AuctionRadar] results error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/trigger", methods=["POST"])
@login_required
def radar_trigger():
    """手动触发盘前竞价扫描（用于测试）。"""
    from flask import request
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols")
    result = run_auction_scan(symbols)
    return jsonify({
        "success": result.status == "done",
        "data": result.model_dump(),
    })
