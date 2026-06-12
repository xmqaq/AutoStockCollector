"""策略选股 API：多策略合并候选 → 多 Agent 深度分析 → 辩论 → 综合结论。"""
from flask import Blueprint, jsonify, request, Response, stream_with_context
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import threading
import time

from modules.ai.strategies.storage import StrategyStorage
from utils.logger import get_logger
from utils.helpers import beijing_now

logger = get_logger(__name__)
strategy_pick_bp = Blueprint("strategy_pick", __name__, url_prefix="/api/v1/strategy-pick")

storage = StrategyStorage()
_PROGRESS_KEY = "strategy_pick"
_STALE_MINUTES = 10


def _update_progress(progress: int, status: str, is_running: bool = True,
                     extra: Optional[Dict] = None) -> None:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = {
            "progress": progress,
            "status": status,
            "is_running": is_running,
            "updated_at": beijing_now(),
        }
        if extra:
            doc.update(extra)
        db["pick_progress"].update_one(
            {"key": _PROGRESS_KEY}, {"$set": doc}, upsert=True,
        )
    except Exception:
        pass


def _get_progress() -> Dict[str, Any]:
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["pick_progress"].find_one({"key": _PROGRESS_KEY}, {"_id": 0})
        if doc:
            updated = doc.get("updated_at")
            if doc.get("is_running") and updated is not None:
                if beijing_now() - updated > timedelta(minutes=_STALE_MINUTES):
                    doc["is_running"] = False
                    doc["status"] = f"{doc.get('status', '')}（运行已中断，可重新发起）"
            for k in ("updated_at",):
                if k in doc and hasattr(doc[k], "isoformat"):
                    doc[k] = doc[k].isoformat()
            return doc
        return {"is_running": False, "progress": 0, "status": ""}
    except Exception:
        return {"is_running": False, "progress": 0, "status": ""}


def _save_result(result: Dict[str, Any]) -> None:
    try:
        from config.database import DatabaseConfig
        import uuid as uuid_mod
        db = DatabaseConfig.get_database()
        run_id = str(uuid_mod.uuid4())[:8]
        result["run_id"] = run_id
        result["created_at"] = beijing_now()
        db["pick_progress"].update_one(
            {"key": f"{_PROGRESS_KEY}_result"}, {"$set": result}, upsert=True,
        )
        db["pick_progress"].insert_one(dict(result, key=f"strategy_pick_result_v2:{run_id}"))
        # 清理旧历史，保留最近 50 条
        old = list(db["pick_progress"].find(
            {"key": {"$regex": "^strategy_pick_result_v2:"}},
            {"_id": 1}
        ).sort("created_at", -1).skip(50).limit(1000))
        if old:
            db["pick_progress"].delete_many({"_id": {"$in": [o["_id"] for o in old]}})
    except Exception:
        pass


