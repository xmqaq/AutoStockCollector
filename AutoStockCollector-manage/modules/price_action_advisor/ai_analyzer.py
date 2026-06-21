"""价格行为 AI 分析 — LLM 解读交易信号。"""
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

_AI_ANALYSIS_PROMPT = """你是一位专业的价格行为学交易员，请基于以下技术分析数据给出交易决策解读。

股票: {name} ({symbol})
当前价格: ¥{current_price}
时间周期: {timeframe}

市场趋势: {trend}
ATR (14): {atr}
信号: {signal}
置信度: {confidence}/5

信号依据:
{reasons}

关键价格区间:
{zones_info}

斐波那契回撤位:
{fib_info}

交易计划:
{direction} | 入场 ¥{entry_price} | 止损 ¥{stop_loss} | 止盈 ¥{take_profit}
盈亏比: {rr_ratio}
仓位: {position_size} 股 ({position_value}元)
单笔风险: ¥{total_risk}

请给出以下分析（控制在300字以内）：
1. 多空逻辑判断 — 当前信号是否可靠？主要矛盾是什么？
2. 关键观察点 — 未来需要关注哪些价格水平或K线形态变化？
3. 风险提示 — 什么情况下信号可能失效？
4. 综合建议 — 是否建议执行交易计划？仓位是否需要调整？
"""


def get_ai_commentary(signal: Dict[str, Any]) -> Optional[str]:
    """调用 LLM 对价格行为信号进行解读。"""
    try:
        from modules.ai.foundation.llm_router import LLMRouter
    except ImportError:
        logger.warning("[PAAI] LLMRouter not available")
        return None

    tp = signal.get("trade_plan") or {}
    zones = signal.get("zones", [])
    fibs = signal.get("fib_levels", {})
    reasons = signal.get("reasons", [])

    zones_info = "\n".join(
        [f"  {z.get('low', z.get('price_min', '?'))} - {z.get('high', z.get('price_max', '?'))} (强度 {z.get('strength', '?')})"
         for z in zones]
    ) or "无"

    fib_info = "\n".join([f"  {k}: ¥{v}" for k, v in (fibs or {}).items()]) or "无"

    prompt = _AI_ANALYSIS_PROMPT.format(
        name=signal.get("name", ""),
        symbol=signal.get("symbol", ""),
        current_price=signal.get("current_price", 0),
        timeframe=signal.get("timeframe", "daily"),
        trend=signal.get("trend", "未知"),
        atr=signal.get("atr", 0),
        signal=signal.get("signal", "未知"),
        confidence=signal.get("confidence", 0),
        reasons="\n".join(f"  • {r}" for r in reasons) or "无",
        zones_info=zones_info,
        fib_info=fib_info,
        direction=tp.get("direction", "-"),
        entry_price=tp.get("entry", "-"),
        stop_loss=tp.get("stop_loss", "-"),
        take_profit=tp.get("take_profit", "-"),
        rr_ratio=tp.get("r_r_ratio", "-"),
        position_size=tp.get("position_size", 0),
        position_value=tp.get("position_value", 0),
        total_risk=tp.get("total_risk", 0),
    )

    try:
        router = LLMRouter()
        result = router(prompt, temperature=0.5, max_tokens=500)
        if result:
            return result.strip()
    except Exception as e:
        logger.warning(f"[PAAI] LLM call failed: {e}")

    return None
