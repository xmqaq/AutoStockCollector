"""纯计算因子引擎。所有函数吃已取好的数据，返回 0–100 分。无 DB / 无网络。

公式提炼自原 smart_picker.py 与 ai_analyzer.py，剥离其中的数据库读取。
"""
from typing import Dict, List, Optional


def trend_score(closes: List[float]) -> float:
    """趋势因子。closes 按时间倒序（[最新, ..., 最早]），至少 5 条。
    引入涨跌幅动量使得同处上升趋势的股票也能拉开差距。
    """
    if len(closes) < 5:
        return 50.0
    n20 = min(len(closes), 20)
    ma5 = sum(closes[:5]) / 5
    ma20 = sum(closes[:n20]) / n20
    current = closes[0]

    # 基础趋势档位
    if current > ma5 > ma20:
        base = 75.0
    elif current > ma5:
        base = 60.0
    elif current < ma5 < ma20:
        base = 25.0
    else:
        base = 45.0

    # 动量修正：5 日涨跌幅连续性，最多 ±15 分
    if len(closes) >= 6:
        ret5 = (closes[0] - closes[5]) / closes[5] if closes[5] > 0 else 0
        momentum = max(-15.0, min(15.0, ret5 * 200))  # 7.5% 涨幅 → +15 分
        base = base + momentum

    # 均线粘合惩罚：ma5 与 ma20 差距小于 0.5% 视为震荡，降 5 分
    if ma20 > 0 and abs(ma5 - ma20) / ma20 < 0.005:
        base -= 5.0

    return max(0.0, min(100.0, base))


def volume_score(volumes: List[float]) -> float:
    """量能因子。volumes 按时间倒序，至少 5 条。放量加分，萎缩扣分。"""
    if len(volumes) < 5:
        return 50.0
    avg_vol = sum(volumes[1:]) / max(len(volumes) - 1, 1)
    current_vol = volumes[0]
    if avg_vol <= 0:
        return 50.0
    ratio = current_vol / avg_vol
    if ratio > 2.0:
        return min(95.0, 50.0 + (ratio - 1) * 15.0)
    if ratio > 1.5:
        return min(80.0, 50.0 + (ratio - 1) * 10.0)
    if ratio < 0.5:
        return max(20.0, 50.0 - (1 - ratio) * 30.0)
    return 50.0


def valuation_score(pe: Optional[float], pb: Optional[float], ps: Optional[float]) -> float:
    """估值因子。合理 PE/PB 加分，高估扣分。"""
    score = 50.0
    if pe and 5 < pe < 25:
        score += 15
    elif pe and 0 < pe <= 5:
        score += 10
    elif pe and 25 <= pe < 40:
        score += 5
    elif pe and pe >= 40:
        score -= 15

    if pb and 0.5 < pb < 3:
        score += 10
    elif pb and pb >= 3:
        score -= 5

    return max(0.0, min(100.0, score))


def fund_flow_score(main_net_inflow: Optional[float]) -> float:
    """资金流因子。主力净流入(元)为正加分、为负扣分。用 1 亿元做满分标度。"""
    if not main_net_inflow:
        return 50.0
    scale = 1e8
    delta = max(-40.0, min(40.0, (main_net_inflow / scale) * 40.0))
    return max(0.0, min(100.0, 50.0 + delta))


def composite_score(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """综合评分。缺失的维度跳过并对剩余权重重归一化。"""
    total_w = 0.0
    acc = 0.0
    for dim, w in weights.items():
        if dim in scores and scores[dim] is not None:
            acc += scores[dim] * w
            total_w += w
    if total_w == 0:
        return 50.0
    return acc / total_w
