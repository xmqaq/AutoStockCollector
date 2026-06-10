"""
市场信号检测相关接口
包含：买入/卖出信号检测、信号历史
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, List, Any
import random

market_bp = Blueprint("market", __name__, url_prefix="/api/v1/market")


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible, beijing_now
    return normalize_stock_code_flexible(code)


def _get_kline_data(code: str, days: int = 30) -> List[Dict]:
    """获取K线历史数据"""
    try:
        from core.storage.mongo_storage import KlineStorage
        storage = KlineStorage()
        records = storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=days
        )
        return records
    except Exception:
        return []


def _detect_ma_cross(klines: List[Dict]) -> Dict[str, Any]:
    """检测均线金叉/死叉信号"""
    if len(klines) < 20:
        return {"signal": None, "strength": None, "reasons": []}

    closes = [float(k.get("close", 0)) for k in reversed(klines)]

    ma5_current = sum(closes[-5:]) / 5
    ma5_prev = sum(closes[-6:-1]) / 5
    ma20_current = sum(closes[-20:]) / 20
    ma20_prev = sum(closes[-21:-1]) / 20

    if ma5_current > ma20_current and ma5_prev <= ma20_prev:
        return {
            "signal": "buy",
            "strength": "中等",
            "reasons": ["MA5上穿MA20形成金叉", "短期趋势转多"]
        }
    elif ma5_current < ma20_current and ma5_prev >= ma20_prev:
        return {
            "signal": "sell",
            "strength": "中等",
            "reasons": ["MA5下穿MA20形成死叉", "短期趋势转空"]
        }

    return {"signal": None, "strength": None, "reasons": []}


def _detect_volume_surge(klines: List[Dict]) -> Dict[str, Any]:
    """检测成交量放量信号"""
    if len(klines) < 10:
        return {"signal": None, "strength": None, "reasons": []}

    volumes = [float(k.get("volume", 0)) for k in reversed(klines)]

    avg_volume = sum(volumes[1:10]) / 9 if len(volumes) > 9 else sum(volumes) / max(1, len(volumes))
    current_volume = volumes[-1] if volumes else 0

    if current_volume > avg_volume * 2:
        return {
            "signal": "buy",
            "strength": "强",
            "reasons": [f"成交量放大{(current_volume / avg_volume):.1f}倍", "资金明显介入"]
        }
    elif current_volume > avg_volume * 1.5:
        return {
            "signal": "neutral",
            "strength": "弱",
            "reasons": ["成交量有所放大", "需观察持续性"]
        }

    return {"signal": None, "strength": None, "reasons": []}


def _detect_price_breakout(klines: List[Dict]) -> Dict[str, Any]:
    """检测价格突破信号"""
    if len(klines) < 20:
        return {"signal": None, "strength": None, "reasons": []}

    highs = [float(k.get("high", 0)) for k in reversed(klines)]
    lows = [float(k.get("low", 0)) for k in reversed(klines)]
    closes = [float(k.get("close", 0)) for k in reversed(klines)]

    recent_high = max(highs[1:20]) if len(highs) > 20 else max(highs[1:])
    recent_low = min(lows[1:20]) if len(lows) > 20 else min(lows[1:])
    current_price = closes[-1]

    if current_price > recent_high:
        return {
            "signal": "buy",
            "strength": "强",
            "reasons": ["价格突破20日高点", "或开启新一轮上涨"]
        }
    elif current_price < recent_low:
        return {
            "signal": "sell",
            "strength": "强",
            "reasons": ["价格跌破20日低点", "需警惕下行风险"]
        }

    return {"signal": None, "strength": None, "reasons": []}


def _detect_rsi_signal(klines: List[Dict]) -> Dict[str, Any]:
    """RSI超买超卖信号"""
    if len(klines) < 14:
        return {"signal": None, "strength": None, "reasons": []}

    closes = [float(k.get("close", 0)) for k in reversed(klines)]

    deltas = [closes[i] - closes[i + 1] for i in range(len(closes) - 1)]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:14]) / 14 if len(gains) >= 14 else sum(gains) / max(1, len(gains))
    avg_loss = sum(losses[:14]) / 14 if len(losses) >= 14 else sum(losses) / max(1, len(losses))

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if rsi > 80:
        return {
            "signal": "sell",
            "strength": "中等",
            "reasons": [f"RSI={rsi:.1f}超买区域", "注意回调风险"]
        }
    elif rsi < 20:
        return {
            "signal": "buy",
            "strength": "中等",
            "reasons": [f"RSI={rsi:.1f}超卖区域", "或存在反弹机会"]
        }

    return {"signal": None, "strength": None, "reasons": []}


@market_bp.route("/signals/<code>", methods=["GET"])
def detect_signals(code: str):
    """检测交易信号"""
    code = _normalize_code(code)
    if not code:
        return jsonify({"error": "invalid code"}), 400

    klines = _get_kline_data(code, days=30)

    if not klines or len(klines) < 5:
        return jsonify({
            "success": True,
            "code": code,
            "signal": "neutral",
            "type": "neutral",
            "strength": "弱",
            "price": 0,
            "time": beijing_now().isoformat(),
            "reasons": ["数据不足，无法生成信号"]
        })

    ma_signal = _detect_ma_cross(klines)
    vol_signal = _detect_volume_surge(klines)
    break_signal = _detect_price_breakout(klines)
    rsi_signal = _detect_rsi_signal(klines)

    signals = [ma_signal, vol_signal, break_signal, rsi_signal]
    buy_signals = [s for s in signals if s.get("signal") == "buy"]
    sell_signals = [s for s in signals if s.get("signal") == "sell"]

    current_price = float(klines[0].get("close", 0))

    if len(buy_signals) >= 2:
        final_signal = "buy"
        strength = "强" if len(buy_signals) >= 3 else "中等"
        all_reasons = []
        for s in buy_signals:
            all_reasons.extend(s.get("reasons", []))
    elif len(sell_signals) >= 2:
        final_signal = "sell"
        strength = "强" if len(sell_signals) >= 3 else "中等"
        all_reasons = []
        for s in sell_signals:
            all_reasons.extend(s.get("reasons", []))
    elif len(buy_signals) == 1:
        final_signal = "buy"
        strength = buy_signals[0].get("strength", "弱")
        all_reasons = buy_signals[0].get("reasons", [])
    elif len(sell_signals) == 1:
        final_signal = "sell"
        strength = sell_signals[0].get("strength", "弱")
        all_reasons = sell_signals[0].get("reasons", [])
    else:
        final_signal = "neutral"
        strength = "弱"
        all_reasons = ["无明显信号", "建议观望"]

    return jsonify({
        "success": True,
        "code": code,
        "signal": final_signal,
        "type": final_signal,
        "strength": strength,
        "price": current_price,
        "time": beijing_now().isoformat(),
        "reasons": all_reasons[:5]
    })


@market_bp.route("/signal-history", methods=["GET"])
def get_signal_history():
    """获取信号历史"""
    from config.database import DatabaseConfig

    code = request.args.get("code")
    limit = int(request.args.get("limit", 50))

    db = DatabaseConfig.get_database()

    filter_doc = {}
    if code:
        filter_doc["code"] = _normalize_code(code)

    history = list(db["signal_history"].find(
        filter_doc,
        sort=[("timestamp", -1)],
        limit=limit
    ))

    for h in history:
        h.pop("_id", None)

    return jsonify({
        "success": True,
        "count": len(history),
        "data": history
    })


@market_bp.route("/save-signal", methods=["POST"])
def save_signal():
    """保存信号到历史"""
    from config.database import DatabaseConfig

    data = request.get_json() or {}

    code = data.get("code")
    signal = data.get("signal", "neutral")
    strength = data.get("strength", "弱")
    price = data.get("price", 0)
    reasons = data.get("reasons", [])

    if not code:
        return jsonify({"error": "code is required"}), 400

    code = _normalize_code(code)

    signal_doc = {
        "code": code,
        "signal": signal,
        "type": signal,
        "strength": strength,
        "price": price,
        "reasons": reasons,
        "timestamp": beijing_now().isoformat()
    }

    db = DatabaseConfig.get_database()
    db["signal_history"].insert_one(signal_doc)

    return jsonify({
        "success": True,
        "message": "Signal saved"
    })