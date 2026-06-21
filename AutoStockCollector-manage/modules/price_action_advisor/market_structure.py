"""市场结构识别 — HH/HL（上升趋势）、LH/LL（下降趋势）、震荡。

纯价格行为逻辑，不依赖任何技术指标。
"""
from typing import Any, Dict, List, Optional


def _find_pivots(bars: List[Dict], left: int = 2, right: int = 2) -> Dict[str, List[int]]:
    """寻找波段高点和低点（Pivot High / Pivot Low）。

    left/right: 左右各需要多少根 K 线确认。
    返回: {"highs": [idx...], "lows": [idx...]}
    """
    highs = []
    lows = []
    n = len(bars)
    for i in range(left, n - right):
        is_high = True
        is_low = True
        for j in range(i - left, i + right + 1):
            if j == i:
                continue
            if bars[j]["high"] >= bars[i]["high"]:
                is_high = False
            if bars[j]["low"] <= bars[i]["low"]:
                is_low = False
        if is_high:
            highs.append(i)
        if is_low:
            lows.append(i)
    return {"highs": highs, "lows": lows}


def detect_trend(bars: List[Dict]) -> str:
    """判断趋势方向。"""
    if len(bars) < 10:
        return "Ranging"

    pivots = _find_pivots(bars, left=2, right=2)
    highs = pivots["highs"]
    lows = pivots["lows"]

    if len(highs) < 2 or len(lows) < 2:
        ema_short = sum(b["close"] for b in bars[-5:]) / 5
        ema_long = sum(b["close"] for b in bars[-20:]) / 20 if len(bars) >= 20 else ema_short
        if ema_short > ema_long * 1.02:
            return "Bullish"
        elif ema_short < ema_long * 0.98:
            return "Bearish"
        return "Ranging"

    last_two_highs = [bars[i]["high"] for i in highs[-2:]]
    last_two_lows = [bars[i]["low"] for i in lows[-2:]]

    hh = last_two_highs[-1] > last_two_highs[-2] * 1.005
    hl = last_two_lows[-1] > last_two_lows[-2] * 1.005
    lh = last_two_highs[-1] < last_two_highs[-2] * 0.995
    ll = last_two_lows[-1] < last_two_lows[-2] * 0.995

    if hh and hl:
        return "Bullish"
    elif lh and ll:
        return "Bearish"
    elif hh and ll:
        return "Ranging"
    return "Ranging"


def detect_market_structure(bars: List[Dict]) -> Dict[str, Any]:
    """完整的市场结构分析。

    Args:
        bars: List[{date, open, high, low, close, volume}]
    Returns:
        dict with trend, swing levels, breakout info
    """
    if not bars or len(bars) < 10:
        return {"trend": "Ranging", "error": "数据不足"}

    trend = detect_trend(bars)
    pivots = _find_pivots(bars, left=2, right=2)
    highs_idx = pivots["highs"]
    lows_idx = pivots["lows"]

    high_prices = [bars[i]["high"] for i in highs_idx] if highs_idx else []
    low_prices = [bars[i]["low"] for i in lows_idx] if lows_idx else []

    last_swing_high = max(high_prices[-3:]) if len(high_prices) >= 3 else (high_prices[-1] if high_prices else bars[-1]["high"])
    last_swing_low = min(low_prices[-3:]) if len(low_prices) >= 3 else (low_prices[-1] if low_prices else bars[-1]["low"])

    recent = bars[-5:]
    recent_high = max(b["high"] for b in recent)
    recent_low = min(b["low"] for b in recent)

    breakout_level = None
    if trend == "Bullish":
        breakout_level = last_swing_high
    elif trend == "Bearish":
        breakout_level = last_swing_low

    structure = trend
    if len(highs_idx) >= 3 and len(lows_idx) >= 3:
        recent_highs = [bars[i]["high"] for i in highs_idx[-3:]]
        recent_lows = [bars[i]["low"] for i in lows_idx[-3:]]
        if recent_highs[-1] > recent_highs[-2] > recent_highs[-3] and recent_lows[-1] > recent_lows[-2] > recent_lows[-3]:
            structure = "Strong Bullish"
        elif recent_highs[-1] < recent_highs[-2] < recent_highs[-3] and recent_lows[-1] < recent_lows[-2] < recent_lows[-3]:
            structure = "Strong Bearish"

    return {
        "trend": trend,
        "structure": structure,
        "last_swing_high": round(last_swing_high, 2),
        "last_swing_low": round(last_swing_low, 2),
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
        "breakout_level": round(breakout_level, 2) if breakout_level else None,
        "pivot_highs": [round(p, 2) for p in high_prices[-5:]],
        "pivot_lows": [round(p, 2) for p in low_prices[-5:]],
    }
