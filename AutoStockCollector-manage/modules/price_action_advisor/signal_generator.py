"""信号生成器 — 融合市场结构 + 供需区 + 形态确认，生成交易信号。"""
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


def _detect_candlestick_patterns(bars: List[Dict]) -> List[Dict]:
    """识别经典 K 线形态（纯价格行为，无指标）。"""
    if len(bars) < 3:
        return []
    patterns = []

    prev = bars[-3]
    curr = bars[-2]
    last = bars[-1]

    prev_body = abs(prev["close"] - prev["open"])
    curr_body = abs(curr["close"] - curr["open"])
    last_body = abs(last["close"] - last["open"])
    prev_range = prev["high"] - prev["low"]
    curr_range = curr["high"] - curr["low"]

    # Pin Bar / Hammer
    if curr_body < curr_range * 0.35:
        lower_wick = min(curr["open"], curr["close"]) - curr["low"]
        upper_wick = curr["high"] - max(curr["open"], curr["close"])
        if lower_wick > curr_body * 2 and lower_wick > upper_wick * 2:
            patterns.append({"name": "pin_bar", "type": "bullish" if curr["close"] > curr["open"] else "bearish"})
        elif upper_wick > curr_body * 2 and upper_wick > lower_wick * 2:
            patterns.append({"name": "shooting_star" if curr["close"] < curr["open"] else "inverted_hammer", "type": "bearish" if curr["close"] < curr["open"] else "bullish"})

    # Bullish Engulfing
    if curr["close"] > curr["open"] and prev["close"] < prev["open"]:
        if curr["open"] < prev["close"] and curr["close"] > prev["open"]:
            patterns.append({"name": "bullish_engulfing", "type": "bullish"})

    # Bearish Engulfing
    if curr["close"] < curr["open"] and prev["close"] > prev["open"]:
        if curr["open"] > prev["close"] and curr["close"] < prev["open"]:
            patterns.append({"name": "bearish_engulfing", "type": "bearish"})

    # Inside Bar
    if curr["high"] <= prev["high"] and curr["low"] >= prev["low"]:
        patterns.append({"name": "inside_bar", "type": "neutral"})

    last_range = last["high"] - last["low"]

    # Doji
    if last_body < last_range * 0.1 and last_range > 0:
        patterns.append({"name": "doji", "type": "neutral"})

    # Three White Soldiers / Three Black Crows
    if len(bars) >= 4:
        b3, b2, b1 = bars[-4], bars[-3], bars[-2]
        if b1["close"] > b1["open"] and b2["close"] > b2["open"] and b3["close"] > b3["open"]:
            if b1["close"] > b2["close"] > b3["close"]:
                patterns.append({"name": "three_white_soldiers", "type": "bullish"})
        if b1["close"] < b1["open"] and b2["close"] < b2["open"] and b3["close"] < b3["open"]:
            if b1["close"] < b2["close"] < b3["close"]:
                patterns.append({"name": "three_black_crows", "type": "bearish"})

    return patterns


def _calculate_fib_levels(bars: List[Dict], trend: str, recent_high: float, recent_low: float) -> Dict[str, float]:
    """计算斐波那契回撤位。"""
    if trend == "Bullish":
        move = recent_high - recent_low
        return {
            "0.382": round(recent_high - move * 0.382, 2),
            "0.500": round(recent_high - move * 0.500, 2),
            "0.618": round(recent_high - move * 0.618, 2),
            "0.786": round(recent_high - move * 0.786, 2),
        }
    elif trend == "Bearish":
        move = recent_high - recent_low
        return {
            "0.382": round(recent_low + move * 0.382, 2),
            "0.500": round(recent_low + move * 0.500, 2),
            "0.618": round(recent_low + move * 0.618, 2),
            "0.786": round(recent_low + move * 0.786, 2),
        }
    return {}


