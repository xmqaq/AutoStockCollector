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


def _capped_weights(items: List[Dict[str, Any]], max_weight: float,
                    total_budget: float = 1.0) -> Dict[str, float]:
    """评分加权 + 单仓上限，返回 {code: weight_frac(0-1)}，加总 = total_budget。
    weight_i = composite_i / Σcomposite × total_budget，超 max_weight 的截断在上限，
    剩余权重在未封顶的票里按评分再分配，迭代到收敛。"""
    capped: Dict[str, float] = {}
    remaining = list(items)
    budget = total_budget
    while remaining:
        total = sum(p["composite"] for p in remaining)
        over = [p for p in remaining if p["composite"] / total * budget > max_weight]
        if not over:
            for p in remaining:
                capped[p["code"]] = p["composite"] / total * budget
            break
        for p in over:
            capped[p["code"]] = max_weight
            budget -= max_weight
        remaining = [p for p in remaining if p["code"] not in capped]
    return capped


def build_score_weighted_targets(
    picks: List[Dict[str, Any]],
    max_weight: float = 0.30,
    prices: Optional[Dict[str, float]] = None,
    capital: Optional[float] = None,
    invest_ratio: float = 1.0,
) -> List[Dict[str, Any]]:
    """把"只有评分、没有权重"的选股结果（如量化选股）转成按综合评分加权的目标组合。

    返回 [{code, name, weight(0-100), composite, industry}]，供 build_rebalance_orders 消费。

    invest_ratio：目标投入比例（0-1）。默认 1.0 满仓；设 0.8 则目标权重加总=80%，
    主动留 20% 现金当子弹（后续加仓用）。

    A1 整手可行性：传入 prices+capital 时，剔除"按目标预算连一手(100股)都买不起"的高价票
    （如 10 万本金下茅台一手十几万），权重在买得起的票里重新归一化。否则那部分钱永远投不出去。
    """
    invest_ratio = min(max(invest_ratio, 0.0), 1.0)
    valid = [p for p in picks if (p.get("composite") or 0) > 0]
    if not valid or invest_ratio <= 0:
        return []
    if prices and capital and capital > 0:
        while len(valid) > 1:
            w = _capped_weights(valid, max_weight, invest_ratio)
            # 一手成本 > 该票目标预算(weight×capital) → 买不起一手，剔除
            unaffordable = {p["code"] for p in valid
                            if prices.get(p["code"]) and prices[p["code"]] * 100 > w[p["code"]] * capital}
            if not unaffordable or len(unaffordable) >= len(valid):
                break  # 没有买不起的，或全都买不起(本金过小)→ 不再剔除
            valid = [p for p in valid if p["code"] not in unaffordable]
    capped = _capped_weights(valid, max_weight, invest_ratio)
    return [{
        "code": p["code"],
        "name": p.get("name", p["code"]),
        "weight": round(capped[p["code"]] * 100, 2),
        "composite": p["composite"],
        "industry": p.get("industry", "未知"),
    } for p in valid]


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
        target_shares = int(math.floor(target_value / price / 100) * 100)
        diff = target_shares - cur_shares

        # 缓冲带：已持仓的票，调仓金额占净值比 < buffer → 不动（防小幅频繁调仓）。
        # 空仓建仓(cur_shares==0)不走缓冲带，否则小权重目标永远买不进。
        if cur_shares > 0 and total_value > 0 and abs(diff) * price / total_value < buffer:
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

    # 空仓建仓：小权重目标(3% < 5%缓冲带)也必须建仓，不能被缓冲带吞掉
    r2 = build_rebalance_orders(
        [{"code": "000001", "name": "小仓", "weight": 3.0, "composite": 60, "industry": "银行"}],
        [], 100000.0, {"000001": 10.0},
    )
    bought = [o for o in r2["orders"] if o["action"] == "buy" and not o["skipped"]]
    assert bought and bought[0]["shares"] == 300, r2  # 3000元/10元=300股

    # A1：10万本金下，茅台(一手16万)买不起一手 → 被剔除；其余低价票归一化（单仓上限30%内）
    picks = [{"code": "600519", "name": "茅台", "composite": 80}] + \
            [{"code": f"00000{i}", "name": f"低价{i}", "composite": 70} for i in range(4)]
    px = {"600519": 1600, **{f"00000{i}": 20 for i in range(4)}}
    t = build_score_weighted_targets(picks, prices=px, capital=100000.0)
    codes = {x["code"] for x in t}
    assert "600519" not in codes and len(codes) == 4, t          # 茅台剔除，4只低价票留下
    assert abs(sum(x["weight"] for x in t) - 100.0) < 0.5, t      # 权重归一化到~100%
    # 不传 prices/capital 时不剔除（向后兼容）
    assert len(build_score_weighted_targets(picks)) == 5

    # invest_ratio=0.5 → 目标权重加总≈50%，留50%现金
    t5 = build_score_weighted_targets(
        [{"code": f"00000{i}", "composite": 70} for i in range(5)], invest_ratio=0.5)
    assert abs(sum(x["weight"] for x in t5) - 50.0) < 0.5, t5

    # 幂等性：建仓后再次生成应无新订单（不能反复买卖震荡）
    tg = build_score_weighted_targets(
        [{"code": f"S{i}", "name": f"S{i}", "composite": 80 - i} for i in range(6)],
        prices={f"S{i}": 28.0 for i in range(6)}, capital=100000.0)
    px = {f"S{i}": 28.0 for i in range(6)}
    a1 = build_rebalance_orders(tg, [], 100000.0, px)
    pos = [{"code": o["code"], "name": o["code"], "shares": o["shares"],
            "market_value": o["shares"] * px[o["code"]], "current_price": px[o["code"]]}
           for o in a1["orders"] if o["action"] == "buy" and not o["skipped"]]
    spent = sum(p["market_value"] for p in pos)
    a2 = build_rebalance_orders(tg, pos, 100000.0 - spent, px)
    assert not [o for o in a2["orders"] if not o["skipped"]], a2  # 第二轮无可执行订单
    print("advisor self-check OK")
