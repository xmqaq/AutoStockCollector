"""多时间框架融合 — 纯价格行为的三周期共振判断。

PA 学核心：daily(触发) + weekly(中期结构) + monthly(宏观方向) 共振。
权重分层：monthly > weekly > daily。逆月线不做 SETUP（月线最重，逆大势是接飞刀）。
纯函数无 IO，可直接单测。
"""
from typing import Any, Dict, Optional


def project_direction(trend: str) -> int:
    """趋势 → 方向：+1 多 / -1 空 / 0 震荡。Strong 不额外加权（成熟度另算）。"""
    if trend in ("Bullish", "Strong Bullish"):
        return 1
    if trend in ("Bearish", "Strong Bearish"):
        return -1
    return 0


# 方向 → 中文文案
_DIR_LABEL = {1: "多", -1: "空", 0: "震荡"}


def _resonance_label(m: int, w: int, d: int) -> str:
    if m == w == d and m != 0:
        return f"三周期共振（{_DIR_LABEL[m]}）"
    if m != 0 and w == m and d != m:
        return f"大周期同向但触发逆（{_DIR_LABEL[m]}）"
    if m != 0 and w != m and w != 0:
        return f"月线与周线分歧"
    if m != 0 and d == m and w != m:
        return f"月线背书但周线逆"
    if m == 0 and w != 0 and d == w:
        return f"周线与触发共振（中宏观无趋势）"
    if m == 0 and w == 0 and d != 0:
        return f"仅触发有方向（中宏观无趋势）"
    return "三周期分歧"


def fuse_timefaces(tf_structs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """三周期结构融合，产出信号提示/置信度调整/共振标签/警告/multi_tf 视图。

    Args:
        tf_structs: {timeframe: detect_market_structure 返回的 dict}，至少含 "daily"，
            可选 "weekly"/"monthly"。缺失的周期视为 0（无趋势）。

    Returns:
        {
            signal_hint: "BUY_SETUP"|"SELL_SETUP"|"WEAK_BUY"|"WEAK_SELL"|"NEUTRAL"|"NO_TRADE",
            confidence_delta: int,  # 叠加到基础 confidence 上（封顶由调用方处理）
            resonance: str,         # 共振文案
            warnings: List[str],    # 成熟度/冲突警告（不二次降级，仅文案）
            multi_tf: {             # 三周期视图，供前端展示
                daily: {trend, structure},
                weekly: {trend, structure} | None,
                monthly: {trend, structure} | None,
                resonance: str,
            },
        }
    """
    daily = tf_structs.get("daily", {}) or {}
    weekly = tf_structs.get("weekly", {}) or {}
    monthly = tf_structs.get("monthly", {}) or {}

    d = project_direction(daily.get("trend", "Ranging"))
    w = project_direction(weekly.get("trend", "Ranging"))
    m = project_direction(monthly.get("trend", "Ranging"))

    resonance = _resonance_label(m, w, d)
    warnings = []

    # 成熟度警告（Strong 趋势 = 已 3 次 HH/LL，可能接近末端）— 仅文案，不碰 confidence
    for tf_name, struct in (("monthly", monthly), ("weekly", weekly), ("daily", daily)):
        s = struct.get("structure", "")
        if s in ("Strong Bullish", "Strong Bearish"):
            direction = "上升" if "Bullish" in s else "下降"
            warnings.append(f"{tf_name}趋势已到 Strong（{direction}可能接近末端）")

    # 信号提示：基于三周期方向组合
    # 规则：逆月线(月线=-1)绝不出 BUY_SETUP；逆月线(月线=+1)绝不出 SELL_SETUP
    signal_hint = "NO_TRADE"
    confidence_delta = 0

    if d > 0:  # 日线多
        if m > 0 and w > 0:  # 三周期共振多
            signal_hint = "BUY_SETUP"
            confidence_delta = 1
        elif m > 0 and w < 0:  # 月线多但周线回调
            signal_hint = "WEAK_BUY"
        elif m < 0 and w > 0:  # 月线逆势，周线反弹
            signal_hint = "WEAK_BUY"
            confidence_delta = -1
        elif m == 0 and w >= 0:  # 中宏观无趋势/震荡
            signal_hint = "WEAK_BUY"
        # m>0 w<0 d>0 已处理；m<0 w<=0 d>0 逆月线不做多 → NO_TRADE
    elif d < 0:  # 日线空（镜像）
        if m < 0 and w < 0:  # 三周期共振空
            signal_hint = "SELL_SETUP"
            confidence_delta = 1
        elif m < 0 and w > 0:  # 月线空但周线反弹
            signal_hint = "WEAK_SELL"
        elif m > 0 and w < 0:  # 月线逆势，周线回调
            signal_hint = "WEAK_SELL"
            confidence_delta = -1
        elif m == 0 and w <= 0:  # 中宏观无趋势/震荡
            signal_hint = "WEAK_SELL"
    else:  # 日线震荡
        if (m > 0 and w > 0) or (m < 0 and w < 0):
            signal_hint = "NEUTRAL"  # 大周期有方向但触发无方向
        else:
            signal_hint = "NO_TRADE"

    multi_tf = {
        "daily": {
            "trend": daily.get("trend", "Ranging"),
            "structure": daily.get("structure", "Ranging"),
        },
        "weekly": {
            "trend": weekly.get("trend", "Ranging"),
            "structure": weekly.get("structure", "Ranging"),
        } if weekly else None,
        "monthly": {
            "trend": monthly.get("trend", "Ranging"),
            "structure": monthly.get("structure", "Ranging"),
        } if monthly else None,
        "resonance": resonance,
    }

    return {
        "signal_hint": signal_hint,
        "confidence_delta": confidence_delta,
        "resonance": resonance,
        "warnings": warnings,
        "multi_tf": multi_tf,
    }
