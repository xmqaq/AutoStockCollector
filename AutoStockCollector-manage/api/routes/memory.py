"""年轮记忆系统 API 端点"""
import json
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Dict
from flask import Blueprint, request, jsonify
from utils.logger import get_logger

logger = get_logger(__name__)
memory_bp = Blueprint("memory", __name__, url_prefix="/api/v1/memory")


def _get_synthesizer():
    from modules.memory.synthesizer import MemorySynthesizer
    return MemorySynthesizer()


def _get_episodic():
    from modules.memory.episodic_memory import EpisodicMemory
    return EpisodicMemory()


def _get_user_id() -> str:
    return request.args.get("user_id") or (request.get_json() or {}).get("user_id") or "default"


# ==================== 用户画像 ====================


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
    user_id = _get_user_id()
    data = request.get_json() or {}
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


# ==================== 持仓记录 ====================


@memory_bp.route("/holdings", methods=["GET"])
def get_holdings():
    user_id = request.args.get("user_id", "default")
    episodic = _get_episodic()
    summary = episodic.get_holding_summary(user_id)
    holdings = episodic.get_current_holdings(user_id)
    return jsonify({
        "success": True,
        "summary": summary,
        "holdings": [h.to_dict() for h in holdings],
    })


@memory_bp.route("/holdings", methods=["POST"])
def add_holding():
    from modules.memory.models import HoldingRecord

    data = request.get_json() or {}
    required = ["code", "buy_price", "shares"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Missing required fields: {required}"}), 400

    record = HoldingRecord(
        user_id=data.get("user_id", "default"),
        code=data["code"],
        stock_name=data.get("stock_name", ""),
        buy_date=data.get("buy_date", beijing_now().strftime("%Y-%m-%d")),
        buy_price=float(data["buy_price"]),
        shares=int(data["shares"]),
        reason=data.get("reason", ""),
    )
    episodic = _get_episodic()
    episodic.record_holding(record)
    return jsonify({"success": True, "message": "Holding recorded"})


# ==================== 分析历史 ====================


@memory_bp.route("/analyses", methods=["GET"])
def get_analyses():
    user_id = request.args.get("user_id", "default")
    code = request.args.get("code")
    episodic = _get_episodic()

    if code:
        analyses = episodic.get_stock_analyses(user_id, code)
    else:
        analyses = episodic.get_recent_analyses(user_id)

    return jsonify({
        "success": True,
        "count": len(analyses),
        "data": analyses,
    })


@memory_bp.route("/analyses/feedback", methods=["POST"])
def record_feedback():
    data = request.get_json() or {}
    user_id = data.get("user_id", "default")
    analysis_id = data.get("analysis_id")
    feedback = data.get("feedback")

    if not all([analysis_id, feedback]):
        return jsonify({"error": "analysis_id and feedback are required"}), 400

    episodic = _get_episodic()
    episodic.record_feedback(user_id, analysis_id, feedback)
    return jsonify({"success": True, "message": "Feedback recorded"})


# ==================== 投资模式 ====================


@memory_bp.route("/patterns", methods=["GET"])
def get_patterns():
    user_id = request.args.get("user_id", "default")
    from modules.memory.semantic_memory import SemanticMemory
    semantic = SemanticMemory()
    patterns = semantic.get_patterns(user_id)
    return jsonify({
        "success": True,
        "count": len(patterns),
        "data": [p.to_dict() for p in patterns],
    })


@memory_bp.route("/patterns/analyze", methods=["POST"])
def analyze_patterns():
    user_id = _get_user_id()
    from modules.memory.semantic_memory import SemanticMemory
    semantic = SemanticMemory()
    patterns = semantic.analyze_patterns(user_id)
    return jsonify({
        "success": True,
        "count": len(patterns),
        "data": [p.to_dict() for p in patterns],
        "message": f"发现 {len(patterns)} 个投资模式",
    })


# ==================== 上下文 ====================


@memory_bp.route("/context", methods=["GET"])
def get_context():
    import asyncio
    user_id = request.args.get("user_id", "default")
    stock_code = request.args.get("code")

    synthesizer = _get_synthesizer()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        context = loop.run_until_complete(
            synthesizer.synthesize(user_id, stock_code)
        )
        loop.close()
        return jsonify({
            "success": True,
            "data": context.to_dict(),
        })
    except Exception as e:
        logger.error(f"Memory context failed: {e}")
        return jsonify({
            "success": True,
            "data": {"user_id": user_id},
        })


@memory_bp.route("/stats", methods=["GET"])
def get_stats():
    user_id = request.args.get("user_id", "default")
    synthesizer = _get_synthesizer()
    stats = synthesizer.get_stats(user_id)
    return jsonify({"success": True, "data": stats})


# ==================== 会话管理 ====================


@memory_bp.route("/session/clear", methods=["POST"])
def clear_session():
    user_id = _get_user_id()
    from modules.memory.working_memory import WorkingMemory
    WorkingMemory().clear_session(user_id)
    return jsonify({"success": True, "message": "Session cleared"})
