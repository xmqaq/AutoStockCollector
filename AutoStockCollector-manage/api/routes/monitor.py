"""
AI盯盘相关接口
包含：盯盘配置、盯盘股票、告警管理
支持MongoDB持久化存储
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

monitor_bp = Blueprint("monitor", __name__, url_prefix="/api/v1/monitor")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


@monitor_bp.route("/config", methods=["GET"])
def get_monitor_config():
    """获取盯盘配置"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    config_doc = db["monitor_configs"].find_one({"user_id": user_id})

    if not config_doc:
        default_config = {
            "user_id": user_id,
            "enabled": False,
            "price_rise_threshold": 5.0,
            "price_fall_threshold": 3.0,
            "quick_fall_threshold": 2.0,
            "volume_ratio_threshold": 2.0,
            "shrink_ratio_threshold": 30,
            "main_flow_threshold": 5000,
            "continuous_days": 3,
            "notify_in_app": True,
            "notify_email": False,
            "notify_webhook": False,
            "email": "",
            "webhook_url": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        return jsonify({
            "success": True,
            "data": default_config
        })

    config_doc.pop("_id", None)
    return jsonify({
        "success": True,
        "data": config_doc
    })


@monitor_bp.route("/config", methods=["POST"])
def save_monitor_config():
    """保存盯盘配置"""
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}
    db = _get_db()

    config_doc = {
        "user_id": user_id,
        "enabled": data.get("enabled", False),
        "price_rise_threshold": data.get("price_rise_threshold", 5.0),
        "price_fall_threshold": data.get("price_fall_threshold", 3.0),
        "quick_fall_threshold": data.get("quick_fall_threshold", 2.0),
        "volume_ratio_threshold": data.get("volume_ratio_threshold", 2.0),
        "shrink_ratio_threshold": data.get("shrink_ratio_threshold", 30),
        "main_flow_threshold": data.get("main_flow_threshold", 5000),
        "continuous_days": data.get("continuous_days", 3),
        "notify_in_app": data.get("notify_in_app", True),
        "notify_email": data.get("notify_email", False),
        "notify_webhook": data.get("notify_webhook", False),
        "email": data.get("email", ""),
        "webhook_url": data.get("webhook_url", ""),
        "updated_at": datetime.now().isoformat()
    }

    existing = db["monitor_configs"].find_one({"user_id": user_id})
    if existing:
        db["monitor_configs"].update_one(
            {"user_id": user_id},
            {"$set": config_doc}
        )
    else:
        config_doc["created_at"] = datetime.now().isoformat()
        db["monitor_configs"].insert_one(config_doc)

    return jsonify({
        "success": True,
        "message": "配置已保存"
    })


@monitor_bp.route("/stocks", methods=["GET"])
def get_monitor_stocks():
    """获取盯盘股票列表"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    stocks = list(db["monitor_stocks"].find({"user_id": user_id}))

    for stock in stocks:
        stock.pop("_id", None)
        stock.pop("user_id", None)

    return jsonify({
        "success": True,
        "count": len(stocks),
        "data": stocks
    })


@monitor_bp.route("/stocks", methods=["POST"])
def add_monitor_stock():
    """添加盯盘股票"""
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}
    code = data.get("code")
    name = data.get("name", "")

    if not code:
        return jsonify({"error": "code is required"}), 400

    code = _normalize_code(code)
    db = _get_db()

    existing = db["monitor_stocks"].find_one({"user_id": user_id, "code": code})
    if existing:
        return jsonify({
            "success": False,
            "message": "股票已在盯盘列表中"
        })

    stock_doc = {
        "user_id": user_id,
        "code": code,
        "name": name,
        "price": 0,
        "change_rate": 0,
        "high": 0,
        "low": 0,
        "alert_type": "success",
        "alert_label": "正常",
        "added_at": datetime.now().isoformat()
    }

    db["monitor_stocks"].insert_one(stock_doc)

    return jsonify({
        "success": True,
        "message": "已添加盯盘"
    })


@monitor_bp.route("/stocks/<code>", methods=["DELETE"])
def remove_monitor_stock(code: str):
    """移除盯盘股票"""
    user_id = request.args.get("user_id", "default")
    code = _normalize_code(code)
    db = _get_db()

    result = db["monitor_stocks"].delete_one({"user_id": user_id, "code": code})

    if result.deleted_count == 0:
        return jsonify({
            "success": False,
            "message": "股票不在盯盘列表中"
        })

    return jsonify({
        "success": True,
        "message": "已移除"
    })


@monitor_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """获取告警列表"""
    user_id = request.args.get("user_id", "default")
    limit = int(request.args.get("limit", 50))
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    db = _get_db()

    filter_doc = {"user_id": user_id}
    if unread_only:
        filter_doc["read"] = False

    alerts = list(db["monitor_alerts"].find(
        filter_doc,
        sort=[("created_at", -1)],
        limit=limit
    ))

    unread_count = db["monitor_alerts"].count_documents({"user_id": user_id, "read": False})

    for alert in alerts:
        alert.pop("_id", None)
        alert.pop("user_id", None)

    return jsonify({
        "success": True,
        "count": len(alerts),
        "unread_count": unread_count,
        "data": alerts
    })


@monitor_bp.route("/alerts/<alert_id>/read", methods=["POST"])
def mark_alert_read(alert_id: str):
    """标记告警已读"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    db["monitor_alerts"].update_one(
        {"user_id": user_id, "id": alert_id},
        {"$set": {"read": True}}
    )

    return jsonify({"success": True})


