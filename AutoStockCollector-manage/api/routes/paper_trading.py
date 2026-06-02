"""模拟盘交易 API — /api/paper/*"""
from flask import Blueprint, request, jsonify
from utils.logger import get_logger

logger = get_logger(__name__)
paper_bp = Blueprint("paper", __name__, url_prefix="/api/paper")

_account = None
_engine = None
_stats = None


def _lazy_init():
    global _account, _engine, _stats
    if _account is None:
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine
        from modules.paper_trading.stats import PaperStats
        _account = PaperAccount()
        _engine = TradeEngine()
        _stats = PaperStats()


@paper_bp.route("/account", methods=["GET"])
def get_account():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    doc = _account.get(user_id)
    if not doc:
        return jsonify({"success": False, "error": "账户未初始化，请先设置初始资金"}), 404
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/account/init", methods=["POST"])
def init_account():
    _lazy_init()
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    try:
        capital = float(data.get("initial_capital", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "initial_capital 必须为数字"}), 400
    if capital <= 0:
        return jsonify({"error": "initial_capital 必须大于 0"}), 400
    doc = _account.init(capital, user_id)
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/trade", methods=["POST"])
def execute_trade():
    _lazy_init()
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    code = data.get("code", "").strip()
    action = data.get("action", "").strip()
    ai_signal = data.get("ai_signal", {})

    try:
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "shares 必须为整数"}), 400

    if not code or not action or shares <= 0:
        return jsonify({"error": "code、action、shares 均为必填项"}), 400

    from utils.helpers import normalize_stock_code_flexible
    code = normalize_stock_code_flexible(code)

    try:
        if action == "buy":
            record = _engine.buy(user_id, code, shares, ai_signal, _account)
        elif action == "sell":
            record = _engine.sell(user_id, code, shares, ai_signal, _account)
        else:
            return jsonify({"error": "action 必须为 buy 或 sell"}), 400
        return jsonify({"success": True, "data": record})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@paper_bp.route("/positions", methods=["GET"])
def get_positions():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    positions = _engine.get_positions(user_id)
    return jsonify({"success": True, "count": len(positions), "data": positions})


@paper_bp.route("/trades", methods=["GET"])
def get_trades():
    _lazy_init()
    from config.database import DatabaseConfig
    user_id = request.args.get("user_id", "default")
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    db = DatabaseConfig.get_database()
    trades = list(
        db["trade_records"].find({"user_id": user_id}, sort=[("traded_at", -1)], limit=limit)
    )
    for t in trades:
        t.pop("_id", None)
    return jsonify({"success": True, "count": len(trades), "data": trades})


@paper_bp.route("/stats", methods=["GET"])
def get_stats():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    stats = _stats.get_stats(user_id)
    return jsonify({"success": True, "data": stats})


@paper_bp.route("/nav", methods=["GET"])
def get_nav():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    nav = _stats.get_nav(user_id, _account)
    return jsonify({"success": True, "data": nav})
