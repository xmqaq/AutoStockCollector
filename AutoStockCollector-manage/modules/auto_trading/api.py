"""Auto-trading API blueprint.

端点：
  GET  /status             仪表盘状态（持仓/盈亏/敞口/统计）
  GET  /signals            融合信号列表（支持 user_id）
  POST /cycle              手动触发一轮
  GET  /config             读取运行时配置
  POST /config             修改运行时配置（持久化到 Mongo）
  GET  /history            轮询历史
  GET  /drawdown-strategy  读取回撤策略
  POST /drawdown-strategy  修改回撤策略
  POST /close-positions    一键平仓
"""
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from utils.helpers import beijing_now
from utils.logger import get_logger

from .executor import UnifiedAutoTrader

logger = get_logger(__name__)
auto_trade_bp = Blueprint("auto_trading", __name__, url_prefix="/api/v1/auto-trading")

# 懒加载：避免模块顶层实例化即连库（UnifiedAutoTrader 构造里 PaperAccount 连 DB），
# 否则 import 本模块（如跑单测）在无 MONGODB_URI 环境会 ValueError。首次请求才构造。
_trader = None


def _get_trader():
    global _trader
    if _trader is None:
        _trader = UnifiedAutoTrader()
    return _trader


def _ok(data: Any = None, msg: str = "ok"):
    return jsonify({"success": True, "data": data, "error": None, "msg": msg})


def _err(msg: str, code: int = 400):
    return jsonify({"success": False, "data": None, "error": msg, "msg": msg}), code


def _resolve_user_id() -> str:
    """优先 query/body 的 user_id，其次 token，最后 default。"""
    uid = request.args.get("user_id")
    if not uid and request.is_json:
        uid = request.get_json(silent=True).get("user_id")
    if uid:
        return uid
    try:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from api.auth_utils import decode_token
            payload = decode_token(auth[7:])
            if payload and payload.get("user_id"):
                return payload["user_id"]
    except Exception:
        pass
    return "default"


@auto_trade_bp.route("/status", methods=["GET"])
def get_status():
    return _ok(_get_trader().get_stats(_resolve_user_id()))


@auto_trade_bp.route("/signals", methods=["GET"])
def get_signals():
    date = request.args.get("date", beijing_now().strftime("%Y-%m-%d"))
    signals = _get_trader().get_signals(date, _resolve_user_id())
    return _ok({"date": date, "signals": signals, "count": len(signals)})


@auto_trade_bp.route("/cycle", methods=["POST"])
def trigger_cycle():
    date = None
    user_id = "default"
    if request.is_json:
        body = request.get_json(silent=True) or {}
        date = body.get("date")
        user_id = body.get("user_id", _resolve_user_id())
    result = _get_trader().run_cycle(user_id, date)
    if result.get("status") == "locked":
        return _err("Previous cycle still running", 429)
    if result.get("status") == "disabled":
        return _err("Auto-trading is disabled", 403)
    return _ok(result)


@auto_trade_bp.route("/config", methods=["GET", "POST"])
def config():
    from .config_store import ConfigStore
    store = ConfigStore()
    if request.method == "GET":
        return _ok(store.to_dict(store.load()))
    # POST：运行时修改配置
    try:
        data = request.get_json(force=True) or {}
        cfg = store.save(data)
        # 清除信号缓存，使新权重立即生效
        _get_trader()._fusion.clear_cache()
        return _ok(store.to_dict(cfg))
    except ValueError as e:
        return _err(str(e), 400)
    except Exception as e:
        logger.error(f"[auto-trading] save config failed: {e}")
        return _err(str(e), 500)


@auto_trade_bp.route("/history", methods=["GET"])
def get_history():
    from config.database import DatabaseConfig
    from .config import AutoTradingConfig as Cfg
    limit = min(int(request.args.get("limit", 50)), 200)
    user_id = request.args.get("user_id")
    try:
        db = DatabaseConfig.get_database()
        query = {"user_id": user_id} if user_id else {}
        docs = list(db[Cfg.LOG_COLLECTION].find(query, {"_id": 0})
                     .sort("cycle_time", -1).limit(limit))
        return _ok(docs)
    except Exception as e:
        return _err(str(e))


@auto_trade_bp.route("/drawdown-strategy", methods=["GET", "POST"])
def drawdown_strategy():
    from .drawdown_strategy import DrawdownStrategyManager
    mgr = DrawdownStrategyManager()
    if request.method == "GET":
        return _ok(mgr.to_dict(mgr.load()))
    try:
        data = request.get_json(force=True) or {}
        cfg = mgr.from_dict(data)
        mgr.save(cfg)
        return _ok(mgr.to_dict(cfg))
    except Exception as e:
        return _err(str(e))


@auto_trade_bp.route("/close-positions", methods=["POST"])
def close_all():
    user_id = "default"
    if request.is_json:
        user_id = request.get_json(silent=True).get("user_id", _resolve_user_id())
    else:
        user_id = _resolve_user_id()
    result = _get_trader().close_all(user_id)
    if result.get("error"):
        return _err(result["error"])
    return _ok(result)
