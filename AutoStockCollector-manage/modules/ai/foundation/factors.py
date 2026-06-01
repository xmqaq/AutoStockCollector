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


def valuation_score(
    pe: Optional[float],
    pb: Optional[float],
    ps: Optional[float] = None,
    roe: Optional[float] = None,
    gross_margin: Optional[float] = None,
    debt_ratio: Optional[float] = None,
    revenue_growth: Optional[float] = None,
    profit_growth: Optional[float] = None,
) -> float:
    """综合基本面评分。

    维度：
      · TTM PE（相对质量调整后的容忍区间，高 ROE/高毛利公司给予更高容忍）
      · PB（结合 ROE 判断是否物有所值）
      · ROE（盈利能力核心指标，权重最高）
      · 毛利率（商业模式护城河）
      · 负债率（财务稳健性）
      · 营收 / 利润增速（成长性）
    """
    score = 50.0

    # ── 质量特征：判断是否高 ROE / 高毛利公司（放宽 PE/PB 容忍）──
    high_quality = bool(
        (roe is not None and roe >= 20) or
        (gross_margin is not None and gross_margin >= 50)
    )

    # ── TTM PE ──
    if pe is not None and pe > 0:
        if pe <= 10:
            score += 12
        elif pe <= 20:
            score += 8
        elif pe <= 30:
            score += 4
        elif pe <= 50:
            # 高质量公司 PE 30-50 不扣分，普通公司小幅扣分
            score += 0 if high_quality else -3
        elif pe <= 80:
            score += -5 if high_quality else -12
        else:
            score -= 15
    elif pe is not None and pe <= 0:
        score -= 10  # 亏损

    # ── PB ──
    if pb is not None and pb > 0:
        # ROE 高时，高 PB 仍合理
        roe_adj = roe if roe is not None else 0
        if pb < 1:
            score += 8
        elif pb < 3:
            score += 5
        elif pb < 6:
            score += 3 if roe_adj >= 15 else 0
        elif pb < 10:
            score += 0 if roe_adj >= 20 else -5
        else:
            score -= 8

    # ── ROE（权重最高：±20） ──
    if roe is not None:
        if roe >= 25:
            score += 20
        elif roe >= 20:
            score += 15
        elif roe >= 15:
            score += 10
        elif roe >= 10:
            score += 5
        elif roe >= 0:
            score += 0
        else:
            score -= 15

    # ── 毛利率（±10） ──
    if gross_margin is not None:
        if gross_margin >= 70:
            score += 10
        elif gross_margin >= 50:
            score += 7
        elif gross_margin >= 30:
            score += 3
        elif gross_margin >= 10:
            score += 0
        else:
            score -= 5

    # ── 负债率（±8） ──
    if debt_ratio is not None:
        if debt_ratio < 30:
            score += 8
        elif debt_ratio < 50:
            score += 3
        elif debt_ratio < 70:
            score -= 3
        else:
            score -= 8

    # ── 营收增速（±5） ──
    if revenue_growth is not None:
        if revenue_growth >= 20:
            score += 5
        elif revenue_growth >= 5:
            score += 2
        elif revenue_growth < 0:
            score -= 5

    # ── 利润增速（±5） ──
    if profit_growth is not None:
        if profit_growth >= 20:
            score += 5
        elif profit_growth >= 5:
            score += 2
        elif profit_growth < -10:
            score -= 5
        elif profit_growth < 0:
            score -= 2

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