def _get_result(run_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        if run_id:
            doc = db["pick_progress"].find_one(
                {"key": f"strategy_pick_result_v2:{run_id}"}, {"_id": 0, "key": 0})
        else:
            doc = db["pick_progress"].find_one(
                {"key": f"{_PROGRESS_KEY}_result"}, {"_id": 0})
        if doc:
            for k in ("timestamp", "updated_at"):
                if k in doc and hasattr(doc[k], "isoformat"):
                    doc[k] = doc[k].isoformat()
            return doc
    except Exception:
        pass
    return {"picks": [], "status": ""}


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    for k in ("created_at", "updated_at"):
        if k in doc and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


def _get_philosophy_signals(code: str, bundle) -> tuple:
    """运行所有投资哲学 Agent 对单只股票生成信号，返回 (signals, dim_scores, flat_details)。"""
    from modules.ai.foundation import factors
    closes_asc = list(reversed(bundle.closes))
    amounts_asc = list(reversed(bundle.volumes))

    fund_s, fund_d = factors.fundamental_score(
        roe=bundle.roe, revenue_growth=bundle.revenue_growth,
        profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
        debt_ratio=bundle.debt_ratio, industry=bundle.industry)
    tech_s, tech_d = factors.technical_score(closes_asc, amounts_asc)
    flow_s, flow_d = factors.fund_flow_detail_score(
        main_net_inflow=bundle.main_net_inflow, total_amount=bundle.total_amount,
        turnover_rate=bundle.turnover_rate)
    val_s, val_d = factors.valuation_detail_score(pe=bundle.pe, pb=bundle.pb, industry=bundle.industry)

    dim_scores = {"fundamental": fund_s, "technical": tech_s, "fund_flow": flow_s, "valuation": val_s}

    raw_details = {"fundamental": fund_d, "technical": tech_d, "fund_flow": flow_d, "valuation": val_d}
    flat_details: Dict[str, Any] = {}
    for dim, detail in raw_details.items():
        flat: Dict[str, Any] = {"data_available": detail.get("data_available", True), "score": dim_scores[dim]}
        for key, val in detail.items():
            if key == "data_available": continue
            if isinstance(val, dict) and "value" in val:
                if val["value"] is not None: flat[key] = val["value"]
                if "score" in val: flat[f"{key}_score"] = val["score"]
            elif isinstance(val, dict) and "score" in val:
                flat[f"{key}_score"] = val["score"]
                if val.get("value") is not None: flat[key] = val["value"]
            else: flat[key] = val
        flat_details[dim] = flat

    from modules.ai.philosophies.registry import PhilosophyRegistry
    PhilosophyRegistry.init_default()
    signals = []
    for ph in PhilosophyRegistry.get_all():
        try:
            signal = ph.interpret_signal(dim_scores, flat_details)
            signals.append(signal.to_dict())
        except Exception as e:
            logger.warning(f"Philosophy {ph.agent_id} signal failed: {e}")

    comp, comp_details = factors.composite_score(
        {"fundamental": (fund_s, {}), "technical": (tech_s, {}),
         "fund_flow": (flow_s, {}), "valuation": (val_s, {})},
        factors.DEFAULT_WEIGHTS)

    dim_scores_flat = {**dim_scores, "composite": comp}
    return signals, dim_scores_flat, flat_details, comp_details


def _generate_trade_signals(picks: List[Dict]) -> List[Dict]:
    """对比选股结果与当前持仓，生成买卖信号。"""
    try:
        from modules.paper_trading.trade_engine import TradeEngine
        positions, _ = TradeEngine().get_positions("default")
    except Exception:
        positions = []

    held = {p["code"]: p for p in positions}
    picked = {p["code"] for p in picks}

    signals: List[Dict] = []

    for p in picks:
        code = p["code"]
        composite = p.get("composite", 0) or 0
        hp = held.get(code)

        if hp is None:
            if composite >= 72:
                action = "买入"
            elif composite >= 55:
                action = "关注"
            else:
                action = "观望"
        else:
            if composite >= 72:
                action = "加仓"
            elif composite >= 55:
                action = "持有"
            else:
                action = "减仓"

        priority = "高" if composite >= 72 else ("中" if composite >= 55 else "低")

        reason_parts = [f"综合评分{composite:.0f}"]
        if hp:
            reason_parts.append(f"当前持仓{hp['shares']}股")
            if action in ("加仓", "持有"):
                reason_parts.append("建议继续持有或加仓")
            else:
                reason_parts.append("建议减仓")
        else:
            reason_parts.append(f"未持仓")
            if action == "买入":
                reason_parts.append("建议买入建仓")

        signals.append({
            "code": code,
            "name": p.get("name", ""),
            "action": action,
            "priority": priority,
            "composite": composite,
            "current_shares": hp["shares"] if hp else 0,
            "reason": "，".join(reason_parts),
        })

    # 已持仓但未入选的 → 卖出
    for code, hp in held.items():
        if code not in picked:
            signals.append({
                "code": code,
                "name": hp.get("name", ""),
                "action": "卖出",
                "priority": "高",
                "composite": None,
                "current_shares": hp["shares"],
                "reason": f"未入选本次选股结果，持仓{hp['shares']}股建议卖出清仓",
            })

    action_order = {"买入": 0, "加仓": 1, "关注": 2, "持有": 3, "观望": 4, "减仓": 5, "卖出": 6}
    signals.sort(key=lambda s: (action_order.get(s["action"], 99), -(s.get("composite") or 0)))
    return signals


def _build_portfolio_suggestion(picks: List[Dict], signals: List[Dict], max_positions: int = 5) -> Dict[str, Any]:
    """从买卖信号和选股结果生成持仓组合建议（行业分散 + 评分加权）。
    max_positions: 精选组合最大持仓数量。
    """
    candidates = []
    pick_map = {p["code"]: p for p in picks}
    buy_actions = {"买入", "加仓", "关注"}
    for s in signals:
        if s["action"] in buy_actions:
            p = pick_map.get(s["code"])
            if p:
                candidates.append({
                    "code": s["code"], "name": s["name"],
                    "industry": p.get("industry", "未知"),
                    "composite": float(s.get("composite") or 0),
                    "action": s["action"],
                })
    if not candidates:
        return {"positions": [], "total_count": 0, "industry_count": 0, "max_industry_pct": 0}

    candidates.sort(key=lambda x: -x["composite"])
    # 精选：只取评分最高的 max_positions 只
    candidates = candidates[:max_positions]

    # 行业分散：同一行业最多占 30%
    max_per_industry = max(1, round(len(candidates) * 0.3))
    industry_groups: Dict[str, List[Dict]] = {}
    for c in candidates:
        industry_groups.setdefault(c["industry"], []).append(c)

    selected = []
    for ind, group in industry_groups.items():
        keep = group[:max_per_industry]
        selected.extend(keep)

    selected.sort(key=lambda x: -x["composite"])

    # 评分加权仓位
    total_score = sum(c["composite"] for c in selected) or 1
    positions = []
    cumulative = 0.0
    N = len(selected)
    for i, c in enumerate(selected):
        weight = round(c["composite"] / total_score * 100, 1)
        cumulative += weight
        positions.append({
            "code": c["code"], "name": c["name"],
            "industry": c["industry"], "composite": c["composite"],
            "action": c["action"],
            "weight": weight,
            "cumulative": round(cumulative, 1),
        })

    # 统计行业分布
    ind_counts: Dict[str, int] = {}
    for p in positions:
        ind_counts[p["industry"]] = ind_counts.get(p["industry"], 0) + 1
    total_pos = len(positions)
    max_ind_pct = round(max(ind_counts.values()) / total_pos * 100, 1) if total_pos else 0

    return {
        "positions": positions,
        "total_count": total_pos,
        "industry_count": len(ind_counts),
        "max_industry_pct": max_ind_pct,
        "industry_distribution": {ind: {"count": cnt, "pct": round(cnt / total_pos * 100, 1)}
                                  for ind, cnt in sorted(ind_counts.items(), key=lambda x: -x[1])},
    }


def _build_debate_consensus(agent_signals: List[Dict]) -> Dict[str, Any]:
    """从多个 Agent 信号构建共识结果。"""
    if not agent_signals:
        return {"tendency": 0, "consensus_level": 0, "confidence": 0,
                "positive_count": 0, "negative_count": 0, "neutral_count": 0}

    scores = [s.get("score", 50) for s in agent_signals]
    actions = [s.get("action", "hold") for s in agent_signals]
    avg_score = sum(scores) / len(scores)
    tendency = round((avg_score - 50) / 50, 3)

    # 分歧度：score 的标准差 / 100
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
    divergence = (variance ** 0.5) / 100 if scores else 0
    consensus_level = round(max(0, min(1, 1 - divergence)), 2)
    confidence = round(0.5 + consensus_level * 0.3, 2)

    positive = sum(1 for a in actions if a in ("strong_buy", "buy"))
    negative = sum(1 for a in actions if a in ("strong_sell", "sell"))
    neutral = len(actions) - positive - negative

    return {
        "tendency": tendency,
        "consensus_level": consensus_level,
        "confidence": confidence,
        "high_conviction": divergence < 0.2,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "avg_score": round(avg_score, 1),
        "agent_count": len(agent_signals),
    }


def _generate_debate_summary(all_debates: List[Dict], picks: List[Dict]) -> str:
    """对整体选股结果生成辩论摘要。"""
    try:
        from modules.ai.foundation.llm_router import LLMRouter
        from modules.ai.content_risk import sanitize_text
        router = LLMRouter()

        total = len(all_debates)
        if total == 0: return ""

        avg_consensus = sum(d.get("consensus", {}).get("consensus_level", 0.5) for d in all_debates) / total
        avg_tendency = sum(d.get("consensus", {}).get("tendency", 0) for d in all_debates) / total
        avg_confidence = sum(d.get("consensus", {}).get("confidence", 0.5) for d in all_debates) / total
        total_positive = sum(d.get("consensus", {}).get("positive_count", 0) for d in all_debates)
        total_negative = sum(d.get("consensus", {}).get("negative_count", 0) for d in all_debates)

        lines = []
        for i, p in enumerate(picks[:10], 1):
            sc = p.get("scores", {})
            debate = next((d for d in all_debates if d.get("code") == p.get("code")), None)
            consensus = debate.get("consensus", {}) if debate else {}
            signal_cnt = consensus.get("agent_count", 0)
            pos = consensus.get("positive_count", 0)
            neg = consensus.get("negative_count", 0)
            lines.append(
                f"{i}. {p.get('code','')} {p.get('name','')} "
                f"综合={p.get('composite',0):.0f} 基本面={sc.get('fundamental',0):.0f} "
                f"技术面={sc.get('technical',0):.0f} 资金面={sc.get('fund_flow',0):.0f} "
                f"估值面={sc.get('valuation',0):.0f} 行业={p.get('industry','')} "
                f"辩论: {signal_cnt}位Agent|看多{pos}|看空{neg}"
            )

        prompt = (
            "你是一位专业的A股投资顾问。以下是多策略选股 + 多Agent深度分析 + 多投资哲学辩论后的股票列表"
            f"（共{len(picks)}只精选股票，{total}只经辩论，"
            f"整体共识度{avg_consensus*100:.0f}%，倾向度{avg_tendency:.2f}）：\n\n"
            + "\n".join(lines)
            + f"\n\n整体辩论统计：共识度{avg_consensus*100:.0f}%，信心{avg_confidence*100:.0f}%，"
              f"看多信号{total_positive}次，看空信号{total_negative}次。"
              f"{'市场整体偏乐观' if avg_tendency > 0.1 else '市场整体偏谨慎' if avg_tendency < -0.1 else '市场看法分歧'}。"
            + "\n\n请直接给出投资建议，严格遵守：\n"
            "1. 不要复述题目或股票列表，直接输出结论；\n"
            "2. 语言简洁，总字数控制在300字以内；\n"
            "3. 格式：\n\n"
            "**综合研判**\n一句话总结市场共识\n\n"
            "**优先关注**\n- 股票名：理由（含辩论共识度）\n\n"
            "**风险提示**\n- 需注意的风险点\n\n"
            "**配置建议**\n一句话仓位配置建议。"
        )
        result = router.chat(prompt, use_cache=False, task_type="stock_analysis")
        if result.success and result.data:
            raw = result.data.get("content", "") if isinstance(result.data, dict) else str(result.data)
            text, _ = sanitize_text(str(raw))
            return text.strip() or ""
    except Exception as e:
        logger.warning(f"Debate summary failed: {e}")
    return ""


def _acquire_run_lock() -> bool:
    try:
        from datetime import timedelta
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        now = beijing_now()
        stale_before = now - timedelta(minutes=_STALE_MINUTES)
        claimed = db["pick_progress"].find_one_and_update(
            {"key": _PROGRESS_KEY,
             "$or": [{"is_running": {"$ne": True}},
                     {"updated_at": {"$lt": stale_before}}]},
            {"$set": {"is_running": True, "progress": 5,
                      "status": "正在加载股票池...", "updated_at": now}},
        )
        if claimed is not None:
            return True
        if db["pick_progress"].find_one({"key": _PROGRESS_KEY}) is None:
            db["pick_progress"].update_one(
                {"key": _PROGRESS_KEY},
                {"$set": {"is_running": True, "progress": 5,
                          "status": "正在加载股票池...", "updated_at": now}},
                upsert=True,
            )
            return True
        return False
    except Exception:
        return True


def _run_pipeline(strategy_ids: List[str], top_n: int, per_strategy_top: int,
                   agent_ids: Optional[List[str]] = None,
                   philosophy_ids: Optional[List[str]] = None) -> None:
    """后台流水线：多策略 preview → 合并去重 → 多 Agent 深度分析 → 辩论 → 排序。"""
    try:
        from modules.ai.engines.picker import PickerEngine
        from modules.ai.engines.analysis import AnalysisEngine
        from modules.ai.foundation.dal import StockDAL
        from modules.ai.foundation.llm_router import LLMRouter
        from modules.ai.philosophies.registry import PhilosophyRegistry
        from concurrent.futures import ThreadPoolExecutor, as_completed

        dal = StockDAL()
        analysis_engine = AnalysisEngine(dal=dal)
        picker = PickerEngine(dal=dal, analysis_engine=analysis_engine)

        # 加载选中的 MongoDB AI Agent 配置
        agents: List[Dict[str, Any]] = []
        if agent_ids:
            try:
                from config.database import DatabaseConfig
                db = DatabaseConfig.get_database()
                for aid in agent_ids:
                    agent = db["ai_agents"].find_one({"id": aid}, {"_id": 0})
                    if agent and agent.get("enabled", True):
                        agents.append(agent)
            except Exception as e:
                logger.warning(f"Failed to load agents: {e}")

        # 初始化投资哲学注册表
        PhilosophyRegistry.init_default()
        selected_philosophies: List = []
        if philosophy_ids:
            for pid in philosophy_ids:
                ph = PhilosophyRegistry.get(pid)
                if ph:
                    selected_philosophies.append(ph)
        use_philosophy = bool(selected_philosophies)

        # ── 阶段1：多策略选股，合并候选 ──
        all_candidates: Dict[str, Dict[str, Any]] = {}
        code_strategies: Dict[str, List[str]] = {}
        total_strategies = len(strategy_ids)

        def _preview_one(sid: str, idx: int) -> Optional[Dict]:
            try:
                doc = storage.find_one({"_id": __import__("bson").ObjectId(sid)})
                if not doc or doc.get("type") != "selection":
                    return None
                sname = doc["name"]
                weights = doc.get("weights", {})
                indicators = doc.get("indicators", [])
                filters = doc.get("filters", {})
                r = picker.preview(
                    strategy=sname, top_n=per_strategy_top, candidate_pool=per_strategy_top * 3,
                    weight_overrides=weights, filter_overrides=filters, indicator_config=indicators)
                return {"name": sname, "picks": r.get("picks", [])}
            except Exception as e:
                logger.warning(f"策略 preview 失败 sid={sid}: {e}")
                return None

        preview_exec = ThreadPoolExecutor(max_workers=min(4, total_strategies))
        try:
            fut_map = {preview_exec.submit(_preview_one, sid, idx): (sid, idx) for idx, sid in enumerate(strategy_ids)}
            for fut in as_completed(fut_map):
                sid, idx = fut_map[fut]
                result = fut.result()
                if not result:
                    continue
                sname = result["name"]
                pct = int((idx / total_strategies) * 30)
                _update_progress(pct, f"策略选股 {idx + 1}/{total_strategies}：{sname}...")
                for pick in result["picks"]:
                    code = pick["code"]
                    if code not in code_strategies: code_strategies[code] = []
                    if sname not in code_strategies[code]: code_strategies[code].append(sname)
                    if code not in all_candidates or pick.get("composite", 0) > all_candidates[code].get("composite", 0):
                        pick["from_strategy"] = sname
                        all_candidates[code] = pick
        finally:
            preview_exec.shutdown(wait=False)

        if not all_candidates:
            _update_progress(100, "无候选股票", is_running=False)
            _save_result({"picks": [], "status": "无候选股票", "timestamp": beijing_now(), "pick_config": {"strategy_ids": strategy_ids, "agent_ids": agent_ids or [], "philosophy_ids": philosophy_ids or [], "top_n": top_n}})
            return

        for code, pick in all_candidates.items():
            pick["from_strategies"] = code_strategies.get(code, [pick.get("from_strategy", "")])

        merged = sorted(all_candidates.values(), key=lambda x: x.get("composite", 0), reverse=True)
        merged = merged[:top_n]
        codes = [p["code"] for p in merged]

        _update_progress(32, f"合并候选 {len(all_candidates)} 只，精选 {len(codes)} 只，开始多 Agent 深度分析...")

        # ── 阶段2：多 Agent 并发深度分析 ──

        analyzed: List[Dict[str, Any]] = []
        total_c = len(codes)
        done_n = 0
        _ANALYSIS_WORKERS = 6

        def _analyze_one(code: str) -> Optional[Dict[str, Any]]:
            try:
                if not agents:
                    return analysis_engine.analyze(code, use_cache=False)
                bundle = dal.get_stock_bundle(code)
                closes_asc = list(reversed(bundle.closes))
                amounts_asc = list(reversed(bundle.volumes))

                from modules.ai.foundation import factors
                fund_s, _ = factors.fundamental_score(
                    roe=bundle.roe, revenue_growth=bundle.revenue_growth,
                    profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
                    debt_ratio=bundle.debt_ratio, industry=bundle.industry)
                tech_s, _ = factors.technical_score(closes_asc, amounts_asc)
                flow_s, _ = factors.fund_flow_detail_score(
                    main_net_inflow=bundle.main_net_inflow, total_amount=bundle.total_amount,
                    turnover_rate=bundle.turnover_rate)
                val_s, _ = factors.valuation_detail_score(pe=bundle.pe, pb=bundle.pb, industry=bundle.industry)
                comp, comp_details = factors.composite_score(
                    {"fundamental": (fund_s, {}), "technical": (tech_s, {}),
                     "fund_flow": (flow_s, {}), "valuation": (val_s, {})}, factors.DEFAULT_WEIGHTS)
                scores = {"fundamental": fund_s, "technical": tech_s, "fund_flow": flow_s, "valuation": val_s, "composite": comp}

                data_context = (
                    f"【股票数据】\n- 代码：{bundle.code}，名称：{bundle.name}，行业：{bundle.industry}\n"
                    f"- 当前价：{bundle.realtime_price or (bundle.closes[0] if bundle.closes else 'N/A')}\n"
                    f"- PE(TTM)：{bundle.pe or 'N/A'}，PB：{bundle.pb or 'N/A'}\n"
                    f"- ROE：{bundle.roe or 'N/A'}，毛利率：{bundle.gross_margin or 'N/A'}\n"
                    f"- 营收同比：{bundle.revenue_growth or 'N/A'}，净利润同比：{bundle.profit_growth or 'N/A'}\n"
                    f"- 主力净流入：{bundle.main_net_inflow or 'N/A'}，换手率：{bundle.turnover_rate or 'N/A'}\n"
                    f"\n【因子得分】\n基本面={fund_s:.0f} 技术面={tech_s:.0f} 资金面={flow_s:.0f} 估值面={val_s:.0f} 综合={comp:.0f}\n"
                )
                from modules.ai.content_risk import sanitize_text
                agent_analyses = []
                llm_payload = None; source = "factor"

                def _call_agent(agent: Dict) -> Optional[Dict]:
                    try:
                        router = LLMRouter()
                        prompt = f"{agent['system_prompt']}\n\n{data_context}\n请给出分析结论，包含：summary（一句话总结）、recommendation（操作建议）、risk_factors（风险列表，JSON格式）。"
                        result = router.chat(prompt, use_cache=False, task_type="stock_analysis")
                        if result.success and result.data:
                            data = result.data
                            summary, _ = sanitize_text(str(data.get("summary", "")))
                            recommendation, _ = sanitize_text(str(data.get("recommendation", "")))
                            risks = [sanitize_text(str(r))[0] for r in (data.get("risk_factors") or [])]
                            return {"agent_id": agent.get("id"), "agent_name": agent.get("name"),
                                    "summary": summary, "recommendation": recommendation, "risk_factors": risks}
                    except Exception as e_agent:
                        logger.warning(f"Agent {agent.get('id')} analyze {code} failed: {e_agent}")
                    return None

                if agents:
                    agent_exec = ThreadPoolExecutor(max_workers=min(4, len(agents)))
                    try:
                        agent_futs = {agent_exec.submit(_call_agent, a): a for a in agents}
                        for af in as_completed(agent_futs):
                            payload = af.result()
                            if payload:
                                agent_analyses.append(payload)
                                if llm_payload is None:
                                    llm_payload = payload
                                    source = "llm"
                    finally:
                        agent_exec.shutdown(wait=False)

                return {"code": bundle.code, "name": bundle.name, "industry": bundle.industry,
                        "scores": scores, "score_details": comp_details,
                        "llm": llm_payload, "agent_analyses": agent_analyses, "source": source}
            except Exception as e1:
                logger.warning(f"LLM analyze {code} failed: {e1}, trying factor-only")
                try: return analysis_engine.analyze_factor_only(code)
                except Exception as e2:
                    logger.warning(f"Factor-only analyze {code} also failed: {e2}")
                    return None

        executor = ThreadPoolExecutor(max_workers=_ANALYSIS_WORKERS)
        try:
            future_map = {executor.submit(_analyze_one, code): code for code in codes}
            budget = 60 * max(1, -(-total_c // _ANALYSIS_WORKERS))
            try:
                for future in as_completed(list(future_map), timeout=budget):
                    code = future_map.pop(future)
                    try:
                        res = future.result()
                        if res:
                            sp = next((p for p in merged if p["code"] == code), {})
                            composite = res.get("scores", {}).get("composite", 50)
                            ss = sp.get("composite", 50) * 20
                            analyzed.append({
                                "code": code, "name": res.get("name", ""), "industry": res.get("industry", ""),
                                "composite": round(composite * 0.7 + ss * 0.3, 1),
                                "scores": res.get("scores", {}), "score_details": res.get("score_details", {}),
                                "llm": res.get("llm"), "agent_analyses": res.get("agent_analyses", []),
                                "source": res.get("source", "factor"),
                                "from_strategy": sp.get("from_strategy", ""),
                                "from_strategies": sp.get("from_strategies", []),
                                "strategy_score": round(sp.get("composite", 0), 1),
                                "agent_analysis": res.get("llm"),
                            })
                    except Exception as e: logger.warning(f"深度分析 {code} 失败: {e}")
                    done_n += 1
                    _update_progress(32 + int(done_n / total_c * 30), f"深度分析 {done_n}/{total_c} 只...")
            except Exception: pass
            for future, code in future_map.items():
                future.cancel(); done_n += 1
                _update_progress(32 + int(done_n / total_c * 30), f"深度分析 {done_n}/{total_c} 只...")
        finally:
            executor.shutdown(wait=False)

        # ── 阶段3：投资哲学辩论 ──
        analyzed.sort(key=lambda x: x.get("composite", 0), reverse=True)
        logger.info(f"Strategy-pick: {len(analyzed)} stocks analyzed from {len(codes)} codes")

        _MAX_PER_INDUSTRY = 3
        final_picks: List[Dict[str, Any]] = []
        industry_count: Dict[str, int] = {}
        for item in analyzed:
            ind = item.get("industry") or ""
            if ind and industry_count.get(ind, 0) >= _MAX_PER_INDUSTRY: continue
            final_picks.append(item)
            if ind: industry_count[ind] = industry_count.get(ind, 0) + 1

        # 辩论阶段（多股票并行，每只带 timeout）
        debate_results: List[Dict[str, Any]] = []
        total_final = len(final_picks)

        def _debate_one(code: str) -> Optional[Dict]:
            try:
                bundle = dal.get_stock_bundle(code)
                if bundle is None:
                    raise ValueError(f"get_stock_bundle returned None for {code}")
                signals, dim_scores, flat_details, comp_details = _get_philosophy_signals(code, bundle)

                if use_philosophy:
                    filtered_signals = [s for s in signals if s.get("agent_id") in philosophy_ids]
                else:
                    filtered_signals = signals

                consensus = _build_debate_consensus(filtered_signals) if filtered_signals else None
                return {"signals": filtered_signals, "consensus": consensus, "dim_scores": dim_scores}
            except Exception as e:
                logger.warning(f"Debate failed for {code}: {e}")
                return None

        debate_exec = ThreadPoolExecutor(max_workers=min(4, total_final))
        try:
            fut_map = {debate_exec.submit(_debate_one, pick["code"]): pick for pick in final_picks}
            done_count = 0
            for fut in as_completed(fut_map):
                pick = fut_map[fut]
                code = pick.get("code", "")
                result = None
                try:
                    result = fut.result(timeout=30)
                except Exception as e:
                    logger.warning(f"Debate timeout/error for {code}: {e}")
                done_count += 1
                _update_progress(65 + int(done_count / total_final * 30),
                                 f"投资哲学辩论 {done_count}/{total_final}：{code}...")
                if result:
                    pick["debate_signals"] = result["signals"]
                    pick["debate_consensus"] = result["consensus"]
                    pick["debate_dim_scores"] = result["dim_scores"]
                    debate_results.append({
                        "code": code,
                        "name": pick.get("name", ""),
                        "signals": result["signals"],
                        "consensus": result["consensus"],
                    })
                else:
                    pick["debate_signals"] = []
                    pick["debate_consensus"] = None
                    debate_results.append({"code": code, "name": pick.get("name", ""), "signals": [], "consensus": None})
        finally:
            debate_exec.shutdown(wait=False)

        _update_progress(96, "综合研判中...")

        strategy_stats: Dict[str, int] = {}
        for p in final_picks:
            for s in p.get("from_strategies", []): strategy_stats[s] = strategy_stats.get(s, 0) + 1

        # ── 组合级绩效指标 ──
        scores_list = [p.get("composite", 0) for p in final_picks if p.get("composite") is not None]
        industry_dist: Dict[str, int] = {}
        dim_totals: Dict[str, float] = {}
        dim_count = 0
        for p in final_picks:
            ind = p.get("industry") or "未知"
            industry_dist[ind] = industry_dist.get(ind, 0) + 1
            sc = p.get("scores") or {}
            for k in ("fundamental", "technical", "fund_flow", "valuation"):
                v = sc.get(k)
                if v is not None:
                    dim_totals[k] = dim_totals.get(k, 0) + v
            dim_count += 1

        total_picks = len(final_picks)
        portfolio_metrics = {
            "avg_composite": round(sum(scores_list) / len(scores_list), 1) if scores_list else 0,
            "composite_std": round((sum((s - sum(scores_list) / len(scores_list)) ** 2 for s in scores_list) / len(scores_list)) ** 0.5, 1) if len(scores_list) > 1 else 0,
            "composite_max": max(scores_list) if scores_list else 0,
            "composite_min": min(scores_list) if scores_list else 0,
            "industry_count": len(industry_dist),
            "industry_hhi": round(sum((c / total_picks) ** 2 for c in industry_dist.values()), 3) if total_picks else 0,
            "top_industry": max(industry_dist, key=industry_dist.get) if industry_dist else "",
            "top_industry_pct": round(max(industry_dist.values()) / total_picks * 100, 1) if industry_dist else 0,
            "dimension_avg": {k: round(v / dim_count, 1) for k, v in sorted(dim_totals.items())} if dim_count else {},
        }

        # 辩论摘要
        debate_summary = _generate_debate_summary(debate_results, final_picks) if debate_results else ""

        # 买卖信号（对比持仓）
        trade_signals = _generate_trade_signals(final_picks)
        portfolio_suggestion = _build_portfolio_suggestion(final_picks, trade_signals, max_positions=5)

        _save_result({
            "picks": final_picks,
            "debate_results": debate_results,
            "debate_summary": debate_summary,
            "ai_summary": debate_summary,
            "strategy_count": total_strategies,
            "merged_count": len(all_candidates),
            "selected_count": len(final_picks),
            "strategy_stats": strategy_stats,
            "trade_signals": trade_signals,
            "portfolio_suggestion": portfolio_suggestion,
            "portfolio_metrics": portfolio_metrics,
            "timestamp": beijing_now(),
            "pick_config": {"strategy_ids": strategy_ids, "agent_ids": agent_ids or [], "philosophy_ids": philosophy_ids or [], "top_n": top_n},
        })

        _update_progress(100, "策略选股完成", is_running=False)

    except Exception as e:
        logger.error(f"策略选股流水线失败: {e}")
        _update_progress(0, f"策略选股失败: {e}", is_running=False)



@strategy_pick_bp.route("/run", methods=["POST"])
def run_strategy_pick():
    """启动策略选股流水线。"""
    if not _acquire_run_lock():
        return jsonify({"success": False, "error": "已有策略选股任务运行中或上次运行尚未完成"}), 409

    data = request.get_json() or {}
    strategy_ids = data.get("strategy_ids", [])
    top_n = data.get("top_n", 20)
    per_strategy_top = data.get("per_strategy_top", 15)
    agent_ids = data.get("agent_ids", [])
    philosophy_ids = data.get("philosophy_ids", [])

    if not strategy_ids:
        return jsonify({"success": False, "error": "请至少选择一个策略"}), 400

    valid_ids = []
    for sid in strategy_ids:
        try:
            from bson import ObjectId
            doc = storage.find_one({"_id": ObjectId(sid)})
            if doc and doc.get("type") == "selection":
                valid_ids.append(sid)
        except Exception: continue

    if not valid_ids:
        return jsonify({"success": False, "error": "未找到有效选股策略"}), 400

    import uuid as uuid_mod
    _CURRENT_RUN_ID = str(uuid_mod.uuid4())[:8]
    _update_progress(1, "策略选股启动中...", extra={"strategy_ids": valid_ids, "run_id": _CURRENT_RUN_ID})
    t = threading.Thread(target=_run_pipeline,
                         args=(valid_ids, top_n, per_strategy_top, agent_ids, philosophy_ids), daemon=True)
    t.start()
    return jsonify({"success": True, "message": f"策略选股已启动，共 {len(valid_ids)} 个策略"})


@strategy_pick_bp.route("/progress", methods=["GET"])
def get_progress():
    prog = _get_progress()
    prog["updated_at"] = str(prog.get("updated_at", ""))
    return jsonify({"success": True, "data": prog})


@strategy_pick_bp.route("/progress/stream")
def progress_stream():
    """SSE 流式输出选股进度。"""
    def generate():
        while True:
            try:
                prog = _get_progress()
                data = json.dumps({"success": True, "data": prog}, default=str)
                yield f"data: {data}\n\n"
                if not prog.get("is_running"):
                    break
            except Exception:
                yield f"data: {json.dumps({'success': True, 'data': {'is_running': False, 'progress': 0, 'status': 'error'}})}\n\n"
                break
            time.sleep(1)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@strategy_pick_bp.route("/result", methods=["GET"])
def get_result():
    run_id = request.args.get("run_id")
    result = _get_result(run_id=run_id)
    return jsonify({"success": True, "data": result})


@strategy_pick_bp.route("/history", methods=["GET"])
def get_result_history():
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        docs = list(db["pick_progress"].find(
            {"key": {"$regex": "^strategy_pick_result_v2:"}},
            {"_id": 0, "key": 0, "picks": 0, "debate_results": 0, "trade_signals": 0, "ai_summary": 0, "debate_summary": 0, "strategy_stats": 0}
        ).sort("created_at", -1).limit(20))
        for doc in docs:
            for k in ("created_at",):
                if k in doc and hasattr(doc[k], "isoformat"):
                    doc[k] = doc[k].isoformat()
        return jsonify({"success": True, "data": docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@strategy_pick_bp.route("/cancel", methods=["POST"])
def cancel_strategy_pick():
    """取消正在运行的策略选股任务。"""
    _update_progress(0, "已取消", is_running=False)
    return jsonify({"success": True, "message": "策略选股已取消"})


@strategy_pick_bp.route("/strategies", methods=["GET"])
def list_selection_strategies():
    items = storage.list_by_type("selection", enabled_only=True)
    if not items:
        from modules.ai.strategies.presets import get_selection_presets, get_trading_presets
        existing = storage.count_documents({})
        if existing == 0:
            for doc in get_selection_presets():
                doc["created_at"] = datetime.now(); doc["updated_at"] = datetime.now()
                storage.upsert_strategy(doc)
            for doc in get_trading_presets():
                doc["created_at"] = datetime.now(); doc["updated_at"] = datetime.now()
                storage.upsert_strategy(doc)
        items = storage.list_by_type("selection", enabled_only=True)
    return jsonify({"success": True, "data": [_serialize(d) for d in items]})


@strategy_pick_bp.route("/agents", methods=["GET"])
def list_agents():
    """获取可用的分析 Agent 列表（含 MongoDB Agent 和投资哲学 Agent）。"""
    from modules.ai.philosophies.registry import PhilosophyRegistry
    PhilosophyRegistry.init_default()

    result = []
    # MongoDB AI agents
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        for a in db["ai_agents"].find({"enabled": True}, {"_id": 0, "id": 1, "name": 1, "description": 1, "role": 1, "priority": 1}).sort("priority", 1):
            a["type"] = "llm"
            result.append(a)
    except Exception: pass

    # Philosophy agents
    for a in PhilosophyRegistry.get_all():
        entry = a.to_registry_entry()
        entry["type"] = "philosophy"
        entry["id"] = entry.pop("agent_id")
        result.append(entry)

    return jsonify({"success": True, "data": result})
