from datetime import datetime
from utils.helpers import beijing_now
from typing import Dict, List, Optional
from flask import Blueprint, request, jsonify
from config.database import get_collection
from utils.logger import get_logger
import uuid

logger = get_logger(__name__)
signals_bp = Blueprint("signals", __name__, url_prefix="/api/v1/signals")


def _get_collection():
    return get_collection("agent_signals")


@signals_bp.route("/publish", methods=["POST"])
def publish_signal():
    data = request.get_json() or {}
    required = ["publisher_id", "type", "direction", "target"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    signal = {
        "signal_id": f"sig_{uuid.uuid4().hex[:12]}",
        "publisher_id": data["publisher_id"],
        "publisher_name": data.get("publisher_name", data["publisher_id"]),
        "type": data["type"],
        "direction": data["direction"],
        "target": data["target"],
        "price": data.get("price"),
        "confidence": data.get("confidence", 0.5),
        "reasoning": data.get("reasoning", ""),
        "timestamp": beijing_now().isoformat(),
        "expiry": data.get("expiry", ""),
        "status": "active",
    }
    _get_collection().insert_one(signal)
    return jsonify({"success": True, "data": signal})


@signals_bp.route("/feed", methods=["GET"])
def get_feed():
    limit = int(request.args.get("limit", 50))
    publisher = request.args.get("publisher_id")
    direction = request.args.get("direction")
    signal_type = request.args.get("type")
    since = request.args.get("since")

    query = {"status": "active"}
    if publisher:
        query["publisher_id"] = publisher
    if direction:
        query["direction"] = direction
    if signal_type:
        query["type"] = signal_type
    if since:
        query["timestamp"] = {"$gte": since}

    signals = list(_get_collection().find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit))
    return jsonify({"success": True, "count": len(signals), "data": signals})


@signals_bp.route("/<signal_id>", methods=["GET"])
def get_signal(signal_id: str):
    signal = _get_collection().find_one({"signal_id": signal_id}, {"_id": 0})
    if not signal:
        return jsonify({"error": "Signal not found"}), 404
    return jsonify({"success": True, "data": signal})


@signals_bp.route("/<signal_id>/expire", methods=["POST"])
def expire_signal(signal_id: str):
    result = _get_collection().update_one(
        {"signal_id": signal_id},
        {"$set": {"status": "expired", "expired_at": beijing_now().isoformat()}},
    )
    if result.modified_count == 0:
        return jsonify({"error": "Signal not found"}), 404
    return jsonify({"success": True, "message": "Signal expired"})
