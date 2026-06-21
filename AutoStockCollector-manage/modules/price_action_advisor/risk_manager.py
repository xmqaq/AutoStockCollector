"""风险管理 — 止损位、止盈位、仓位计算。

基于 ATR 和固定百分比两种模式。
"""
from typing import Any, Dict


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

    Args:
        entry_price: 入场价
        signal_type: BUY_SETUP / SELL_SETUP
        atr: ATR 值
        demand_zones: 需求区列表 [{low, high}]
        supply_zones: 供应区列表 [{low, high}]
        account_balance: 账户总资金
        risk_pct: 单笔风险百分比
    Returns:
        dict {entry, stop_loss, take_profit, position_size, r_r_ratio}
    """
    is_buy = signal_type in ("BUY_SETUP", "WEAK_BUY")
    sl_distance = max(atr * 1.5, entry_price * 0.015)

    if is_buy:
        if demand_zones:
            zone_low = min(z["low"] for z in demand_zones)
            sl_candidate = zone_low * 0.99
            sl = min(sl_candidate, entry_price - sl_distance)
        else:
            sl = entry_price - sl_distance
        tp = entry_price + sl_distance * 2
    else:
        if supply_zones:
            zone_high = max(z["high"] for z in supply_zones)
            sl_candidate = zone_high * 1.01
            sl = max(sl_candidate, entry_price + sl_distance)
        else:
            sl = entry_price + sl_distance
        tp = entry_price - sl_distance * 2

    risk_per_share = abs(entry_price - sl)
    if risk_per_share <= 0:
        risk_per_share = entry_price * 0.02

    max_risk = account_balance * risk_pct
    position_size = int(max_risk / risk_per_share)
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
