"""再平衡建议：目标组合权重 + 当前持仓 + 现金 → 具体买卖订单清单。

纯计算、无 IO，所有数据由调用方传入，便于单测。
"""
from typing import Any, Dict, List, Optional
import math

DEFAULT_FEES = {
    "buy_commission_rate": 0.0003,
    "sell_commission_rate": 0.0003,
    "min_commission": 5.0,
    "stamp_tax_rate": 0.001,
}


def _buy_cost(amount: float, fees: Dict[str, float]) -> float:
    commission = max(fees["min_commission"], amount * fees["buy_commission_rate"])
    return amount + commission


def _sell_net(amount: float, fees: Dict[str, float]) -> float:
    commission = max(fees["min_commission"], amount * fees["sell_commission_rate"])
    tax = amount * fees["stamp_tax_rate"]
    return amount - commission - tax


def build_rebalance_orders(
    target_positions: List[Dict[str, Any]],
    current_positions: List[Dict[str, Any]],
    cash: float,
    prices: Dict[str, float],
    buffer: float = 0.05,
    fees: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    fees = fees or DEFAULT_FEES
    held = {p["code"]: p for p in current_positions}
    target_codes = {t["code"] for t in target_positions}

    total_value = cash + sum((p.get("market_value") or 0) for p in current_positions)

    sell_orders: List[Dict[str, Any]] = []
    buy_candidates: List[Dict[str, Any]] = []

    def _cur_weight(code: str) -> float:
        mv = (held.get(code, {}).get("market_value") or 0)
        return round(mv / total_value * 100, 2) if total_value > 0 else 0.0

    # ── 1. 持有但不在目标 → 清仓卖出 ──
    for code, hp in held.items():
        if code in target_codes:
            continue
        price = prices.get(code) or hp.get("current_price")
        sell_orders.append({
            "code": code, "name": hp.get("name", code), "action": "sell",
            "shares": hp["shares"], "price": price,
            "target_weight": 0.0, "current_weight": _cur_weight(code),
            "reason": f"未入选目标组合，清仓 {hp['shares']} 股",
            "skipped": False, "skip_reason": None,
        })

    # ── 2. 目标票：算目标股数，与现持做差（含缓冲带） ──
    for t in sorted(target_positions, key=lambda x: -(x.get("composite") or 0)):
        code = t["code"]
        price = prices.get(code)
        cur_shares = held.get(code, {}).get("shares", 0)
        cur_w = _cur_weight(code)
        if not price or price <= 0:
            buy_candidates.append({
                "code": code, "name": t.get("name", code), "action": "buy",
                "shares": 0, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": "无法取得实时价格", "skipped": True,
                "skip_reason": "无实时价格（停牌或行情接口失败），已跳过",
                "composite": t.get("composite") or 0,
            })
            continue

        target_value = t["weight"] / 100.0 * total_value
        target_shares_float = target_value / price
        target_shares = int(math.floor(target_shares_float / 100) * 100)
        # 如果目标金额非零但四舍五入到0，则至少买一手（100股）
        if target_shares == 0 and target_shares_float > 0:
            target_shares = 100
        diff = target_shares - cur_shares

        # 缓冲带：调仓金额占净值比 < buffer → 不动
        if total_value > 0 and abs(diff) * price / total_value < buffer:
            continue
        if diff == 0:
            continue

        if diff > 0:
            buy_candidates.append({
                "code": code, "name": t.get("name", code), "action": "buy",
                "shares": diff, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": f"目标权重 {t['weight']}%，欠配，买入 {diff} 股",
                "skipped": False, "skip_reason": None,
                "composite": t.get("composite") or 0,
            })
        else:
            sell_orders.append({
                "code": code, "name": t.get("name", code), "action": "sell",
                "shares": -diff, "price": price,
                "target_weight": t["weight"], "current_weight": cur_w,
                "reason": f"目标权重 {t['weight']}%，超配，卖出 {-diff} 股",
                "skipped": False, "skip_reason": None,
            })

    # ── 3. 资金校验：先卖释放现金，买单按评分高→低，不够则跳过低优先级 ──
    available = cash + sum(_sell_net(o["shares"] * o["price"], fees)
                           for o in sell_orders if o["price"])
    buy_orders: List[Dict[str, Any]] = []
    for o in buy_candidates:  # 已按 composite 降序（停牌的 shares=0 不耗现金）
        if o["skipped"]:
            buy_orders.append(o)
            continue
        cost = _buy_cost(o["shares"] * o["price"], fees)
        if cost > available:
            o["skipped"] = True
            o["skip_reason"] = f"现金不足（需 {cost:.0f} 元，可用 {available:.0f} 元），已跳过"
        else:
            available -= cost
        buy_orders.append(o)

    orders = sell_orders + buy_orders
    for o in orders:
        o.pop("composite", None)
    return {"total_value": round(total_value, 2), "buffer": buffer, "orders": orders}


if __name__ == "__main__":
    # 冒烟自检
    r = build_rebalance_orders(
        [{"code": "600519", "name": "茅台", "weight": 40.0, "composite": 80, "industry": "白酒"}],
        [], 100000.0, {"600519": 200.0},
    )
    assert r["orders"][0]["shares"] == 200, r
    print("advisor self-check OK")
