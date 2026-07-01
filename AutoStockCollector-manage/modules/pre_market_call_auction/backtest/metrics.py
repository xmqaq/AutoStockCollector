"""回测绩效指标计算 — 分桶胜率/盈亏比/夏普/最大回撤/单调性。"""
from typing import Any, Dict, List

from utils.logger import get_logger

logger = get_logger(__name__)


def compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算回测绩效：按强度分桶 + 整体指标 + 单调性检验。

    分桶：[0-39, 40-59, 60-79, 80-100]，每桶算 count/wins/win_rate/avg_return/profit_factor。
    整体：total_trades/win_rate/avg_return/profit_factor/sharpe/max_drawdown/monotonicity。
    单调性：高桶 win_rate 应 >= 低桶 win_rate，否则因子无效。
    """
    if not trades:
        return {"buckets": [], "overall": {"total_trades": 0}, "monotonicity": None}

    buckets = _bucket_by_score(trades, [0, 40, 60, 80, 101])
    daily_returns = _aggregate_daily(trades)
    overall = {
        "total_trades": len(trades),
        "win_rate": _win_rate(trades),
        "avg_return": _avg([t.get("return_pct", 0) for t in trades]),
        "profit_factor": _profit_factor(trades),
        "sharpe": _sharpe(daily_returns),
        "max_drawdown": _max_drawdown(daily_returns),
        "total_return": sum(daily_returns) if daily_returns else 0,
    }
    monotonicity = _check_monotonicity(buckets)
    return {"buckets": buckets, "overall": overall, "monotonicity": monotonicity}


def _bucket_by_score(trades: List[Dict], boundaries: List[int]) -> List[Dict]:
    """按 strength_score 分桶。"""
    labels = {0: "0-39", 40: "40-59", 60: "60-79", 80: "80-100"}
    buckets: Dict[int, Dict] = {}
    for t in trades:
        score = t.get("strength_score", 0)
        bid = 0
        for b in boundaries:
            if score >= b:
                bid = b
        b = buckets.setdefault(bid, {"score_bracket": labels.get(bid, str(bid)),
                                     "count": 0, "wins": 0, "returns": []})
        b["count"] += 1
        ret = t.get("return_pct", 0)
        b["returns"].append(ret)
        if ret > 0:
            b["wins"] += 1

    result = []
    for bid in sorted(buckets.keys(), reverse=True):
        b = buckets[bid]
        rets = b.pop("returns")
        b["win_rate"] = round(b["wins"] / b["count"], 4) if b["count"] > 0 else 0
        b["avg_return"] = round(_avg(rets), 4)
        b["total_return"] = round(sum(rets), 4)
        b["profit_factor"] = round(_profit_factor([{"return_pct": r} for r in rets]), 4)
        result.append(b)
    return result


def _aggregate_daily(trades: List[Dict]) -> List[float]:
    """按日期聚合日均收益率。"""
    daily: Dict[str, List[float]] = {}
    for t in trades:
        d = t.get("date", "")
        daily.setdefault(d, []).append(t.get("return_pct", 0))
    return [sum(v) / len(v) if v else 0 for v in daily.values()]


def _win_rate(trades: List[Dict]) -> float:
    if not trades:
        return 0
    wins = sum(1 for t in trades if t.get("return_pct", 0) > 0)
    return round(wins / len(trades), 4)


def _avg(values: List[float]) -> float:
    if not values:
        return 0
    return round(sum(values) / len(values), 4)


def _profit_factor(trades: List[Dict]) -> float:
    gross_profit = sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0)
    gross_loss = abs(sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0
    return round(gross_profit / gross_loss, 4)


def _sharpe(daily_returns: List[float]) -> float:
    """简化夏普：日均收益/标准差 * sqrt(252)。无波动返回 0。"""
    if len(daily_returns) < 2:
        return 0
    import math
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0
    return round(mean / std * math.sqrt(252), 4)


def _max_drawdown(daily_returns: List[float]) -> float:
    """累计收益曲线的最大回撤（%）。"""
    if not daily_returns:
        return 0
    cumulative = 0
    peak = 0
    max_dd = 0
    for r in daily_returns:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _check_monotonicity(buckets: List[Dict]) -> bool:
    """单调性：高分桶 win_rate 应 >= 低分桶 win_rate。"""
    if len(buckets) < 2:
        return None
    # buckets 已按 score 降序
    rates = [b.get("win_rate", 0) for b in buckets]
    return all(rates[i] >= rates[i + 1] - 0.05 for i in range(len(rates) - 1))
