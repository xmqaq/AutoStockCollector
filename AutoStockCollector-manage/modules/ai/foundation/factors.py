"""纯计算因子引擎。所有函数吃已取好的数据，返回 0–100 分。无 DB / 无网络。

公式提炼自原 smart_picker.py 与 ai_analyzer.py，剥离其中的数据库读取。
"""
from typing import Dict, List, Optional


def trend_score(closes: List[float]) -> float:
    """趋势因子。closes 按时间倒序（[最新, ..., 最早]），至少 5 条。"""
    if len(closes) < 5:
        return 50.0
    ma5 = sum(closes[:5]) / 5
    ma20 = sum(closes[:20]) / min(len(closes), 20)
    current = closes[0]
    if current > ma5 > ma20:
        return 80.0
    if current > ma5:
        return 65.0
    if current < ma5 < ma20:
        return 30.0
    return 50.0


def volume_score(volumes: List[float]) -> float:
    """量能因子。volumes 按时间倒序，至少 5 条。放量加分。"""
    if len(volumes) < 5:
        return 50.0
    avg_vol = sum(volumes[1:]) / max(len(volumes) - 1, 1)
    current_vol = volumes[0]
    if avg_vol > 0 and current_vol > avg_vol * 1.5:
        return min(95.0, 50.0 + (current_vol / avg_vol) * 10.0)
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
