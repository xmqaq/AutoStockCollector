"""融合选股 API：市场感知初筛 + 多策略叠加 + 多哲学辩论 + 仓位建议 + 回测/权重优化。
独立 Blueprint，不影响任何现有路由。
"""
from flask import Blueprint, jsonify, request, Response, stream_with_context, g
from typing import Any, Dict, Optional
import json
import threading
import time

from utils.logger import get_logger
from api.auth_utils import login_required, admin_required
from modules.ai.fusion.progress import acquire_run_lock, get_progress

logger = get_logger(__name__)
fusion_pick_bp = Blueprint("fusion_pick", __name__, url_prefix="/api/v1/fusion-pick")

RESULTS_COL = "fusion_pick_results"


def _run_async(top_n, candidate_pool, strategy_ids, philosophy_ids,
               weight_overrides, filter_overrides):
    try:
        from modules.ai.fusion.engine import FusionPickerEngine
        FusionPickerEngine().run(
            top_n=top_n, candidate_pool=candidate_pool,
            strategy_ids=strategy_ids, philosophy_ids=philosophy_ids,
            weight_overrides=weight_overrides, filter_overrides=filter_overrides,
            mode="full")
    except Exception as e:
        logger.error(f"[fusion] 后台选股失败: {e}")
        from modules.ai.fusion.progress import update_progress
        update_progress(0, f"AI 智选失败: {e}", is_running=False)


def _serialize_dates(doc: Dict[str, Any]) -> Dict[str, Any]:
    for k in ("timestamp", "created_at", "updated_at"):
        if k in doc and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


@fusion_pick_bp.route("/run", methods=["POST"])
@login_required
def run_fusion_pick():
    if not acquire_run_lock():
        return jsonify({"success": False, "error": "已有 AI 智选任务运行中"}), 409
    data = request.get_json() or {}
    top_n = data.get("top_n", 10)
    candidate_pool = data.get("candidate_pool", 50)
    strategy_ids = data.get("strategy_ids", []) or []
    philosophy_ids = data.get("philosophy_ids", []) or []
    weight_overrides = data.get("weight_overrides")
    filter_overrides = data.get("filter_overrides")

    t = threading.Thread(
        target=_run_async,
        args=(top_n, candidate_pool, strategy_ids, philosophy_ids,
              weight_overrides, filter_overrides),
        daemon=True)
    t.start()
    return jsonify({"success": True, "message": "AI 智选已启动"})


@fusion_pick_bp.route("/progress", methods=["GET"])
def progress():
    prog = get_progress()
    prog["updated_at"] = str(prog.get("updated_at", ""))
    return jsonify({"success": True, "data": prog})


@fusion_pick_bp.route("/progress/stream")
def progress_stream():
    def generate():
        while True:
            try:
                prog = get_progress()
                data = json.dumps({"success": True, "data": prog}, default=str)
                yield f"data: {data}\n\n"
                if not prog.get("is_running"):
                    break
            except Exception:
                yield f"data: {json.dumps({'success': True, 'data': {'is_running': False, 'progress': 0, 'status': 'error'}})}\n\n"
                break
            time.sleep(1)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@fusion_pick_bp.route("/result", methods=["GET"])
def result():
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        run_id = request.args.get("run_id")
        if run_id:
            doc = db[RESULTS_COL].find_one({"run_id": run_id}, {"_id": 0})
        else:
            doc = db[RESULTS_COL].find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        if doc:
            _serialize_dates(doc)
        return jsonify({"success": True, "data": doc or {"picks": []}})
    except Exception as e:
        logger.error(f"[fusion] 读取结果失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/history", methods=["GET"])
def history():
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        docs = list(db[RESULTS_COL].find(
            {}, {"_id": 0, "run_id": 1, "timestamp": 1, "market_state": 1,
                 "universe_count": 1, "candidate_count": 1, "mode": 1, "picks": 1},
        ).sort("created_at", -1).limit(20))
        out = []
        for d in docs:
            out.append({
                "run_id": d.get("run_id"),
                "timestamp": d["timestamp"].isoformat() if hasattr(d.get("timestamp"), "isoformat") else d.get("timestamp"),
                "market_state": d.get("market_state"),
                "universe_count": d.get("universe_count"),
                "candidate_count": d.get("candidate_count"),
                "selected_count": len(d.get("picks", [])),
                "mode": d.get("mode"),
            })
        return jsonify({"success": True, "data": out})
    except Exception as e:
        logger.error(f"[fusion] 读取历史失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/market-state", methods=["GET"])
def market_state():
    try:
        from modules.ai.fusion.market_state import MarketStateDetector
        from config.database import DatabaseConfig
        detector = MarketStateDetector()
        state = detector.detect()
        weights_auto = MarketStateDetector.WEIGHT_PRESETS.get(state, {})

        weights_optimized = None
        last_optimized_at = None
        try:
            doc = DatabaseConfig.get_database()["fusion_weight_config"].find_one({"state": state})
            if doc:
                weights_optimized = doc.get("weights")
                upd = doc.get("updated_at")
                last_optimized_at = upd.isoformat() if hasattr(upd, "isoformat") else upd
        except Exception:
            pass

        return jsonify({"success": True, "data": {
            "state": state,
            "description": detector.get_description(state),
            "weights_auto": weights_auto,
            "weights_optimized": weights_optimized,
            "last_optimized_at": last_optimized_at,
        }})
    except Exception as e:
        logger.error(f"[fusion] 市场状态查询失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/backtest", methods=["GET"])
def backtest():
    try:
        from modules.ai.fusion.backtest import FusionBacktest
        try:
            limit = min(int(request.args.get("limit", 30)), 200)
        except (TypeError, ValueError):
            limit = 30
        data = FusionBacktest().evaluate(limit=limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"[fusion] 回测失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/backtest/optimization-signals", methods=["GET"])
def optimization_signals():
    try:
        from modules.ai.fusion.backtest import FusionBacktest
        data = FusionBacktest().get_optimization_signals()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"[fusion] 优化信号失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/optimize-weights", methods=["POST"])
@admin_required
def optimize_weights():
    try:
        from modules.ai.fusion.weight_optimizer import WeightOptimizer
        result = WeightOptimizer().run()
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"[fusion] 权重优化失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fusion_pick_bp.route("/cancel", methods=["POST"])
def cancel():
    from modules.ai.fusion.progress import update_progress
    update_progress(0, "已取消", is_running=False)
    return jsonify({"success": True, "message": "AI 智选已取消"})
