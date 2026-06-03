"""多因子量化评分引擎。所有函数吃已取好的数据，返回 (score, details)。
score 范围 0–100，details 含各子维度得分和原始值。无 DB / 无网络。
"""
from typing import Any, Dict, List, Optional, Tuple
import math

DetailScore = Tuple[float, Dict[str, Any]]

_FINANCE_INDUSTRIES = ("货币金融服务", "银行", "保险", "证券", "资本市场服务",
                       "多元金融", "其他金融业")
_HIGH_PE_INDUSTRIES = ("软件和信息技术服务业", "医药制造业", "计算机",
                       "电子", "通信", "生物医药", "半导体")


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 基本面评分 (30%)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fundamental_score(
    roe: Optional[float] = None,
    revenue_growth: Optional[float] = None,
    profit_growth: Optional[float] = None,
    gross_margin: Optional[float] = None,
    debt_ratio: Optional[float] = None,
    industry: str = "",
) -> DetailScore:
    """基本面综合评分。输入值为百分比数字（10.57 表示 10.57%）。"""
    details: Dict[str, Any] = {"data_available": True}
    is_finance = any(kw in industry for kw in _FINANCE_INDUSTRIES)

    # ROE（满分35）
    if roe is not None:
        if roe >= 25:    roe_s = 35
        elif roe >= 20:  roe_s = 30
        elif roe >= 15:  roe_s = 24
        elif roe >= 10:  roe_s = 18
        elif roe >= 5:   roe_s = 10
        elif roe >= 0:   roe_s = 5
        else:            roe_s = 0
    else:
        roe_s = 17
    if revenue_growth is not None and revenue_growth > 50 and roe is not None and roe >= 10:
        roe_bonus = min(5.0, (revenue_growth - 50) / 10)
        roe_s = min(35, roe_s + roe_bonus)
        details["roe_growth_bonus"] = f"+{roe_bonus:.1f}分（高速成长期调整）"
    details["roe"] = {"value": roe, "score": roe_s, "max": 35}

    # 营收增速（满分20）
    if revenue_growth is not None:
        rg = min(revenue_growth, 500)
        if rg >= 30:     rev_s = 20
        elif rg >= 20:   rev_s = 16
        elif rg >= 10:   rev_s = 12
        elif rg >= 0:    rev_s = 8
        else:            rev_s = 4
    else:
        rev_s = 10
    details["revenue_growth"] = {"value": revenue_growth, "score": rev_s, "max": 20}

    # 净利润增速（满分20）
    if profit_growth is not None:
        pg = min(profit_growth, 500)
        if pg >= 30:     pg_s = 20
        elif pg >= 20:   pg_s = 16
        elif pg >= 10:   pg_s = 12
        elif pg >= 0:    pg_s = 8
        else:            pg_s = 4
    else:
        pg_s = 10
    details["profit_growth"] = {"value": profit_growth, "score": pg_s, "max": 20}

    # 毛利率（满分15）
    if gross_margin is not None:
        if gross_margin >= 60:   gm_s = 15
        elif gross_margin >= 40: gm_s = 12
        elif gross_margin >= 25: gm_s = 9
        elif gross_margin >= 10: gm_s = 6
        else:                    gm_s = 3
    else:
        gm_s = 7
    details["gross_margin"] = {"value": gross_margin, "score": gm_s, "max": 15}

    # 资产负债率（满分10，越低越好）
    if debt_ratio is not None:
        if is_finance:
            # 金融行业负债率天然高
            if debt_ratio <= 70:   dr_s = 10
            elif debt_ratio <= 85: dr_s = 8
            elif debt_ratio <= 95: dr_s = 6
            else:                  dr_s = 4
        else:
            if debt_ratio <= 30:   dr_s = 10
            elif debt_ratio <= 40: dr_s = 9
            elif debt_ratio <= 50: dr_s = 8
            elif debt_ratio <= 60: dr_s = 6
            elif debt_ratio <= 70: dr_s = 5
            elif debt_ratio <= 80: dr_s = 3
            elif debt_ratio <= 85: dr_s = 2
            else:                  dr_s = 1
    else:
        dr_s = 5
    details["debt_ratio"] = {"value": debt_ratio, "score": dr_s, "max": 10, "is_finance": is_finance}

    total = roe_s + rev_s + pg_s + gm_s + dr_s
    score = _clamp(total)
    return score, details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 技术面评分 (25%)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ema(data: List[float], period: int) -> List[float]:
    if not data:
        return []
    k = 2.0 / (period + 1)
    result = [data[0]]
    for v in data[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1 + rs)


