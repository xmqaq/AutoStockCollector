"""用户画像 API（记忆系统其余能力已融合进个股深度分析链路）"""
from flask import Blueprint, request, jsonify
from utils.logger import get_logger

logger = get_logger(__name__)
memory_bp = Blueprint("memory", __name__, url_prefix="/api/v1/memory")


def _get_episodic():
    from modules.memory.episodic_memory import EpisodicMemory
    return EpisodicMemory()


@memory_bp.route("/profile", methods=["GET"])
def get_profile():
    user_id = request.args.get("user_id", "default")
    episodic = _get_episodic()
    profile = episodic.get_profile(user_id)
    if not profile:
        return jsonify({
            "success": True,
            "data": {
                "user_id": user_id,
                "risk_level": "balanced",
                "preferred_industries": [],
                "preferred_strategies": [],
                "holding_horizon": "medium",
            }
        })
    return jsonify({"success": True, "data": profile.to_dict()})


@memory_bp.route("/profile", methods=["PUT"])
def update_profile():
    data = request.get_json() or {}
    user_id = request.args.get("user_id") or data.get("user_id") or "default"
    if not data:
        return jsonify({"error": "No data provided"}), 400

    episodic = _get_episodic()
    allowed_fields = {
        "risk_level", "preferred_industries", "preferred_strategies",
        "holding_horizon",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    episodic.update_profile(user_id, updates)
    return jsonify({"success": True, "message": "Profile updated"})