def generate_signal(
    code: str,
    name: str,
    bars: List[Dict],
    market_struct: Dict[str, Any],
    sd_result: Dict[str, Any],
) -> Dict[str, Any]:
    """综合判断，生成买卖信号。

    Args:
        code: 股票代码
        name: 股票名称
        bars: OHLCV bars
        market_struct: detect_market_structure() 的结果
        sd_result: analyze_supply_demand() 的结果
    Returns:
        signal dict
    """
    if not bars or len(bars) < 20:
        return {"symbol": code, "signal": "NO_DATA", "message": "数据不足"}

    current_price = bars[-1]["close"]
    trend = market_struct.get("trend", "Ranging")
    patterns = _detect_candlestick_patterns(bars)
    fibs = _calculate_fib_levels(
        bars, trend,
        market_struct.get("recent_high", current_price),
        market_struct.get("recent_low", current_price),
    )

    demand_zones = sd_result.get("demand_zones", [])
    supply_zones = sd_result.get("supply_zones", [])
    order_blocks = sd_result.get("order_blocks", [])
    sweeps = sd_result.get("sweeps", [])
    atr = sd_result.get("atr", 0)

    buy_reasons = []
    sell_reasons = []
    confidence = 1

    # === 买入逻辑 ===
    if trend in ("Bullish", "Strong Bullish"):
        buy_reasons.append(f"上升趋势: {trend}")
        confidence += 1

        # 回踩需求区
        for dz in demand_zones:
            if dz["low"] <= current_price <= dz["high"] * 1.02:
                buy_reasons.append(f"回踩需求区 ({dz['low']}-{dz['high']})")
                confidence += 1
                break
        # 回踩斐波那契 0.618
        if "0.618" in fibs and abs(current_price - fibs["0.618"]) / current_price < 0.02:
            buy_reasons.append(f"回撤至 Fib 0.618 ({fibs['0.618']})")
            confidence += 1

        # 看涨形态确认
        for p in patterns:
            if p["type"] == "bullish":
                buy_reasons.append(f"看涨形态: {p['name']}")
                confidence += 1
                break

        # 看涨订单块
        for ob in order_blocks:
            if ob["type"] == "bullish" and ob["price_min"] <= current_price <= ob["price_max"] * 1.01:
                buy_reasons.append(f"看涨订单块 ({ob['price_min']}-{ob['price_max']})")
                confidence += 1
                break

        # 流动性抓取后反弹
        for sw in sweeps:
            if sw["type"] == "bullish_sweep" and current_price > sw["level"]:
                buy_reasons.append(f"流动性抓取后反弹 (突破{sw['level']})")
                confidence += 1
                break

    # === 卖出逻辑 ===
    if trend in ("Bearish", "Strong Bearish"):
        sell_reasons.append(f"下降趋势: {trend}")
        confidence += 1

        for sz in supply_zones:
            if sz["low"] * 0.98 <= current_price <= sz["high"]:
                sell_reasons.append(f"反弹至供应区 ({sz['low']}-{sz['high']})")
                confidence += 1
                break

        if "0.618" in fibs and abs(current_price - fibs["0.618"]) / current_price < 0.02:
            sell_reasons.append(f"反弹至 Fib 0.618 ({fibs['0.618']})")
            confidence += 1

        for p in patterns:
            if p["type"] == "bearish":
                sell_reasons.append(f"看跌形态: {p['name']}")
                confidence += 1
                break

        for ob in order_blocks:
            if ob["type"] == "bearish" and ob["price_min"] * 0.99 <= current_price <= ob["price_max"]:
                sell_reasons.append(f"看跌订单块 ({ob['price_min']}-{ob['price_max']})")
                confidence += 1
                break

        for sw in sweeps:
            if sw["type"] == "bearish_sweep" and current_price < sw["level"]:
                sell_reasons.append(f"流动性抓取后下跌 (跌破{sw['level']})")
                confidence += 1
                break

    # === 综合判定 ===
    buy_score = len(buy_reasons)
    sell_score = len(sell_reasons)
    signal = "NEUTRAL"
    reasons = []
    zones = []

    if buy_score > sell_score and buy_score >= 2:
        signal = "BUY_SETUP"
        reasons = buy_reasons
        zones = demand_zones[:1] if demand_zones else []
        confidence = min(buy_score + 1, 5)
    elif sell_score > buy_score and sell_score >= 2:
        signal = "SELL_SETUP"
        reasons = sell_reasons
        zones = supply_zones[:1] if supply_zones else []
        confidence = min(sell_score + 1, 5)
    elif buy_score == sell_score and buy_score >= 2 and sell_score >= 2:
        signal = "NEUTRAL"
        reasons = ["多空信号均衡，等待确认"]
        confidence = 2
    else:
        if buy_score >= 1:
            signal = "WEAK_BUY"
            reasons = buy_reasons
            confidence = 2
        elif sell_score >= 1:
            signal = "WEAK_SELL"
            reasons = sell_reasons
            confidence = 2
        else:
            signal = "NO_TRADE"
            reasons = ["无明显交易信号"]
            confidence = 0

    return {
        "symbol": code,
        "name": name,
        "current_price": round(current_price, 2),
        "signal": signal,
        "confidence": confidence,
        "trend": trend,
        "reasons": reasons,
        "zones": zones,
        "patterns": [p["name"] for p in patterns],
        "fib_levels": fibs,
        "atr": round(atr, 2) if atr else 0,
        "sweeps_detected": len(sweeps),
    }