def technical_score(closes: List[float], amounts: List[float]) -> DetailScore:
    """技术面评分。closes/amounts 按时间**正序**（旧→新）。"""
    details: Dict[str, Any] = {"data_available": True}
    n = len(closes)
    if n < 15:
        return 50.0, {"data_available": False, "reason": f"K线不足({n}条)"}

    cur = closes[-1]

    # 均线趋势（满分30）
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20 if n >= 20 else None
    ma60 = sum(closes[-60:]) / 60 if n >= 60 else None

    if ma60 and ma20 and cur > ma5 > ma20 > ma60:
        ma_s = 30
        ma_label = "强多头排列"
    elif ma20 and cur > ma5 > ma20:
        ma_s = 24
        ma_label = "多头排列"
    elif ma20 and cur > ma20:
        ma_s = 15
        ma_label = "站上20日线"
    elif ma20 and cur < ma20:
        ma_s = 5
        ma_label = "低于20日线"
    else:
        ma_s = 12
        ma_label = "震荡"
    details["ma_trend"] = {"value": ma_label, "score": ma_s, "max": 30,
                           "ma5": round(ma5, 2), "ma20": round(ma20, 2) if ma20 else None}

    # MACD（满分25）
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif_line = [a - b for a, b in zip(ema12, ema26)]
    dea_line = _ema(dif_line, 9)
    macd_bar = [(d - e) * 2 for d, e in zip(dif_line, dea_line)]

    dif = dif_line[-1] if dif_line else 0
    dea = dea_line[-1] if dea_line else 0
    bar = macd_bar[-1] if macd_bar else 0
    prev_bar = macd_bar[-2] if len(macd_bar) >= 2 else 0

    if dif > dea and bar > 0 and bar > prev_bar:
        macd_s = 25
        macd_label = "金叉扩张"
    elif dif > dea and bar > 0:
        macd_s = 20
        macd_label = "金叉"
    elif dif > dea:
        macd_s = 15
        macd_label = "DIF>DEA"
    elif dif < dea and len(macd_bar) >= 2 and abs(bar) < abs(prev_bar):
        macd_s = 10
        macd_label = "空头收窄"
    else:
        macd_s = 5
        macd_label = "空头"
    details["macd"] = {"value": macd_label, "score": macd_s, "max": 25,
                       "dif": round(dif, 4), "dea": round(dea, 4)}

    # RSI（满分20）
    rsi_val = _rsi(closes, 14)
    if rsi_val is not None:
        if 45 <= rsi_val <= 65:
            rsi_s = 20
        elif 65 < rsi_val <= 75:
            rsi_s = 15
        elif rsi_val > 75:
            rsi_s = 8
        elif 35 <= rsi_val < 45:
            rsi_s = 15
        else:
            rsi_s = 10
    else:
        rsi_s = 10
    details["rsi"] = {"value": round(rsi_val, 2) if rsi_val else None, "score": rsi_s, "max": 20}

    # 价格动量（满分25）
    lookback = min(20, n - 1)
    momentum_pct = (closes[-1] - closes[-(lookback + 1)]) / closes[-(lookback + 1)] * 100 if closes[-(lookback + 1)] > 0 else 0
    if momentum_pct > 30:
        mom_s = 10
    elif momentum_pct > 15:
        mom_s = 25
    elif momentum_pct > 8:
        mom_s = 20
    elif momentum_pct > 3:
        mom_s = 16
    elif momentum_pct > 0:
        mom_s = 12
    elif momentum_pct > -5:
        mom_s = 8
    else:
        mom_s = 4
    details["momentum"] = {"value": round(momentum_pct, 2), "period": lookback,
                           "score": mom_s, "max": 25}
    if momentum_pct > 30:
        details["momentum_warning"] = f"短期涨幅{momentum_pct:.1f}%超过30%，注意追高风险"

    if momentum_pct > 20 and rsi_val is not None and rsi_val > 65:
        details["technical_warning"] = (
            f"短期涨幅{momentum_pct:.1f}%且RSI={rsi_val:.1f}，技术面偏热，注意回调风险"
        )

    total = ma_s + macd_s + rsi_s + mom_s
    return _clamp(total), details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 资金面评分 (20%)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fund_flow_detail_score(
    main_net_inflow: Optional[float] = None,
    total_amount: Optional[float] = None,
    turnover_rate: Optional[float] = None,
) -> DetailScore:
    """资金面评分。main_net_inflow/total_amount 单位元，turnover_rate 百分比数字。"""
    details: Dict[str, Any] = {"data_available": True}

    if main_net_inflow is None:
        return 50.0, {"data_available": False, "reason": "无资金流向数据"}

    # 主力净流入（满分50）
    inflow_yi = main_net_inflow / 1e8
    if main_net_inflow > 1e8:
        inf_s = 50
    elif main_net_inflow > 5e7:
        inf_s = 42
    elif main_net_inflow > 2e7:
        inf_s = 34
    elif main_net_inflow > 0:
        inf_s = 25
    elif main_net_inflow > -2e7:
        inf_s = 15
    else:
        inf_s = 6
    details["net_inflow"] = {"value_yi": round(inflow_yi, 4), "score": inf_s, "max": 50}

    # 主力占比（满分30）
    if total_amount and total_amount > 0:
        ratio = main_net_inflow / total_amount * 100
        if ratio > 5:
            rat_s = 30
        elif ratio > 2:
            rat_s = 24
        elif ratio > 0:
            rat_s = 18
        else:
            rat_s = 8
        details["main_ratio"] = {"value": round(ratio, 2), "score": rat_s, "max": 30}
    else:
        rat_s = 15
        details["main_ratio"] = {"value": None, "score": rat_s, "max": 30}

    # 换手率（满分20）
    if turnover_rate is not None:
        if 1 <= turnover_rate <= 5:
            tr_s = 20
        elif 5 < turnover_rate <= 10:
            tr_s = 14
        elif turnover_rate > 10:
            tr_s = 8
        elif 0.3 <= turnover_rate < 1:
            tr_s = 14
        else:
            tr_s = 8
    else:
        tr_s = 10
    details["turnover_rate"] = {"value": turnover_rate, "score": tr_s, "max": 20}

    total = inf_s + rat_s + tr_s
    return _clamp(total), details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 估值面评分 (15%)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def valuation_detail_score(
    pe: Optional[float] = None,
    pb: Optional[float] = None,
    industry: str = "",
) -> DetailScore:
    """估值面评分。"""
    details: Dict[str, Any] = {"data_available": True}
    is_finance = any(kw in industry for kw in _FINANCE_INDUSTRIES)
    is_high_pe = any(kw in industry for kw in _HIGH_PE_INDUSTRIES)

    # PE（满分50）
    if pe is not None and pe > 0:
        if is_finance:
            if pe <= 8:      pe_s = 50
            elif pe <= 15:   pe_s = 45
            elif pe <= 25:   pe_s = 32
            else:            pe_s = 18
        elif is_high_pe:
            if pe <= 25:     pe_s = 50
            elif pe <= 40:   pe_s = 42
            elif pe <= 70:   pe_s = 28
            else:            pe_s = 12
        else:
            if pe <= 15:     pe_s = 50
            elif pe <= 25:   pe_s = 42
            elif pe <= 40:   pe_s = 32
            elif pe <= 70:   pe_s = 18
            else:            pe_s = 8
    elif pe is not None and pe <= 0:
        pe_s = 20
    else:
        pe_s = 25
    details["pe"] = {"value": pe, "score": pe_s, "max": 50, "industry_adj": "finance" if is_finance else ("high_pe" if is_high_pe else "normal")}

    # PB（满分50）
    if pb is not None and pb > 0:
        if pb <= 1:      pb_s = 50
        elif pb <= 2:    pb_s = 42
        elif pb <= 4:    pb_s = 32
        elif pb <= 8:    pb_s = 18
        else:            pb_s = 8
    elif pb is not None and pb <= 0:
        pb_s = 20
    else:
        pb_s = 25
    details["pb"] = {"value": pb, "score": pb_s, "max": 50}

    total = pe_s + pb_s
    return _clamp(total), details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 综合评分
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEFAULT_WEIGHTS = {
    "fundamental": 0.30,
    "technical":   0.25,
    "fund_flow":   0.20,
    "valuation":   0.15,
    "size":        0.10,
}

