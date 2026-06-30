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


def _uid():
    """从 Authorization header 解析用户ID，未认证时返回 None"""
    from api.auth_utils import decode_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:])
        if payload and payload.get("user_id"):
            return payload["user_id"]
    return None


def _resolve_user_id():
    """统一用户ID解析：已认证返回用户自己的ID，未认证回退到 'default'。"""
    _lazy_init()
    uid = _uid()
    if uid:
        return uid
    return "default"


@paper_bp.route("/account", methods=["GET"])
def get_account():
    user_id = _resolve_user_id()
    doc = _account.get(user_id)
    if not doc:
        return jsonify({"success": False, "error": "账户未初始化，请先设置初始资金"}), 404
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/account/init", methods=["POST"])
@login_required
def init_account():
    _lazy_init()
    user_id = g.current_user["user_id"]
    data = request.get_json() or {}
    try:
        capital = float(data.get("initial_capital", 100000))
    except (TypeError, ValueError):
        return jsonify({"error": "initial_capital 必须为数字"}), 400
    if capital <= 0:
        return jsonify({"error": "initial_capital 必须大于 0"}), 400
    doc = _account.init(capital, user_id)
    return jsonify({"success": True, "data": doc})


@paper_bp.route("/account/deposit", methods=["POST"])
@login_required
def deposit_account():
    """非破坏性入金/出金：amount>0 入金，<0 出金。现金与初始资金同步增减。"""
    _lazy_init()
    user_id = _resolve_user_id()
    data = request.get_json() or {}
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
@login_required
def execute_trade():
    _lazy_init()
    data = request.get_json() or {}
    user_id = _resolve_user_id()
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

    stop_loss = None
    if data.get("stop_loss") is not None:
        try:
            stop_loss = float(data["stop_loss"])
        except (TypeError, ValueError):
            pass

    take_profit = None
    if data.get("take_profit") is not None:
        try:
            take_profit = float(data["take_profit"])
        except (TypeError, ValueError):
            pass

    from utils.helpers import normalize_stock_code_flexible
    code = normalize_stock_code_flexible(code)

    if not code or not action or shares <= 0:
        return jsonify({"error": "code、action、shares 均为必填项"}), 400

    try:
        if action == "buy":
            result = _engine.buy(user_id, code, shares, ai_signal, _account, price=price, stop_loss=stop_loss, take_profit=take_profit)
        elif action == "sell":
            result = _engine.sell(user_id, code, shares, ai_signal, _account, price=price)
        else:
            return jsonify({"error": "action 必须为 buy 或 sell"}), 400
        # 即时成交才记净值快照；挂单(pending)未改变持仓/现金，不记。
        if result.get("status") == "filled":
            try:
                _snapshot.record(user_id, _account, _engine)
            except Exception as e:
                logger.warning(f"快照记录失败: {e}")
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@paper_bp.route("/orders", methods=["GET"])
def get_orders():
    """订单列表（含挂单/已成/已撤）。?status=pending|filled|cancelled|all 过滤。"""
    _lazy_init()
    user_id = _resolve_user_id()
    status = (request.args.get("status") or "").strip()
    query = {"user_id": user_id}
    if status and status != "all":
        query["status"] = status
    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    orders = list(_engine._orders.find(query, sort=[("created_at", -1)], limit=limit))
    for o in orders:
        o["_id"] = str(o["_id"])
    return jsonify({"success": True, "count": len(orders), "data": orders})


@paper_bp.route("/orders/cancel", methods=["POST"])
@login_required
def cancel_order():
    """手动撤单：仅 pending 可撤。买入单解冻冻结资金。"""
    _lazy_init()
    user_id = _resolve_user_id()
    data = request.get_json() or {}
    order_id = (data.get("order_id") or "").strip()
    if not order_id:
        return jsonify({"error": "order_id 为必填项"}), 400
    try:
        result = _engine._cancel_order(order_id, reason="用户手动撤单")
        if result["user_id"] != user_id:
            return jsonify({"error": "无权撤他人的订单"}), 403
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@paper_bp.route("/positions", methods=["GET"])
def get_positions():
    _lazy_init()
    # admin 旧数据存于 'default'：显式传入的 user_id 也需同样映射，否则排行榜明细查 'admin' 为空
    _, user_id = _resolve_ranking_uid(request.args.get("user_id") or _resolve_user_id())
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
    from config.database import DatabaseConfig
    _lazy_init()
    # 同 /positions：admin→default 映射，保证排行榜明细能查到旧数据
    _, user_id = _resolve_ranking_uid(request.args.get("user_id") or _resolve_user_id())
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
    user_id = _resolve_user_id()
    stats = _stats.get_stats(user_id)
    return jsonify({"success": True, "data": stats})


