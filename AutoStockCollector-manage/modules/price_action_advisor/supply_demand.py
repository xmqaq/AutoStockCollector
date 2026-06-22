"""供需区 & 订单块识别 — 纯价格行为逻辑。"""
from typing import Any, Dict, List

from .config import PAConfig


def _calc_atr(bars: List[Dict], period: int = None) -> float:
    """计算 ATR。"""
    period = period or PAConfig.ATR_PERIOD
    if len(bars) < period + 1:
        trs = [b["high"] - b["low"] for b in bars]
        return sum(trs) / max(len(trs), 1)
    trs = []
    for i in range(len(bars) - period, len(bars)):
        prev_close = bars[i - 1]["close"] if i > 0 else bars[i]["close"]
        tr = max(
            bars[i]["high"] - bars[i]["low"],
            abs(bars[i]["high"] - prev_close),
            abs(bars[i]["low"] - prev_close),
        )
        trs.append(tr)
    return sum(trs) / period


def _find_consolidation_zones(bars: List[Dict], lookback: int = None) -> List[Dict]:
    """寻找盘整区（价格堆积区）。"""
    lookback = lookback or PAConfig.CONSOLIDATION_LOOKBACK
    if len(bars) < lookback:
        lookback = len(bars)
    recent = bars[-lookback:]

    zones = []
    i = 0
    win = PAConfig.CONSOLIDATION_WINDOW
    while i < len(recent) - 3:
        chunk = recent[i:i + win]
        highs = [b["high"] for b in chunk]
        lows = [b["low"] for b in chunk]
        range_val = max(highs) - min(lows)
        mid = (max(highs) + min(lows)) / 2
        avg_body = sum(abs(b["close"] - b["open"]) for b in chunk) / len(chunk)

        if range_val > 0 and avg_body / range_val < PAConfig.CONSOLIDATION_BODY_RATIO:
            zone_high = max(highs)
            zone_low = min(lows)
            overlapping = False
            for z in zones:
                if abs(z["high"] - zone_high) / zone_high < PAConfig.ZONE_MERGE_THRESHOLD or abs(z["low"] - zone_low) / zone_low < PAConfig.ZONE_MERGE_THRESHOLD:
                    z["high"] = max(z["high"], zone_high)
                    z["low"] = min(z["low"], zone_low)
                    z["count"] += 1
                    overlapping = True
                    break
            if not overlapping:
                zones.append({
                    "high": zone_high,
                    "low": zone_low,
                    "mid": mid,
                    "count": 1,
                    "strength": 1,
                })
        i += 1

    for z in zones:
        z["strength"] = min(z["count"] * PAConfig.ZONE_STRENGTH_MULTIPLIER, 10)
        z["tested"] = _is_zone_tested(z, bars)
    return zones


def _is_zone_tested(zone: Dict, bars: List[Dict]) -> bool:
    """检查供需区是否被测试过（价格进入过该区域）。"""
    test_count = 0
    for b in bars[-PAConfig.ZONE_TEST_BARS:]:
        if zone["low"] <= b["low"] <= zone["high"] or zone["low"] <= b["high"] <= zone["high"]:
            test_count += 1
    return test_count >= PAConfig.ZONE_TEST_MIN_COUNT


def _find_order_blocks(bars: List[Dict], lookback: int = None) -> List[Dict]:
    """识别订单块 — 导致价格剧烈反转的最后一根实体 K 线。"""
    lookback = lookback or PAConfig.ORDER_BLOCK_LOOKBACK
    if len(bars) < 10:
        return []
    recent = bars[-lookback:]
    blocks = []
    atr = _calc_atr(bars)

    for i in range(2, len(recent)):
        prev = recent[i - 1]
        curr = recent[i]
        body = abs(curr["close"] - curr["open"])
        avg_body = sum(abs(b["close"] - b["open"]) for b in recent[max(0, i - 5):i + 1]) / min(5, i)

        if body < avg_body * PAConfig.ORDER_BLOCK_MIN_BODY_ATR:
            continue

        if curr["close"] > curr["open"] and prev["close"] < prev["open"]:
            if curr["close"] - curr["open"] > atr * PAConfig.ORDER_BLOCK_MIN_BODY_ATR:
                blocks.append({
                    "type": "bullish",
                    "price_min": round(min(curr["open"], curr["close"]), 2),
                    "price_max": round(max(curr["open"], curr["close"]), 2),
                    "strength": min(int(body / atr * 10), 10),
                })
        elif curr["close"] < curr["open"] and prev["close"] > prev["open"]:
            if curr["open"] - curr["close"] > atr * PAConfig.ORDER_BLOCK_MIN_BODY_ATR:
                blocks.append({
                    "type": "bearish",
                    "price_min": round(min(curr["open"], curr["close"]), 2),
                    "price_max": round(max(curr["open"], curr["close"]), 2),
                    "strength": min(int(body / atr * 10), 10),
                })

    return blocks[-PAConfig.ORDER_BLOCK_MAX_RESULTS:] if blocks else []


def _find_liquidity_sweeps(bars: List[Dict], lookback: int = None) -> List[Dict]:
    """检测流动性抓取（假突破）。"""
    lookback = lookback or PAConfig.SWEEP_LOOKBACK
    if len(bars) < 5:
        return []
    recent = bars[-lookback:]
    sweeps = []
    thr = PAConfig.SWEEP_THRESHOLD

    for i in range(3, len(recent) - 1):
        curr = recent[i]
        prev = recent[i - 1]
        next_bar = recent[i + 1]

        prev_highs = [b["high"] for b in recent[max(0, i - 5):i]]
        if prev_highs:
            recent_high = max(prev_highs)
            if recent_high > 0:
                if curr["high"] > recent_high and curr["high"] < recent_high * (1 + thr):
                    if next_bar["close"] < curr["close"] and next_bar["low"] < recent_high:
                        sweeps.append({
                            "type": "bullish_sweep",
                            "level": round(recent_high, 2),
                            "wick_high": round(curr["high"], 2),
                        })

        prev_lows = [b["low"] for b in recent[max(0, i - 5):i]]
        if prev_lows:
            recent_low = min(prev_lows)
            if recent_low > 0:
                if curr["low"] < recent_low and curr["low"] > recent_low * (1 - thr):
                    if next_bar["close"] > curr["close"] and next_bar["high"] > recent_low:
                        sweeps.append({
                            "type": "bearish_sweep",
                            "level": round(recent_low, 2),
                            "wick_low": round(curr["low"], 2),
                        })

    return sweeps


def analyze_supply_demand(bars: List[Dict]) -> Dict[str, Any]:
    """完整的供需分析。"""
    if not bars or len(bars) < 10:
        return {"error": "数据不足", "demand_zones": [], "supply_zones": [], "order_blocks": [], "sweeps": []}

    zones = _find_consolidation_zones(bars)
    current_price = bars[-1]["close"]

    demand_zones = []
    supply_zones = []
    for z in zones:
        if z["mid"] <= current_price:
            demand_zones.append(z)
        else:
            supply_zones.append(z)

    demand_zones.sort(key=lambda x: x["mid"], reverse=True)
    supply_zones.sort(key=lambda x: x["mid"])

    order_blocks = _find_order_blocks(bars)
    sweeps = _find_liquidity_sweeps(bars)
    atr = _calc_atr(bars)

    return {
        "demand_zones": demand_zones[:3],
        "supply_zones": supply_zones[:3],
        "order_blocks": order_blocks,
        "sweeps": sweeps,
        "atr": round(atr, 2),
        "current_price": round(current_price, 2),
    }