# Stage-1 初筛权重（简化，无 size 维度）
SCREEN_WEIGHTS = {
    "fundamental": 0.35,
    "technical":   0.30,
    "fund_flow":   0.20,
    "valuation":   0.15,
}


def composite_score(
    dim_scores: Dict[str, DetailScore],
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, Dict[str, Any]]:
    """综合评分。对数据不可用的维度自动重分配权重。"""
    w = weights or DEFAULT_WEIGHTS
    available: Dict[str, float] = {}
    all_details: Dict[str, Any] = {}

    for dim, weight in w.items():
        if dim in dim_scores:
            score, details = dim_scores[dim]
            all_details[dim] = {"score": round(score, 2), "weight": weight, "details": details}
            if details.get("data_available", True):
                available[dim] = weight

    total_w = sum(available.values())
    if total_w == 0:
        return 50.0, all_details

    comp = 0.0
    for dim, weight in available.items():
        s = dim_scores[dim][0]
        normalized_w = weight / total_w
        contribution = s * normalized_w
        all_details[dim]["normalized_weight"] = round(normalized_w, 4)
        all_details[dim]["contribution"] = round(contribution, 2)
        comp += contribution

    comp = round(_clamp(comp), 2)
    return comp, all_details


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 兼容旧接口（picker.py stage-1 用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def trend_score(closes: List[float]) -> float:
    """兼容旧接口：趋势因子。closes 按时间倒序。"""
    if len(closes) < 5:
        return 50.0
    n20 = min(len(closes), 20)
    ma5 = sum(closes[:5]) / 5
    ma20 = sum(closes[:n20]) / n20
    current = closes[0]
    if current > ma5 > ma20:
        base = 75.0
    elif current > ma5:
        base = 60.0
    elif current < ma5 < ma20:
        base = 25.0
    else:
        base = 45.0
    if len(closes) >= 6:
        ret5 = (closes[0] - closes[5]) / closes[5] if closes[5] > 0 else 0
        momentum = max(-15.0, min(15.0, ret5 * 200))
        base = base + momentum
    if ma20 > 0 and abs(ma5 - ma20) / ma20 < 0.005:
        base -= 5.0
    return max(0.0, min(100.0, base))