@monitor_bp.route("/alerts/read-all", methods=["POST"])
def mark_all_alerts_read():
    """标记所有告警已读"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    db["monitor_alerts"].update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True}}
    )

    return jsonify({"success": True, "message": "已全部标记已读"})


@monitor_bp.route("/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id: str):
    """删除告警"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    result = db["monitor_alerts"].delete_one({"user_id": user_id, "id": alert_id})

    if result.deleted_count == 0:
        return jsonify({
            "success": False,
            "message": "告警不存在"
        })

    return jsonify({
        "success": True,
        "message": "已删除"
    })


@monitor_bp.route("/alerts/trigger", methods=["POST"])
def trigger_test_alert():
    """触发测试告警"""
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}
    alert_type = data.get("type", "price")

    db = _get_db()
    alert_id = f"alert_{uuid.uuid4().hex[:12]}"

    alert_doc = {
        "user_id": user_id,
        "id": alert_id,
        "code": "SH600000",
        "name": "测试股票",
        "type": alert_type,
        "level": "warning",
        "message": f"测试{alert_type}告警",
        "detail": "这是测试告警内容",
        "read": False,
        "created_at": datetime.now().isoformat()
    }

    db["monitor_alerts"].insert_one(alert_doc)

    return jsonify({
        "success": True,
        "alert_id": alert_id,
        "message": "测试告警已生成"
    })


@monitor_bp.route("/alerts", methods=["POST"])
def create_alert():
    """创建告警（供内部调用）"""
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}

    code = data.get("code")
    name = data.get("name", "")
    alert_type = data.get("type", "price")
    level = data.get("level", "warning")
    message = data.get("message", "")
    detail = data.get("detail", "")

    if not code or not message:
        return jsonify({"error": "code and message are required"}), 400

    db = _get_db()
    alert_id = f"alert_{uuid.uuid4().hex[:12]}"

    alert_doc = {
        "user_id": user_id,
        "id": alert_id,
        "code": code,
        "name": name,
        "type": alert_type,
        "level": level,
        "message": message,
        "detail": detail,
        "read": False,
        "created_at": datetime.now().isoformat()
    }

    db["monitor_alerts"].insert_one(alert_doc)

    return jsonify({
        "success": True,
        "alert_id": alert_id
    })


@monitor_bp.route("/settings", methods=["GET"])
def get_notification_settings():
    """获取通知设置"""
    user_id = request.args.get("user_id", "default")
    db = _get_db()

    settings_doc = db["monitor_settings"].find_one({"user_id": user_id})

    if not settings_doc:
        default_settings = {
            "user_id": user_id,
            "quiet_start": "22:00",
            "quiet_end": "08:00",
            "sound_enabled": True,
            "desktop_enabled": True,
        }
        return jsonify({
            "success": True,
            "data": default_settings
        })

    settings_doc.pop("_id", None)
    return jsonify({
        "success": True,
        "data": settings_doc
    })


@monitor_bp.route("/settings", methods=["POST"])
def save_notification_settings():
    """保存通知设置"""
    user_id = request.args.get("user_id", "default")
    data = request.get_json() or {}
    db = _get_db()

    settings_doc = {
        "user_id": user_id,
        "quiet_start": data.get("quiet_start", "22:00"),
        "quiet_end": data.get("quiet_end", "08:00"),
        "sound_enabled": data.get("sound_enabled", True),
        "desktop_enabled": data.get("desktop_enabled", True),
        "updated_at": datetime.now().isoformat()
    }

    existing = db["monitor_settings"].find_one({"user_id": user_id})
    if existing:
        db["monitor_settings"].update_one(
            {"user_id": user_id},
            {"$set": settings_doc}
        )
    else:
        settings_doc["created_at"] = datetime.now().isoformat()
        db["monitor_settings"].insert_one(settings_doc)

    return jsonify({
        "success": True,
        "message": "通知设置已保存"
    })