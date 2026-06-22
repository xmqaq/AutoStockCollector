"""风险管理 — 止损位、止盈位、仓位计算。

基于 ATR 和固定百分比两种模式。
"""
from typing import Any, Dict

from .config import PAConfig


VALID_LONG_SIGNALS = {"BUY_SETUP", "WEAK_BUY"}
VALID_SHORT_SIGNALS = {"SELL_SETUP", "WEAK_SELL"}


def calculate_trade_plan(
    entry_price: float,
    signal_type: str,
    atr: float = 0,
    demand_zones: list = None,
    supply_zones: list = None,
    account_balance: float = 100000.0,
    risk_pct: float = 0.02,
) -> Dict[str, Any]:
    """计算交易计划。

    仅对 LONG/SHORT 信号生成计划。NEUTRAL/NO_TRADE/NO_DATA 返回空计划。
    """
    is_buy = signal_type in VALID_LONG_SIGNALS
    is_short = signal_type in VALID_SHORT_SIGNALS

    if not is_buy and not is_short:
        return {"direction": "none", "entry": round(entry_price, 2), "position_size": 0, "position_value": 0, "total_risk": 0, "r_r_ratio": "1:0"}
    sl_distance = max(atr * PAConfig.ATR_STOP_MULTIPLIER, entry_price * PAConfig.PCT_STOP_MIN)

    if is_buy:
        if demand_zones:
            zone_low = min(z["low"] for z in demand_zones)
            sl_candidate = zone_low * (1 - PAConfig.ZONE_MERGE_THRESHOLD)
            sl = min(sl_candidate, entry_price - sl_distance)
        else:
            sl = entry_price - sl_distance
        tp = entry_price + sl_distance * PAConfig.REWARD_MULTIPLIER
    else:
        if supply_zones:
            zone_high = max(z["high"] for z in supply_zones)
            sl_candidate = zone_high * (1 + PAConfig.ZONE_MERGE_THRESHOLD)
            sl = max(sl_candidate, entry_price + sl_distance)
        else:
            sl = entry_price + sl_distance
        tp = entry_price - sl_distance * PAConfig.REWARD_MULTIPLIER

    risk_per_share = abs(entry_price - sl)
    if risk_per_share <= 0:
        risk_per_share = entry_price * PAConfig.RISK_FALLBACK_PCT

    max_risk = account_balance * risk_pct
    position_size = int(max_risk / risk_per_share)

    # 仓位上限：单票不超过账户总资产的 25%
    max_position_value = account_balance * PAConfig.MAX_POSITION_PCT
    max_shares_by_value = int(max_position_value / entry_price)
    position_size = min(position_size, max_shares_by_value)

    # 取整到 100 股（1 手），至少 100 股
    position_size = max(position_size, 100)
    position_size = (position_size // 100) * 100

    reward = abs(tp - entry_price)
    r_r_ratio = round(reward / risk_per_share, 2) if risk_per_share > 0 else 0

    return {
        "direction": "long" if is_buy else "short",
        "entry": round(entry_price, 2),
        "stop_loss": round(sl, 2),
        "take_profit": round(tp, 2),
        "position_size": position_size,
        "position_value": round(position_size * entry_price, 2),
        "risk_per_share": round(risk_per_share, 2),
        "total_risk": round(position_size * risk_per_share, 2),
        "r_r_ratio": f"1:{r_r_ratio}",
    }
