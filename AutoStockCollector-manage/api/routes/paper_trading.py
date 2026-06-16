"""模拟盘交易 API — /api/paper/*"""
import time
import threading
from flask import Blueprint, request, jsonify, g
from utils.logger import get_logger
from api.auth_utils import login_required

logger = get_logger(__name__)
paper_bp = Blueprint("paper", __name__, url_prefix="/api/paper")

_account = None
_engine = None
_stats = None
_snapshot = None

# 实时排行榜缓存：盘中前端会高频轮询，缓存避免每次都对所有用户批量拉行情。
_ranking_live_cache = {"payload": None, "at": 0.0}
_ranking_live_lock = threading.Lock()
_RANKING_LIVE_TTL = 15.0


def _lazy_init():
    global _account, _engine, _stats, _snapshot
    if _account is None:
        from modules.paper_trading.account import PaperAccount
        from modules.paper_trading.trade_engine import TradeEngine
        from modules.paper_trading.stats import PaperStats
        from modules.paper_trading.snapshot import PortfolioSnapshot
        _account = PaperAccount()
        _engine = TradeEngine()
        _stats = PaperStats()
        _snapshot = PortfolioSnapshot()
        _snapshot.ensure_today("default", _account, _engine)


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
        capital = float(data.get("initial_capital", 100000))
    except (TypeError, ValueError):
        return jsonify({"error": "initial_capital 必须为数字"}), 400
    if capital <= 0:
        return jsonify({"error": "initial_capital 必须大于 0"}), 400
    doc = _account.init(capital, user_id)
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/account/deposit", methods=["POST"])
def deposit_account():
    """非破坏性入金/出金：amount>0 入金，<0 出金。现金与初始资金同步增减。"""
    _lazy_init()
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount 必须为数字"}), 400
    if amount == 0:
        return jsonify({"error": "amount 不能为 0"}), 400
    try:
        doc = _account.deposit(user_id, amount)
        return jsonify({"success": True, "data": doc})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


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

    price = None
    if data.get("price") is not None:
        try:
            price = float(data["price"])
        except (TypeError, ValueError):
            pass

    from utils.helpers import normalize_stock_code_flexible
    code = normalize_stock_code_flexible(code)

    if not code or not action or shares <= 0:
        return jsonify({"error": "code、action、shares 均为必填项"}), 400

    try:
        if action == "buy":
            record = _engine.buy(user_id, code, shares, ai_signal, _account, price=price)
        elif action == "sell":
            record = _engine.sell(user_id, code, shares, ai_signal, _account, price=price)
        else:
            return jsonify({"error": "action 必须为 buy 或 sell"}), 400
        try:
            _snapshot.record(user_id, _account, _engine)
        except Exception as e:
            logger.warning(f"快照记录失败: {e}")
        return jsonify({"success": True, "data": record})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@paper_bp.route("/positions", methods=["GET"])
def get_positions():
    _lazy_init()
    user_id = request.args.get("user_id", "default")
    positions, trading = _engine.get_positions(user_id)
    return jsonify({
        "success": True,
        "count": len(positions),
        "data": positions,
        "is_trading_time": trading,
    })


@paper_bp.route("/price", methods=["GET"])
def get_price():
    _lazy_init()
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "code 为必填项"}), 400
    from utils.helpers import normalize_stock_code_flexible
    code = normalize_stock_code_flexible(code)
    price, price_type = _engine.get_current_price(code)
    if price is None:
        return jsonify({"success": False, "error": f"无法获取 {code} 的价格"}), 404
    from modules.paper_trading.trade_engine import is_trading_time
    return jsonify({
        "success": True,
        "data": {
            "code": code,
            "price": round(price, 2),
            "price_type": price_type,
            "is_trading_time": is_trading_time(),
        }
    })


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
    snapshots = _snapshot.get_history(user_id)
    if snapshots:
        nav = [{
            "date": s["date"],
            "net_value": s["net_value"],
            "cash": s["cash"],
            "market_value": s["market_value"],
            "profit_amount": s["profit_amount"],
            "profit_pct": s["profit_pct"],
            "initial_capital": s["initial_capital"],
        } for s in snapshots]
    else:
        nav = _stats.get_nav(user_id, _account)
    return jsonify({"success": True, "data": nav})


def _live_profit(uid):
    """按实时净值（现金 + 实时持仓市值）计算某用户的收益。
    返回 (profit_pct, profit_amount, initial_capital)；账户未初始化返回 None。
    """
    account_info = _account.get(uid)
    if not account_info:
        return None
    initial_capital = account_info["initial_capital"]
    positions, _ = _engine.get_positions(uid)
    cash = account_info["cash_balance"]
    market_value = sum(p["market_value"] for p in positions)
    profit_amount = cash + market_value - initial_capital
    profit_pct = (profit_amount / initial_capital * 100) if initial_capital > 0 else 0
    return profit_pct, profit_amount, initial_capital


@paper_bp.route("/ranking", methods=["GET"])
def get_ranking():
    """用户盈利排行榜：按总收益率降序，含收益率/收益额/胜率/交易次数。

    默认（无 live 参数）：用每日 16:30 净值快照 `portfolio_snapshots`（无快照才退化为实时）。
    传 ?live=1：所有用户都按实时净值计算（盘中可反映当日浮盈浮亏），结果缓存
    _RANKING_LIVE_TTL 秒，避免高频轮询打爆行情接口。
    """
    from config.database import DatabaseConfig
    from modules.paper_trading.trade_engine import is_trading_time

    live = request.args.get("live") in ("1", "true", "True", "yes")

    if live:
        with _ranking_live_lock:
            cache = _ranking_live_cache
            if cache["payload"] is not None and (time.time() - cache["at"]) < _RANKING_LIVE_TTL:
                return jsonify({**cache["payload"], "cached": True})

    db = DatabaseConfig.get_database()
    users = list(db.users.find({}, {"username": 1, "nickname": 1, "user_id": 1, "_id": 0}))

    _lazy_init()
    result = []
    for user in users:
        uid = user["user_id"]
        if live:
            computed = _live_profit(uid)
            if computed is None:
                continue
            profit_pct, profit_amount, initial_capital = computed
        else:
            snap = db["portfolio_snapshots"].find_one(
                {"user_id": uid}, sort=[("date", -1)]
            )
            if snap and snap.get("profit_pct") is not None:
                profit_pct = snap["profit_pct"]
                profit_amount = snap.get("profit_amount", 0)
                account_info = _account.get(uid)
                initial_capital = account_info["initial_capital"] if account_info else snap.get("initial_capital", 0)
            else:
                computed = _live_profit(uid)
                if computed is None:
                    continue
                profit_pct, profit_amount, initial_capital = computed

        stats = _stats.get_stats(uid)
        result.append({
            "user_id": uid,
            "username": user.get("nickname", user.get("username", uid)),
            "raw_username": user.get("username", uid),
            "profit_pct": round(profit_pct, 2),
            "profit_amount": round(profit_amount, 2),
            "initial_capital": round(initial_capital, 2),
            "win_rate": stats.get("win_rate", 0),
            "total_trades": stats.get("total_trades", 0),
        })

    result.sort(key=lambda x: x["profit_pct"], reverse=True)
    for i, r in enumerate(result, 1):
        r["rank"] = i

    payload = {
        "success": True,
        "count": len(result),
        "data": result,
        "live": live,
        "is_trading": is_trading_time(),
    }
    if live:
        with _ranking_live_lock:
            _ranking_live_cache["payload"] = payload
            _ranking_live_cache["at"] = time.time()
    return jsonify(payload)
