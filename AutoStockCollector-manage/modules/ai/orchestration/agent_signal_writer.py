"""AgentSignalWriter — 把 TradingGraph 的 verdict 标准化为 fusion 可消费的信号文档。

为什么独立成模块：graph.py 应保持纯「跑流水线返回结果」，写 DB 是副作用，
由独立 writer 负责，便于单独测试与将来替换产出方式（如换更轻的 agent 编排）。

写入 collection: agent_signals（带 TTL 索引 7 天，由 cron.py 建）。
upsert by (code, trade_date)：同一只票当日多次刷新覆盖最新，不留历史堆叠；
跨日通过 trade_date 区分，过期文档由 TTL 自动清理。
"""
from typing import Any, Dict, Optional

from config.database import DatabaseConfig
from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)

AGENT_SIGNALS_COLLECTION = "agent_signals"


def _coerce_float(val, default: float = 0.0) -> float:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    return f if 0 <= f <= 100 else default


def _map_signal(recommendation: str) -> str:
    """TradingGraph verdict.recommendation → fusion 信号词。"""
    r = (recommendation or "").strip()
    if r == "买入":
        return "buy"
    if r == "回避":
        return "sell"
    return "hold"


def build_signal_doc(verdict: Dict[str, Any], final_decision: Dict[str, Any],
                     trade_date: str) -> Optional[Dict[str, Any]]:
    """把 verdict + final_decision 标准化为 agent_signals 文档。无效输入返回 None。

    agent_score 用连续量 net = (bullScore + (100-bearScore))/2，不丢精度；
    缺 bull/bear 时回退到 50（中性，不参与融合分母，因 _merge_agent 要求 >0）。
    """
    if not verdict or not trade_date:
        return None
    code = verdict.get("code") or ""
    if not code:
        return None
    bull = _coerce_float(verdict.get("bullScore"), 50)
    bear = _coerce_float(verdict.get("bearScore"), 50)
    net = (bull + (100 - bear)) / 2
    agent_score = round(max(0.0, min(100.0, net)), 1)

    recommendation = verdict.get("recommendation", "观望")
    fd = final_decision or {}
    return {
        "code": code,
        "name": verdict.get("name", "") or "",
        "industry": verdict.get("industry", "") or "",
        "agent_score": agent_score,
        "agent_signal": _map_signal(recommendation),
        "tendency": verdict.get("tendency", ""),
        "recommendation": recommendation,
        "confidence": _coerce_float(fd.get("confidence"), 0.5) if fd.get("confidence") is not None else 0.5,
        "bull_score": bull,
        "bear_score": bear,
        "trade_date": trade_date,
        "final_decision": (fd.get("decision") or "")[:800],
        "updated_at": beijing_now().isoformat(),
    }


def write_agent_signal(verdict: Dict[str, Any], final_decision: Dict[str, Any],
                       trade_date: str) -> Optional[Dict[str, Any]]:
    """标准化并 upsert 入 agent_signals。返回写入的文档（失败返回 None）。"""
    doc = build_signal_doc(verdict, final_decision, trade_date)
    if not doc:
        logger.warning("[agent-signal] skip write: verdict/code/trade_date missing")
        return None
    try:
        col = DatabaseConfig.get_database()[AGENT_SIGNALS_COLLECTION]
        col.update_one(
            {"code": doc["code"], "trade_date": trade_date},
            {
                "$set": doc,
                "$setOnInsert": {"generated_at": beijing_now().isoformat()},
            },
            upsert=True,
        )
        logger.info(
            f"[agent-signal] wrote {doc['code']} score={doc['agent_score']} "
            f"signal={doc['agent_signal']} date={trade_date}"
        )
        return doc
    except Exception as e:
        logger.error(f"[agent-signal] write failed for {doc.get('code')}: {e}")
        return None
