"""外部信号采集器 — monitor 吸收 PA/竞价/agent 三路外部信号。

读 DB 快照不实时算（PA 实时算成本不可接受）。三路各自独立查询，缺失返回 None。
compute_fusion_score 按 auto_trading fusion 同款权重(竞价0.20/PA0.30/ai_monitor0.30/agent0.20)
归一化（缺失源不参与分母），产出一个对标 auto_trading overall_score 的"综合融合分"。
"""
from typing import Any, Dict, Optional

from config.database import DatabaseConfig
from utils.logger import get_logger
from utils.helpers import beijing_now

logger = get_logger(__name__)

# 与 auto_trading/signal_fusion 四路权重对齐（ai_monitor=composite 走 0.30）
W_AUCTION = 0.20
W_PA = 0.30
W_AI_MONITOR = 0.30
W_AGENT = 0.20

# PA 信号 → 0-100 分（与 signal_fusion.PA_SIGNAL_SCORES 对齐）
PA_SIGNAL_SCORES = {
    "BUY_SETUP": 95, "WEAK_BUY": 70, "NEUTRAL": 50,
    "WEAK_SELL": 30, "SELL_SETUP": 5, "NO_DATA": 50, "NO_TRADE": 50,
}
# PA confidence 值域上限（与 signal_fusion.PA_CONFIDENCE_MAX 对齐，0-5 整数）
PA_CONFIDENCE_MAX = 5


def _strip_prefix(code: str) -> str:
    """裸代码（与 radar_utils.strip_prefix_from_code 同语义，避免循环依赖内联）。"""
    if not code:
        return ""
    c = code.upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
    return c.split(".")[-1]


def fetch_pa_snapshot(code: str) -> Optional[Dict[str, Any]]:
    """查 pa_scan_results 最新一份，按 code 匹配 results[]。

    盘中优先 30m、盘后优先 daily（两份都查取最新）。返回 {signal, confidence, trade_plan,
    scanned_at, stale}。无数据返回 None。
    """
    try:
        db = DatabaseConfig.get_database()
        bare = _strip_prefix(code)
        # 取最新一份扫描（不区分 timeframe，按 created_at desc）
        doc = db["pa_scan_results"].find_one({}, sort=[("created_at", -1)])
        if not doc:
            return None
        for r in (doc.get("results") or []):
            if _strip_prefix(r.get("symbol", "")) == bare:
                return {
                    "signal": r.get("signal", "NO_DATA"),
                    "confidence": r.get("confidence", 0),
                    "trade_plan": r.get("trade_plan"),
                    "scanned_at": (doc.get("created_at").isoformat()
                                   if hasattr(doc.get("created_at"), "isoformat") else str(doc.get("created_at", ""))),
                    "timeframe": doc.get("timeframe", ""),
                }
        return None
    except Exception as e:
        logger.warning(f"[external] pa snapshot fetch failed for {code}: {e}")
        return None


def fetch_agent_signal(code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    """查 agent_signals {code, trade_date}，返回 {score, signal, trade_date}。

    存储的 code 一律裸码（cron collector 全程 strip_prefix_from_code），故精确匹配
    裸码即可，与 _merge_agent 对齐。缺失返回 None（不回退 50，避免静默进分母）。
    """
    try:
        db = DatabaseConfig.get_database()
        bare = _strip_prefix(code)
        doc = db["agent_signals"].find_one(
            {"code": bare, "trade_date": trade_date},
            sort=[("updated_at", -1)],
        )
        if not doc:
            return None
        return {
            "score": doc.get("agent_score", 0) or 0,
            "signal": doc.get("agent_signal", "hold"),
            "trade_date": doc.get("trade_date", ""),
            "tendency": doc.get("tendency", ""),
        }
    except Exception as e:
        logger.warning(f"[external] agent signal fetch failed for {code}: {e}")
        return None


def fetch_auction(code: str, date: str) -> Optional[Dict[str, Any]]:
    """查 auction_results {date}，从 top_stocks[] 按 code 匹配。"""
    try:
        db = DatabaseConfig.get_database()
        bare = _strip_prefix(code)
        doc = db["auction_results"].find_one({"date": date}, sort=[("created_at", -1)])
        if not doc:
            return None
        for s in (doc.get("top_stocks") or []):
            if _strip_prefix(s.get("symbol", "")) == bare:
                trap = s.get("trap_warning", {}) or {}
                return {
                    "score": s.get("strength_score", 0),
                    "gap_pct": s.get("gap_pct", 0.0),
                    "trap": trap.get("is_trap", False),
                    "name": s.get("name", ""),
                    "industry": s.get("industry", ""),
                    "date": date,
                }
        return None
    except Exception as e:
        logger.warning(f"[external] auction fetch failed for {code}: {e}")
        return None


def compute_fusion_score(
    composite_score: float,
    pa: Optional[Dict[str, Any]],
    auction: Optional[Dict[str, Any]],
    agent: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """四路归一化加权（与 auto_trading signal_fusion._compute_overall 同款逻辑）。

    缺失源不参与分母。返回 {fusion_score, breakdown, weights}。
    """
    # 各路 0-100 分
    pa_signal = pa.get("signal", "NO_DATA") if pa else "NO_DATA"
    pa_score = PA_SIGNAL_SCORES.get(pa_signal, 50) if pa else None
    auction_score = auction.get("score", 0) if auction else None
    agent_score = agent.get("score", 50) if agent else None
    monitor_score = composite_score if composite_score and composite_score > 0 else None

    terms = []
    if auction_score and auction_score > 0:
        terms.append(("auction", W_AUCTION, W_AUCTION * auction_score / 100.0))
    # PA 与 _compute_overall 对齐：confidence 缩放（0-5 归一，缺失回退 0.5）+ NO_DATA 不计分
    if pa_score is not None and pa_signal != "NO_DATA":
        pa_conf = pa.get("confidence", 0) or 0
        pa_conf = pa_conf / PA_CONFIDENCE_MAX if pa_conf > 0 else 0.5
        terms.append(("pa", W_PA, W_PA * pa_score / 100.0 * pa_conf))
    if monitor_score:
        terms.append(("ai_monitor", W_AI_MONITOR, W_AI_MONITOR * monitor_score / 100.0))
    if agent_score and agent_score > 0:
        terms.append(("agent", W_AGENT, W_AGENT * agent_score / 100.0))

    active_weights = sum(w for _, w, _ in terms)
    if active_weights <= 0:
        return {"fusion_score": 50.0, "breakdown": {}, "weights": {}}

    numerator = sum(v for _, _, v in terms)
    fusion_score = round(max(0.0, min(100.0, numerator / active_weights * 100)), 1)

    breakdown = {k: round(v / w * 100, 1) if w > 0 else 0 for k, w, v in terms}
    weights = {k: w for k, w, _ in terms}
    return {"fusion_score": fusion_score, "breakdown": breakdown, "weights": weights}


def collect_external_signals(code: str, composite_score: float, date: str) -> Dict[str, Any]:
    """采集三路外部信号 + 算 fusion_score。整体失败返回空 dict，不影响 monitor 主流程。"""
    try:
        pa = fetch_pa_snapshot(code)
        agent = fetch_agent_signal(code, date)
        auction = fetch_auction(code, date)
        fusion = compute_fusion_score(composite_score, pa, auction, agent)
        return {
            "pa": pa,
            "auction": auction,
            "agent": agent,
            "fusion_score": fusion["fusion_score"],
            "fusion_breakdown": fusion["breakdown"],
            "fusion_weights": fusion["weights"],
        }
    except Exception as e:
        logger.warning(f"[external] collect failed for {code}: {e}")
        return {}
