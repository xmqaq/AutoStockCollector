"""策略管理 API：选股策略 + 交易策略 CRUD。"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from bson import ObjectId
from typing import Any, Dict

from modules.ai.strategies.storage import StrategyStorage
from modules.ai.strategies.presets import get_selection_presets, get_trading_presets
from modules.ai.strategies.models import INDICATOR_CATALOG
from utils.logger import get_logger

logger = get_logger(__name__)
strategy_bp = Blueprint("strategy", __name__, url_prefix="/api/v1/strategies")
storage = StrategyStorage()


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    for k in ("created_at", "updated_at"):
        if k in doc and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


@strategy_bp.route("", methods=["GET"])
def list_strategies():
    type_filter = request.args.get("type")
    enabled_only = request.args.get("enabled_only", "").lower() in ("true", "1")

    if type_filter in ("selection", "trading"):
        items = storage.list_by_type(type_filter, enabled_only)
    else:
        items = list(storage.find_many({"enabled": True} if enabled_only else {},
                                       sort=[("updated_at", -1)]))

    # 如果集合为空，自动注入预设策略
    if not items:
        _seed_presets()
        if type_filter in ("selection", "trading"):
            items = storage.list_by_type(type_filter)
        else:
            items = list(storage.find_many({}, sort=[("updated_at", -1)]))

    return jsonify({"success": True, "data": [_serialize(d) for d in items]})


@strategy_bp.route("/<sid>", methods=["GET"])
def get_strategy(sid):
    doc = storage.find_one({"_id": ObjectId(sid)})
    if not doc:
        return jsonify({"success": False, "error": "策略不存在"}), 404
    return jsonify({"success": True, "data": _serialize(doc)})


@strategy_bp.route("", methods=["POST"])
def create_strategy():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400
    name = data.get("name", "").strip()
    s_type = data.get("type", "selection")
    if not name:
        return jsonify({"success": False, "error": "策略名称不能为空"}), 400
    if s_type not in ("selection", "trading"):
        return jsonify({"success": False, "error": "type 必须为 selection 或 trading"}), 400

    existing = storage.get_by_name(name)
    if existing:
        return jsonify({"success": False, "error": f"策略 '{name}' 已存在"}), 409

    doc: Dict[str, Any] = {
        "name": name,
        "type": s_type,
        "description": data.get("description", ""),
        "enabled": data.get("enabled", True),
        "indicators": data.get("indicators", []),
        "weights": data.get("weights", {}),
        "filters": data.get("filters", {}),
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    oid = storage.insert_one(doc)
    doc["_id"] = oid
    return jsonify({"success": True, "data": _serialize(doc)}), 201


@strategy_bp.route("/<sid>", methods=["PUT"])
def update_strategy(sid):
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体为空"}), 400

    doc = storage.find_one({"_id": ObjectId(sid)})
    if not doc:
        return jsonify({"success": False, "error": "策略不存在"}), 404

    upd: Dict[str, Any] = {"updated_at": datetime.now()}
    for field in ("name", "type", "description", "enabled", "indicators", "weights", "filters"):
        if field in data:
            upd[field] = data[field]

    if "name" in upd:
        name = upd["name"].strip()
        if not name:
            return jsonify({"success": False, "error": "策略名称不能为空"}), 400
        existing = storage.get_by_name(name)
        if existing and str(existing["_id"]) != sid:
            return jsonify({"success": False, "error": f"策略 '{name}' 已存在"}), 409

    storage.update_one({"_id": ObjectId(sid)}, {"$set": upd})
    updated = storage.find_one({"_id": ObjectId(sid)})
    return jsonify({"success": True, "data": _serialize(updated)})


@strategy_bp.route("/<sid>", methods=["DELETE"])
def delete_strategy(sid):
    doc = storage.find_one({"_id": ObjectId(sid)})
    if not doc:
        return jsonify({"success": False, "error": "策略不存在"}), 404
    storage.delete_one({"_id": ObjectId(sid)})
    return jsonify({"success": True, "message": "已删除"})


@strategy_bp.route("/indicators", methods=["GET"])
def list_indicator_catalog():
    return jsonify({"success": True, "data": INDICATOR_CATALOG})


@strategy_bp.route("/presets", methods=["GET"])
def list_presets():
    s_type = request.args.get("type", "selection")
    if s_type == "trading":
        return jsonify({"success": True, "data": get_trading_presets()})
    return jsonify({"success": True, "data": get_selection_presets()})


@strategy_bp.route("/presets/apply", methods=["POST"])
def apply_presets():
    """强制重新注入所有预设策略（清空后重建）。"""
    storage.delete_many({})
    _seed_presets()
    items = list(storage.find_many({}, sort=[("updated_at", -1)]))
    return jsonify({"success": True, "data": [_serialize(d) for d in items]})


@strategy_bp.route("/<sid>/apply", methods=["POST"])
def apply_to_picker(sid):
    """将选股策略应用到量化选股运行。"""
    doc = storage.find_one({"_id": ObjectId(sid)})
    if not doc:
        return jsonify({"success": False, "error": "策略不存在"}), 404
    if doc.get("type") != "selection":
        return jsonify({"success": False, "error": "仅选股策略可应用到量化选股"}), 400

    from modules.ai.engines.picker import PickerEngine

    strategy_name = doc["name"]
    weights = doc.get("weights", {})
    indicators = doc.get("indicators", [])
    filters = doc.get("filters", {})

    data = request.get_json() or {}
    top_n = data.get("top_n", 10)
    candidate_pool = data.get("candidate_pool", 50)

    def _run():
        try:
            PickerEngine().run(
                strategy=strategy_name,
                top_n=top_n,
                candidate_pool=candidate_pool,
                weight_overrides=weights,
                filter_overrides=filters,
                indicator_config=indicators,
            )
        except Exception as e:
            logger.error(f"策略 '{strategy_name}' 选股失败: {e}")
            from modules.ai.engines.picker import _update_progress
            _update_progress(0, f"选股失败: {e}", is_running=False)

    import threading
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({
        "success": True,
        "message": f"策略 '{strategy_name}' 选股任务已启动",
        "strategy": strategy_name,
    })


@strategy_bp.route("/<sid>/test", methods=["POST"])
def test_strategy(sid):
    """异步测试选股策略（后台运行，通过 /test/result 轮询结果）。"""
    doc = storage.find_one({"_id": ObjectId(sid)})
    if not doc:
        return jsonify({"success": False, "error": "策略不存在"}), 404
    if doc.get("type") != "selection":
        return jsonify({"success": False, "error": "仅选股策略可测试"}), 400

    weights = doc.get("weights", {})
    indicators = doc.get("indicators", [])
    filters = doc.get("filters", {})
    sname = doc["name"]

    data = request.get_json() or {}
    top_n = data.get("top_n", 10)
    candidate_pool = data.get("candidate_pool", 30)

    import threading

    def _run():
        try:
            from modules.ai.engines.picker import PickerEngine, _save_test_result
            result = PickerEngine().preview(
                strategy=sname, top_n=top_n, candidate_pool=candidate_pool,
                weight_overrides=weights, filter_overrides=filters,
                indicator_config=indicators,
            )
            result["is_running"] = False
            result["progress"] = 100
            result["status"] = "测试完成"
            _save_test_result(result)
        except Exception as e:
            logger.error(f"策略 '{sname}' 测试失败: {e}")
            from modules.ai.engines.picker import _save_test_result
            _save_test_result({"is_running": False, "progress": 0, "status": f"测试失败: {e}", "strategy": sname, "picks": []})

    from modules.ai.engines.picker import _save_test_result
    _save_test_result({"is_running": True, "progress": 1, "status": "测试启动中...", "strategy": sname, "picks": []})
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "data": {"strategy": sname, "message": "测试已启动"}})


@strategy_bp.route("/test/result", methods=["GET"])
def get_test_result():
    """查询最新测试结果。"""
    from modules.ai.engines.picker import get_test_result
    result = get_test_result()
    return jsonify({"success": True, "data": result})


def _seed_presets():
    """集合为空时注入预设策略。"""
    existing = storage.count_documents({})
    if existing > 0:
        return
    for doc in get_selection_presets():
        doc["created_at"] = datetime.now()
        doc["updated_at"] = datetime.now()
        storage.upsert_strategy(doc)
    for doc in get_trading_presets():
        doc["created_at"] = datetime.now()
        doc["updated_at"] = datetime.now()
        storage.upsert_strategy(doc)
    logger.info(f"已注入 {len(get_selection_presets()) + len(get_trading_presets())} 条预设策略")
