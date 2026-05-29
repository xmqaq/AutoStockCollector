"""
持仓管理相关接口
包含：持仓列表、新增、更新、删除、组合分析
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any
import math

position_bp = Blueprint("position", __name__, url_prefix="/api/position")


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


def _get_current_price(code: str) -> float:
    """从K线获取最新收盘价"""
    try:
        from core.storage.mongo_storage import KlineStorage
        storage = KlineStorage()
        kline = storage.find_one({"code": code}, sort=[("date", -1)])
        if kline:
            return float(kline.get("close", 0))
    except Exception:
        pass
    return 0.0


def _get_stock_name(code: str) -> str:
    """获取股票名称"""
    try:
        from core.storage.mongo_storage import StockInfoStorage
        storage = StockInfoStorage()
        info = storage.get_by_code(code)
        if info:
            return info.get("name") or info.get("A股简称") or info.get("公司名称") or code
    except Exception:
        pass
    return code


@position_bp.route("/list", methods=["GET"])
def list_positions():
    """获取持仓列表"""
    from config.database import DatabaseConfig

    user_id = request.args.get("user_id", "default")
    db = DatabaseConfig.get_database()

    positions = list(db["positions"].find({"user_id": user_id}))

    total_market = 0.0
    for p in positions:
        p.pop("_id", None)
        shares = p.get("shares", 0)
        cost = p.get("avg_cost", 0)
        price = _get_current_price(p.get("code", ""))
        if price > 0:
            p["current_price"] = price
            p["market_value"] = round(shares * price, 2)
            p["pnl"] = round(p["market_value"] - shares * cost, 2)
            p["pnl_percent"] = round((p["pnl"] / (shares * cost) * 100) if cost > 0 else 0, 2)
            total_market += p["market_value"]

    for p in positions:
        if total_market > 0:
            p["position_ratio"] = round(p.get("market_value", 0) / total_market * 100, 2)
        else:
            p["position_ratio"] = 0

    positions.sort(key=lambda x: x.get("market_value", 0), reverse=True)

    return jsonify({
        "success": True,
        "count": len(positions),
        "data": positions,
        "total_market_value": round(total_market, 2)
    })


@position_bp.route("/save", methods=["POST"])
def save_position():
    """新增或更新持仓"""
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    user_id = data.get("user_id", "default")

    code = data.get("code")
    if not code:
        return jsonify({"error": "code is required"}), 400

    code = _normalize_code(code)

    shares = data.get("shares", 0)
    avg_cost = data.get("avg_cost", 0.0)
    stop_loss = data.get("stop_loss", 0.0)
    target_price = data.get("target_price", 0.0)

    if shares <= 0:
        return jsonify({"error": "shares must be positive"}), 400

    db = DatabaseConfig.get_database()

    existing = db["positions"].find_one({"user_id": user_id, "code": code})
    if existing:
        return jsonify({
            "success": False,
            "error": "Position already exists, use update instead"
        }), 400

    name = _get_stock_name(code)
    current_price = _get_current_price(code)

    position_doc = {
        "user_id": user_id,
        "code": code,
        "name": name,
        "shares": shares,
        "avg_cost": avg_cost,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "current_price": current_price,
        "market_value": round(shares * current_price, 2) if current_price > 0 else 0,
        "pnl": 0,
        "pnl_percent": 0,
        "position_ratio": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    if current_price > 0 and avg_cost > 0:
        market_value = shares * current_price
        cost_basis = shares * avg_cost
        position_doc["market_value"] = round(market_value, 2)
        position_doc["pnl"] = round(market_value - cost_basis, 2)
        position_doc["pnl_percent"] = round((position_doc["pnl"] / cost_basis * 100), 2)

    db["positions"].insert_one(position_doc)

    return jsonify({
        "success": True,
        "message": "Position saved",
        "data": position_doc
    })


@position_bp.route("/update/<code>", methods=["PUT"])
def update_position(code: str):
    """更新持仓信息"""
    from config.database import DatabaseConfig

    code = _normalize_code(code)
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}

    db = DatabaseConfig.get_database()

    existing = db["positions"].find_one({"user_id": user_id, "code": code})
    if not existing:
        return jsonify({"error": "Position not found"}), 404

    update_fields = {}
    for field in ["shares", "avg_cost", "stop_loss", "target_price"]:
        if field in data:
            update_fields[field] = data[field]

    update_fields["updated_at"] = datetime.now().isoformat()

    if "shares" in update_fields or "avg_cost" in update_fields:
        shares = update_fields.get("shares", existing.get("shares", 0))
        avg_cost = update_fields.get("avg_cost", existing.get("avg_cost", 0))
        current_price = _get_current_price(code)

        if current_price <= 0:
            current_price = existing.get("current_price", avg_cost)

        market_value = shares * current_price
        cost_basis = shares * avg_cost
        update_fields["current_price"] = current_price
        update_fields["market_value"] = round(market_value, 2)
        update_fields["pnl"] = round(market_value - cost_basis, 2)
        update_fields["pnl_percent"] = round((update_fields["pnl"] / cost_basis * 100) if cost_basis > 0 else 0, 2)

    db["positions"].update_one(
        {"user_id": user_id, "code": code},
        {"$set": update_fields}
    )

    updated = db["positions"].find_one({"user_id": user_id, "code": code})
    if updated:
        updated.pop("_id", None)

    return jsonify({
        "success": True,
        "message": "Position updated",
        "data": updated
    })


@position_bp.route("/delete", methods=["DELETE"])
def delete_position():
    """删除持仓"""
    from config.database import DatabaseConfig

    code = request.args.get("code")
    user_id = request.args.get("user_id", "default")

    if not code:
        return jsonify({"error": "code is required"}), 400

    code = _normalize_code(code)
    db = DatabaseConfig.get_database()

    result = db["positions"].delete_one({"user_id": user_id, "code": code})

    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "Position not found"}), 404

    return jsonify({
        "success": True,
        "message": "Position deleted"
    })


@position_bp.route("/batch_save", methods=["POST"])
def batch_save_positions():
    """批量保存持仓"""
    from config.database import DatabaseConfig

    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    positions = data.get("positions", [])

    if not positions:
        return jsonify({"error": "positions is required"}), 400

    db = DatabaseConfig.get_database()
    results = []

    for p in positions:
        code = _normalize_code(p.get("code", ""))
        if not code:
            continue

        shares = p.get("shares", 0)
        avg_cost = p.get("avg_cost", 0.0)
        stop_loss = p.get("stop_loss", 0.0)
        target_price = p.get("target_price", 0.0)

        name = _get_stock_name(code)
        current_price = _get_current_price(code)

        position_doc = {
            "user_id": user_id,
            "code": code,
            "name": name,
            "shares": shares,
            "avg_cost": avg_cost,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "current_price": current_price,
            "market_value": round(shares * current_price, 2) if current_price > 0 else 0,
            "pnl": 0,
            "pnl_percent": 0,
            "position_ratio": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        if current_price > 0 and avg_cost > 0:
            market_value = shares * current_price
            cost_basis = shares * avg_cost
            position_doc["market_value"] = round(market_value, 2)
            position_doc["pnl"] = round(market_value - cost_basis, 2)
            position_doc["pnl_percent"] = round((position_doc["pnl"] / cost_basis * 100), 2)

        db["positions"].update_one(
            {"user_id": user_id, "code": code},
            {"$set": position_doc},
            upsert=True
        )
        results.append(code)

    return jsonify({
        "success": True,
        "message": f"Saved {len(results)} positions",
        "data": results
    })


@position_bp.route("/portfolio", methods=["GET"])
def get_portfolio():
    """获取组合统计"""
    from config.database import DatabaseConfig

    user_id = request.args.get("user_id", "default")
    db = DatabaseConfig.get_database()

    positions = list(db["positions"].find({"user_id": user_id}))

    total_market = 0.0
    total_cost = 0.0

    for p in positions:
        p.pop("_id", None)
        shares = p.get("shares", 0)
        avg_cost = p.get("avg_cost", 0)
        current_price = _get_current_price(p.get("code", ""))

        if current_price <= 0:
            current_price = avg_cost

        market_value = shares * current_price
        cost_basis = shares * avg_cost

        p["current_price"] = current_price
        p["market_value"] = round(market_value, 2)
        p["pnl"] = round(market_value - cost_basis, 2)
        p["pnl_percent"] = round((p["pnl"] / cost_basis * 100) if cost_basis > 0 else 0, 2)

        total_market += market_value
        total_cost += cost_basis

    for p in positions:
        if total_market > 0:
            p["position_ratio"] = round(p.get("market_value", 0) / total_market * 100, 2)
        else:
            p["position_ratio"] = 0

    total_pnl = total_market - total_cost
    total_pnl_percent = round((total_pnl / total_cost * 100) if total_cost > 0 else 0, 2)

    return jsonify({
        "success": True,
        "data": {
            "total_market_value": round(total_market, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": total_pnl_percent,
            "positions": positions,
            "position_count": len(positions)
        }
    })


@position_bp.route("/distribution", methods=["GET"])
def get_distribution():
    """获取持仓分布"""
    from config.database import DatabaseConfig

    user_id = request.args.get("user_id", "default")
    db = DatabaseConfig.get_database()

    positions = list(db["positions"].find({"user_id": user_id}))

    total_market = 0.0
    position_values = []

    for p in positions:
        shares = p.get("shares", 0)
        current_price = _get_current_price(p.get("code", ""))
        if current_price <= 0:
            current_price = p.get("avg_cost", 0)

        market_value = shares * current_price
        total_market += market_value
        position_values.append({
            "code": p.get("code"),
            "name": p.get("name", ""),
            "market_value": market_value
        })

    distribution = []
    for pv in position_values:
        percent = (pv["market_value"] / total_market * 100) if total_market > 0 else 0
        distribution.append({
            "code": pv["code"],
            "name": pv["name"],
            "market_value": round(pv["market_value"], 2),
            "percent": round(percent, 2)
        })

    distribution.sort(key=lambda x: x["market_value"], reverse=True)

    return jsonify({
        "success": True,
        "data": distribution
    })


@position_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """获取持仓预警"""
    from config.database import DatabaseConfig

    user_id = request.args.get("user_id", "default")
    db = DatabaseConfig.get_database()

    positions = list(db["positions"].find({"user_id": user_id}))

    alerts = []

    for p in positions:
        shares = p.get("shares", 0)
        avg_cost = p.get("avg_cost", 0)
        current_price = _get_current_price(p.get("code", ""))

        if current_price <= 0 or avg_cost <= 0:
            continue

        cost_basis = shares * avg_cost
        market_value = shares * current_price
        pnl_percent = (market_value - cost_basis) / cost_basis * 100

        if pnl_percent <= -10:
            alerts.append({
                "code": p.get("code"),
                "name": p.get("name", p.get("code")),
                "label": "止损预警",
                "type": "danger",
                "message": f"亏损已达 {abs(pnl_percent):.2f}%，建议关注"
            })
        elif pnl_percent <= -5:
            alerts.append({
                "code": p.get("code"),
                "name": p.get("name", p.get("code")),
                "label": "亏损预警",
                "type": "warning",
                "message": f"亏损 {abs(pnl_percent):.2f}%"
            })

        stop_loss = p.get("stop_loss", 0)
        if stop_loss > 0 and current_price <= stop_loss:
            alerts.append({
                "code": p.get("code"),
                "name": p.get("name", p.get("code")),
                "label": "触发止损",
                "type": "danger",
                "message": f"当前价已跌破止损位 {stop_loss:.2f}"
            })

    return jsonify({
        "success": True,
        "count": len(alerts),
        "data": alerts
    })