def valuation_score(
    pe: Optional[float] = None,
    pb: Optional[float] = None,
    ps: Optional[float] = None,
    roe: Optional[float] = None,
    gross_margin: Optional[float] = None,
    debt_ratio: Optional[float] = None,
    revenue_growth: Optional[float] = None,
    profit_growth: Optional[float] = None,
) -> float:
    """兼容旧接口：综合基本面+估值评分。"""
    s1, _ = fundamental_score(roe=roe, revenue_growth=revenue_growth,
                              profit_growth=profit_growth, gross_margin=gross_margin,
                              debt_ratio=debt_ratio)
    s2, _ = valuation_detail_score(pe=pe, pb=pb)
    return round(s1 * 0.6 + s2 * 0.4, 2)


def composite_score_simple(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """兼容旧接口：简单加权平均。scores/weights 都是 {dim: float}。"""
    total_w = 0.0
    acc = 0.0
    for dim, w in weights.items():
        if dim in scores and scores[dim] is not None:
            acc += scores[dim] * w
            total_w += w
    if total_w == 0:
        return 50.0
    return acc / total_w


def fund_flow_score(main_net_inflow: Optional[float]) -> float:
    """兼容旧接口：资金流因子。"""
    if not main_net_inflow:
        return 50.0
    scale = 1e8
    delta = max(-40.0, min(40.0, (main_net_inflow / scale) * 40.0))
    return max(0.0, min(100.0, 50.0 + delta))


def volume_score(volumes: List[float]) -> float:
    """兼容旧接口：量能因子。volumes 按时间倒序。"""
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
