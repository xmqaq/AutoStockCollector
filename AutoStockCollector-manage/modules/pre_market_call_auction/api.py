"""盘前竞价雷达 — Flask Blueprint。"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from api.auth_utils import login_required
from utils.logger import get_logger

from .config import AuctionConfig
from .radar_service import get_status, run_auction_scan
from .radar_utils import today_str
from .performance_tracker import (
    get_performance_stats,
    get_recent_results,
    update_result,
)
from .position_sizer import AuctionPositionSizer
from .schemas import RadarStock
from .intraday_pricer import get_intraday_data
from .risk_dashboard import get_risk_summary
from .signal_emitter import auto_close_positions

logger = get_logger(__name__)

auction_bp = Blueprint("pre_market_radar", __name__, url_prefix="/api/v1/ai")


@auction_bp.route("/pre-market-radar/status", methods=["GET"])
@login_required
def radar_status():
    return jsonify({"success": True, "data": get_status()})


@auction_bp.route("/pre-market-radar/results", methods=["GET"])
@login_required
def radar_results():
    date = request.args.get("date") or today_str()
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db[AuctionConfig.RESULT_COLLECTION].find_one({"date": date}, {"_id": 0})
        if not doc:
            return jsonify({"success": False, "error": f"{date} 尚无扫描结果"}), 404
        return jsonify({"success": True, "data": doc})
    except Exception as e:
        logger.warning(f"[AuctionRadar] results error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/trigger", methods=["POST"])
@login_required
def radar_trigger():
    data = request.get_json(silent=True) or {}
    symbols = data.get("symbols")
    if symbols is not None and not isinstance(symbols, list):
        return jsonify({"success": False, "error": "symbols 必须是数组或 null"}), 400
    result = run_auction_scan(symbols)
    return jsonify({
        "success": result.status == "done",
        "data": result.model_dump(),
    })


# ── Phase 2: Performance Tracker ──


@auction_bp.route("/pre-market-radar/performance", methods=["GET"])
@login_required
def radar_performance():
    days = request.args.get("days", 30, type=int)
    min_score = request.args.get("min_score", 0, type=int)
    if days < 1 or days > 365:
        return jsonify({"success": False, "error": "days 必须在 1-365 之间"}), 400
    stats = get_performance_stats(days=days, min_score=min_score)
    return jsonify({"success": True, "data": stats})


@auction_bp.route("/pre-market-radar/performance/history", methods=["GET"])
@login_required
def radar_performance_history():
    days = request.args.get("days", 7, type=int)
    limit = request.args.get("limit", 50, type=int)
    records = get_recent_results(days=days, limit=limit)
    return jsonify({"success": True, "data": {"records": records, "count": len(records)}})


@auction_bp.route("/pre-market-radar/performance/update", methods=["POST"])
@login_required
def radar_performance_update():
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    date = data.get("date")
    return_pct_raw = data.get("return_pct")
    if not code or not date or return_pct_raw is None:
        return jsonify({"success": False, "error": "缺少 code/date/return_pct"}), 400
    try:
        return_pct = float(return_pct_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "return_pct 必须为数字"}), 400
    update_result(code, date, return_pct, data.get("exit_reason", ""))
    return jsonify({"success": True})


# ── Phase 3: Position Sizer ──


@auction_bp.route("/pre-market-radar/position-suggestions", methods=["GET"])
@login_required
def radar_position_suggestions():
    date = request.args.get("date") or today_str()
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db[AuctionConfig.RESULT_COLLECTION].find_one({"date": date}, {"_id": 0})
        if not doc:
            return jsonify({"success": False, "error": f"{date} 尚无扫描结果"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    stocks = doc.get("top_stocks", [])
    if not stocks:
        return jsonify({"success": False, "error": f"{date} 扫描结果为空"}), 404

    try:
        radar_stocks = [RadarStock(**s) for s in stocks]
    except ValidationError as e:
        return jsonify({"success": False, "error": f"数据格式错误: {str(e)}"}), 500

    sizer = AuctionPositionSizer()
    suggestions = [sizer.suggest(s).__dict__ for s in radar_stocks]
    buy = [s for s in suggestions if s["action"] == "buy"]

    return jsonify({
        "success": True,
        "data": {
            "total_used_pct": sizer.total_used_pct,
            "buy_count": len(buy),
            "suggestions": suggestions,
            "summary": _position_summary(suggestions),
        },
    })


# ── P0: Intraday Tracking ──


@auction_bp.route("/pre-market-radar/intraday", methods=["GET"])
@login_required
def radar_intraday():
    date = request.args.get("date") or today_str()
    refresh = request.args.get("refresh", "1") == "1"
    try:
        data = get_intraday_data(date, refresh=refresh)
        return jsonify({"success": True, "data": {"records": data, "count": len(data)}})
    except Exception as e:
        logger.warning(f"[AuctionRadar] intraday error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/risk", methods=["GET"])
@login_required
def radar_risk():
    try:
        data = get_risk_summary()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.warning(f"[AuctionRadar] risk error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/auto-close", methods=["POST"])
@login_required
def radar_auto_close():
    try:
        closed = auto_close_positions()
        return jsonify({"success": True, "data": {"closed": closed}})
    except Exception as e:
        logger.warning(f"[AuctionRadar] auto-close error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/factor-detail", methods=["GET"])
@login_required
def radar_factor_detail():
    """返回某日某股的 8 维因子明细 + 权重快照。?date=&code="""
    date = request.args.get("date") or today_str()
    code = request.args.get("code", "")
    if not code:
        return jsonify({"success": False, "error": "缺少 code 参数"}), 400
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db[AuctionConfig.RESULT_COLLECTION].find_one({"date": date}, {"top_stocks": 1, "_id": 0})
        if not doc:
            return jsonify({"success": False, "error": f"{date} 尚无扫描结果"}), 404
        for s in doc.get("top_stocks", []) or []:
            if s.get("symbol") == code or s.get("code") == code:
                return jsonify({"success": True, "data": {
                    "code": code, "date": date,
                    "strength_detail": s.get("strength_detail", {}),
                    "trap_warning": s.get("trap_warning"),
                    "strength_score": s.get("strength_score", 0),
                }})
        return jsonify({"success": False, "error": f"{code} 不在 {date} 的 top_stocks 中"}), 404
    except Exception as e:
        logger.warning(f"[AuctionRadar] factor-detail error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/intraday/refresh", methods=["POST"])
@login_required
def radar_intraday_refresh():
    """手动触发盘中报价刷新（配合 cron，替代原懒刷新）。"""
    try:
        from .intraday_pricer import IntradayPricer
        date = request.json.get("date") if request.is_json else None
        updated = IntradayPricer().update_realtime(date)
        return jsonify({"success": True, "data": {"updated": updated}})
    except Exception as e:
        logger.warning(f"[AuctionRadar] intraday-refresh error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/backtest", methods=["POST"])
@login_required
def radar_backtest():
    """触发回测：body={start_date, end_date, exit_strategy?, top_n?, min_score?, weight_overrides?}"""
    try:
        from .backtest.replayer import AuctionBacktestReplayer
        from .backtest.schemas import BacktestConfig
        data = request.get_json(force=True) or {}
        cfg = BacktestConfig(
            start_date=data["start_date"],
            end_date=data["end_date"],
            exit_strategy=data.get("exit_strategy", "close"),
            top_n=data.get("top_n", 30),
            min_score=data.get("min_score", 0),
            weight_overrides=data.get("weight_overrides", {}),
        )
        result = AuctionBacktestReplayer().run(cfg)
        # 持久化结果（供 /backtest/results 查询）
        try:
            from config.database import DatabaseConfig
            from utils.helpers import beijing_now
            doc = result.model_dump()
            doc["created_at"] = beijing_now().isoformat()
            DatabaseConfig.get_database()["auction_backtest_results"].insert_one(doc)
        except Exception as e:
            logger.warning(f"[AuctionRadar] backtest persist error: {e}")
        return jsonify({"success": True, "data": result.model_dump()})
    except KeyError as e:
        return jsonify({"success": False, "error": f"缺少参数 {e}"}), 400
    except Exception as e:
        logger.warning(f"[AuctionRadar] backtest error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/backtest/results", methods=["GET"])
@login_required
def radar_backtest_results():
    """查询最近回测结果。"""
    try:
        from config.database import DatabaseConfig
        limit = min(int(request.args.get("limit", 5)), 20)
        docs = list(DatabaseConfig.get_database()["auction_backtest_results"]
                    .find({}, {"_id": 0}).sort("created_at", -1).limit(limit))
        return jsonify({"success": True, "data": docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@auction_bp.route("/pre-market-radar/backtest/optimize", methods=["POST"])
@login_required
def radar_backtest_optimize():
    """参数寻优：body={start_date, end_date, param_grid}"""
    try:
        from .backtest.optimizer import ParameterOptimizer
        from .backtest.schemas import BacktestConfig
        data = request.get_json(force=True) or {}
        cfg = BacktestConfig(start_date=data["start_date"], end_date=data["end_date"])
        grid = data.get("param_grid", {})
        result = ParameterOptimizer().grid_search(cfg, grid)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.warning(f"[AuctionRadar] optimize error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _position_summary(suggestions: list) -> str:
    buys = [s for s in suggestions if s["action"] == "buy"]
    observes = [s for s in suggestions if s["action"] == "observe"]
    skips = [s for s in suggestions if s["action"] == "skip"]
    total = sum(s["position_pct"] for s in suggestions)
    parts = [
        f"建议买入{len(buys)}只，观察{len(observes)}只，跳过{len(skips)}只",
        f"总建议仓位{total*100:.0f}%",
    ]
    if buys:
        top = buys[:3]
        parts.append("首选: " + ", ".join(f"{s['name']}({s['position_pct']*100:.0f}%)" for s in top))
    return "。".join(parts)
