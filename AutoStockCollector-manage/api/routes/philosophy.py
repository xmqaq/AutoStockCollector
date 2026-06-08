"""投资哲学 API 端点 - 多 Agent 投资哲学辩论"""
import json
from typing import Dict, Any, Tuple
from flask import Blueprint, request, jsonify, Response
from utils.logger import get_logger

logger = get_logger(__name__)
philosophy_bp = Blueprint("philosophy", __name__, url_prefix="/api/v1/ai/philosophy")


def _get_registry():
    from modules.ai.philosophies.registry import PhilosophyRegistry
    PhilosophyRegistry.init_default()
    return PhilosophyRegistry


# ==================== 投资哲学注册表 ====================


@philosophy_bp.route("/agents", methods=["GET"])
def list_agents():
    """列出所有注册的投资哲学 Agent"""
    archetype_filter = request.args.get("archetype")
    registry = _get_registry()

    if archetype_filter:
        agents = registry.get_by_archetype_value(archetype_filter)
    else:
        agents = registry.get_all()

    return jsonify({
        "success": True,
        "count": len(agents),
        "data": [a.to_registry_entry() for a in agents],
    })


@philosophy_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id):
    """获取单个投资哲学配置"""
    registry = _get_registry()
    philosophy = registry.get(agent_id)
    if not philosophy:
        return jsonify({"error": f"Agent '{agent_id}' not found"}), 404
    return jsonify({
        "success": True,
        "data": philosophy.to_registry_entry(),
    })


@philosophy_bp.route("/archetypes", methods=["GET"])
def list_archetypes():
    """列出所有投资流派"""
    from modules.ai.philosophies.base import Archetype
    return jsonify({
        "success": True,
        "data": [
            {"id": a.value, "name": a.name}
            for a in Archetype
        ],
    })


# ==================== 投资哲学辩论（SSE 流式） ====================


@philosophy_bp.route("/debate/stream", methods=["POST"])
def philosophy_debate_stream():
    """投资哲学辩论 - SSE 流式
    Body: {
        "code": "000001",
        "agents": ["buffett", "lynch", "simons", "dalio"],
        "user_id": "default"
    }
    """
    import asyncio
    from modules.ai.engines.graph_engine import GraphEngine
    from modules.ai.foundation.dal import StockDAL
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    code = data.get("code", "")
    agent_ids = data.get("agents", [])
    user_id = data.get("user_id", "default")

    if not code:
        return jsonify({"error": "code is required"}), 400

    registry = _get_registry()
    if not agent_ids:
        agent_ids = registry.get_ids()

    valid_agents = [aid for aid in agent_ids if registry.get(aid)]
    if not valid_agents:
        return jsonify({"error": "No valid agents found"}), 400

    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            engine = GraphEngine(
                dal=StockDAL(),
                router=LLMRouter(),
                progress_callback=lambda p, m: None,
            )
            engine.build_philosophy_debate_graph(valid_agents)

            yield f"data: {json.dumps({'type': 'start', 'data': {'code': code, 'agents': valid_agents}})}\n\n"

            yield f"data: {json.dumps({'type': 'data:start'})}\n\n"
            data_result = loop.run_until_complete(engine._exec_data(code))
            yield f"data: {json.dumps({'type': 'data:done', 'data': {'stock_code': code}})}\n\n"

            yield f"data: {json.dumps({'type': 'factor:start'})}\n\n"
            factor_result = loop.run_until_complete(
                engine._exec_factor({"data": data_result}, code)
            )
            fd = {'type': 'factor:done', 'data': {
                'dim_scores': factor_result['dim_scores'],
                'weighted_score': factor_result['weighted_score'],
            }}
            yield f"data: {json.dumps(fd)}\n\n"

            agent_signals = []
            roa = factor_result.get("details", {}).get("fundamental", {})
            for aid in valid_agents:
                philosophy = registry.get(aid)
                if not philosophy:
                    continue

                dim_scores = factor_result["dim_scores"]
                details = factor_result["details"]
                signal = philosophy.interpret_signal(dim_scores, details)

                agent_signals.append(signal.to_dict())

                ad = {'type': 'agent:done', 'data': {'agent_id': aid, 'signal': signal.to_dict()}}
                yield f"data: {json.dumps(ad)}\n\n"

            from modules.ai.engines.graph_schemas import ConsensusResult
            consensus = ConsensusResult(
                tendency=sum(s.get("score", 50) for s in agent_signals) / len(agent_signals) / 50 - 1 if agent_signals else 0,
                consensus_level=0.5,
                confidence=0.5,
                high_conviction=False,
                agent_signals=agent_signals,
            )
            vd = {'type': 'verdict', 'data': {
                'code': code,
                'agent_signals': agent_signals,
                'consensus': {
                    'tendency': consensus.tendency,
                    'consensus_level': consensus.consensus_level,
                    'confidence': consensus.confidence,
                    'high_conviction': consensus.high_conviction,
                    'positive_count': sum(1 for s in agent_signals if s.get('action') in ('buy', 'strong_buy')),
                    'negative_count': sum(1 for s in agent_signals if s.get('action') in ('sell', 'strong_sell')),
                },
            }}
            yield f"data: {json.dumps(vd)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Philosophy debate failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        finally:
            loop.close()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@philosophy_bp.route("/stream", methods=["POST"])