@paper_bp.route("/nav", methods=["GET"])
def get_nav():
    user_id = _resolve_user_id()
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
    返回 (profit_pct, profit_amount, initial_capital, account_doc, positions)；
    账户未初始化返回 None。
    """
    account_info = _account.get(uid)
    if not account_info:
        return None
    initial_capital = account_info["initial_capital"]
    positions, _ = _engine.get_positions(uid)
    cash = account_info["cash_balance"]
    frozen = account_info.get("frozen_cash", 0)  # 挂单冻结资金仍属用户总资产
    market_value = sum(p["market_value"] for p in positions)
    profit_amount = cash + frozen + market_value - initial_capital
    profit_pct = (profit_amount / initial_capital * 100) if initial_capital > 0 else 0
    return profit_pct, profit_amount, initial_capital, account_info, positions


@paper_bp.route("/ranking", methods=["GET"])
def get_ranking():
    """用户盈利排行榜：按总收益率降序，含收益率/收益额/胜率/交易次数。

    默认（无 live 参数）：用每日 16:30 净值快照 `portfolio_snapshots`（无快照才退化为实时）。
    传 ?live=1：所有用户都按实时净值计算（盘中可反映当日浮盈浮亏），结果缓存
    _RANKING_LIVE_TTL 秒，避免高频轮询打爆行情接口。
    支持 ?limit=N&offset=M 分页。
    """
    from config.database import DatabaseConfig
    from modules.paper_trading.trade_engine import is_trading_time

    live = request.args.get("live") in ("1", "true", "True", "yes")
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int, default=0)

    if live:
        with _ranking_live_lock:
            cache = _ranking_live_cache
            if cache["payload"] is not None and (time.time() - cache["at"]) < _RANKING_LIVE_TTL:
                return jsonify({**cache["payload"], "cached": True})

    db = DatabaseConfig.get_database()

    # 查所有 paper_account 用户（含无 users 记录的头像账户如 "default"）
    account_uids = set(db["paper_account"].distinct("user_id"))
    registered = {
        u["user_id"]: u
        for u in db.users.find(
            {"user_id": {"$in": list(account_uids)}},
            {"username": 1, "nickname": 1, "user_id": 1, "_id": 0},
        )
    }
    users = []
    for uid in account_uids:
        if uid in registered:
            users.append(registered[uid])
        else:
            users.append({"user_id": uid, "username": uid, "nickname": uid})

    # 各用户累计手续费（佣金 + 印花税），一次聚合取齐
    fee_map = {}
    try:
        for r in db["trade_records"].aggregate([
            {"$group": {"_id": "$user_id", "fee": {"$sum": {"$add": [
                {"$ifNull": ["$commission", 0]}, {"$ifNull": ["$stamp_tax", 0]},
            ]}}}},
        ]):
            fee_map[r["_id"]] = r.get("fee", 0)
    except Exception:
        pass

    _lazy_init()

    result = []
    for user in users:
        try:
            uid = user["user_id"]
            query_uid = uid

            if live:
                computed = _live_profit(query_uid)
                if computed is None:
                    continue
                profit_pct, profit_amount, initial_capital, account_doc, positions = computed
                cash = account_doc.get("cash_balance", 0)
                market_value = sum(p["market_value"] for p in positions)
                today_pnl = sum(p.get("today_pnl_amount", 0.0) for p in positions)
            else:
                snap = db["portfolio_snapshots"].find_one(
                    {"user_id": query_uid}, sort=[("date", -1)]
                )
                if snap and snap.get("profit_pct") is not None:
                    profit_pct = snap["profit_pct"]
                    profit_amount = snap.get("profit_amount", 0)
                    initial_capital = snap.get("initial_capital", 0)
                    cash = snap.get("cash", 0)
                    market_value = snap.get("market_value", 0)
                    today_pnl = snap.get("today_pnl", 0)
                else:
                    computed = _live_profit(query_uid)
                    if computed is None:
                        continue
                    profit_pct, profit_amount, initial_capital, account_doc, positions = computed
                    cash = account_doc.get("cash_balance", 0)
                    market_value = sum(p["market_value"] for p in positions)
                    today_pnl = sum(p.get("today_pnl_amount", 0.0) for p in positions)

            account_doc = _account.get(query_uid) if _account else None
            stats = _stats.get_stats(query_uid) if account_doc else {"win_rate": 0.0, "total_trades": 0}
            frozen_cash = (account_doc or {}).get("frozen_cash", 0)
            result.append({
                "user_id": uid,
                "username": user.get("nickname", user.get("username", uid)),
                "raw_username": user.get("username", uid),
                "initial_capital": round(initial_capital, 2),
                "cash_balance": round(cash, 2),
                "frozen_cash": round(frozen_cash, 2),
                "market_value": round(market_value, 2),
                "total_asset": round(cash + frozen_cash + market_value, 2),
                "profit_pct": round(profit_pct, 2),
                "profit_amount": round(profit_amount, 2),
                "today_pnl": round(today_pnl, 2),
                "total_fee": round(fee_map.get(query_uid, 0), 2),
                "win_rate": round(stats.get("win_rate", 0.0), 2),
                "total_trades": stats.get("total_trades", 0),
            })
        except Exception as e:
            logger.warning(f"[Ranking] user={user.get('user_id','?')} skipped: {e}")
            continue

    result.sort(key=lambda x: x["profit_pct"], reverse=True)
    for i, r in enumerate(result, 1):
        r["rank"] = i

    total = len(result)
    if limit:
        result = result[offset:offset + limit]

    payload = {
        "success": True,
        "count": len(result),
        "total": total,
        "data": result,
        "live": live,
        "is_trading": is_trading_time(),
    }
    if live:
        with _ranking_live_lock:
            _ranking_live_cache["payload"] = payload
            _ranking_live_cache["at"] = time.time()
    return jsonify(payload)