def philosophy_stream_alias():
    return philosophy_debate_stream()

@philosophy_bp.route("/analyze", methods=["POST"])
def philosophy_analyze_alias():
    return philosophy_debate_quick()

@philosophy_bp.route("/debate/quick", methods=["POST"])
def philosophy_debate_quick():
    """快速投资哲学辩论（非流式，返回完整结果）"""
    import asyncio
    from modules.ai.engines.graph_engine import GraphEngine
    from modules.ai.foundation.dal import StockDAL
    from modules.ai.foundation.factors import (
        fundamental_score, technical_score, fund_flow_detail_score,
        valuation_detail_score, composite_score,
    )
    from modules.ai.foundation.llm_router import LLMRouter

    data = request.get_json() or {}
    code = data.get("code", "")
    agent_ids = data.get("agents", [])
    user_id = data.get("user_id", "default")

    if not code:
        return jsonify({"error": "code is required"}), 400

    registry = _get_registry()
    if not agent_ids:
        agent_ids = registry.get_ids()

    valid_agents = [aid for aid in agent_ids if registry.get(aid)]
    if not valid_agents:
        return jsonify({"error": "No valid agents found"}), 400

    try:
        dal = StockDAL()
        bundle = dal.get_stock_bundle(code)

        fundamental, fund_detail = fundamental_score(
            roe=bundle.roe, revenue_growth=bundle.revenue_growth,
            profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
            debt_ratio=bundle.debt_ratio, industry=bundle.industry,
        )
        technical, tech_detail = technical_score(
            list(reversed(bundle.closes)) if bundle.closes else [],
            list(reversed(bundle.volumes)) if bundle.volumes else [],
        )
        fund_flow, flow_detail = fund_flow_detail_score(
            main_net_inflow=bundle.main_net_inflow,
            total_amount=bundle.total_amount, turnover_rate=bundle.turnover_rate,
        )
        valuation, val_detail = valuation_detail_score(
            pe=bundle.pe, pb=bundle.pb, industry=bundle.industry,
        )

        dim_pairs: Dict[str, Tuple] = {
            "fundamental": (fundamental, fund_detail),
            "technical": (technical, tech_detail),
            "fund_flow": (fund_flow, flow_detail),
            "valuation": (valuation, val_detail),
        }

        raw_details = {k: v[1] for k, v in dim_pairs.items()}
        flat_details = {}
        for dim, detail in raw_details.items():
            flat: Dict[str, Any] = {"data_available": detail.get("data_available", True)}
            flat["score"] = dim_pairs[dim][0]
            for key, val in detail.items():
                if key == "data_available":
                    continue
                if isinstance(val, dict) and "value" in val:
                    if val["value"] is not None:
                        flat[key] = val["value"]
                    if "score" in val:
                        flat[f"{key}_score"] = val["score"]
                elif isinstance(val, dict) and "score" in val:
                    flat[f"{key}_score"] = val["score"]
                    if val.get("value") is not None:
                        flat[key] = val["value"]
                else:
                    flat[key] = val
            flat_details[dim] = flat

        dim_scores_flat = {k: v[0] for k, v in dim_pairs.items()}

        agent_signals = []
        for aid in valid_agents:
            philosophy = registry.get(aid)
            if philosophy:
                signal = philosophy.interpret_signal(dim_scores_flat, flat_details)
                agent_signals.append(signal.to_dict())

        weighted, _ = composite_score(dim_pairs)
        avg_score = sum(s.get("score", 50) for s in agent_signals) / len(agent_signals) if agent_signals else 50

        return jsonify({
            "success": True,
            "data": {
                "code": code,
                "factor_scores": dim_scores_flat,
                "weighted_score": weighted,
                "agents": agent_signals,
                "summary": {
                    "agent_count": len(agent_signals),
                    "average_score": round(avg_score, 1),
                    "positive": sum(1 for s in agent_signals if s.get("action") in ("buy", "strong_buy")),
                    "negative": sum(1 for s in agent_signals if s.get("action") in ("sell", "strong_sell")),
                    "neutral": sum(1 for s in agent_signals if s.get("action") in ("hold", "watch")),
                },
            },
        })
    except Exception as e:
        logger.error(f"Philosophy debate failed: {e}")
        return jsonify({"error": str(e)}), 500
