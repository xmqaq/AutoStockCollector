"""开盘强度打分模型 (0-100) — 8 维因子体系。

4 维 → 8 维：跳空/量能/板块/乖离 + 量比/委比/竞价换手/金额分位。
负跳空修复（bug 3）：原 _score_gap 对负跳空返回 0，与 bear_trap 诱空检测矛盾。
现负跳空按"低开+量大（大资金承接）"给 40-60 分，使诱空识别与打分一致。

权重和=1.0，全 AUCTION_WEIGHT_* env 可配。缺失数据源的因子不参与分母（与 signal_fusion 一致）。
"""
import bisect
from typing import Any, Dict, List, Optional, Tuple

from .config import AuctionConfig
from .schemas import StrengthScore


def compute_strength(
    snapshot: Dict[str, Any],
    sorted_amounts_desc: List[float],
    neg_sorted_amounts_desc: List[float],
    industry_map: Dict[str, str],
    sector_gap_map: Optional[Dict[str, float]] = None,
    sorted_turnover_desc: Optional[List[float]] = None,
) -> StrengthScore:
    """计算单只股票的开盘强度（8 维）。

    参数:
        sorted_amounts_desc: 全市场竞价金额降序列表
        neg_sorted_amounts_desc: 负值升序列表，用于 bisect O(log N) 百分位查找
        sorted_turnover_desc: 全市场竞价换手降序列表（可选，缺失则换手因子降级）
    """
    gap_pct = snapshot.get("gap_pct", 0.0) or 0.0
    amount = snapshot.get("amount", 0.0) or 0.0
    code = snapshot.get("code", "")
    industry = industry_map.get(code, "")

    # ── 8 维分值 ──
    gap_score = _score_gap(gap_pct, amount, neg_sorted_amounts_desc)
    vol_rank_pct = _rank_percentile(amount, neg_sorted_amounts_desc)
    volume_score = vol_rank_pct * 100
    sector_score = _score_sector_resonance(gap_pct, industry, sector_gap_map)
    deviation_score = _score_deviation(gap_pct, amount, neg_sorted_amounts_desc)
    vol_ratio_score = _score_vol_ratio(snapshot)
    order_imbalance_score = _score_order_imbalance(snapshot)
    auction_turnover_score = _score_auction_turnover(snapshot, sorted_turnover_desc)
    amount_percentile_score = volume_score  # 金额分位与量能同源（clist f6），独立成因子但值相同

    # ── 权重 & 加权（缺失因子不参与分母）──
    factors: List[Tuple[str, float, float]] = [
        ("gap", AuctionConfig.STRENGTH_WEIGHT_GAP, gap_score),
        ("volume", AuctionConfig.STRENGTH_WEIGHT_VOLUME, volume_score),
        ("sector", AuctionConfig.STRENGTH_WEIGHT_SECTOR, sector_score),
        ("deviation", AuctionConfig.STRENGTH_WEIGHT_DEVIATION, deviation_score),
        ("vol_ratio", AuctionConfig.STRENGTH_WEIGHT_VOL_RATIO, vol_ratio_score),
        ("order_imbalance", AuctionConfig.STRENGTH_WEIGHT_ORDER_IMBALANCE, order_imbalance_score),
        ("auction_turnover", AuctionConfig.STRENGTH_WEIGHT_AUCTION_TURNOVER, auction_turnover_score),
        ("amount_percentile", AuctionConfig.STRENGTH_WEIGHT_AMOUNT_PCTILE, amount_percentile_score),
    ]

    weights_snapshot: Dict[str, float] = {}
    factors_used: List[str] = []
    numerator = 0.0
    denom = 0.0
    for name, weight, score in factors:
        if score is None:
            continue
        weights_snapshot[name] = weight
        factors_used.append(name)
        numerator += weight * score
        denom += weight

    total = (numerator / denom * 100) if denom > 0 else 50.0
    total = min(100, max(0, total))

    return StrengthScore(
        score=int(round(total)),
        gap_score=round(gap_score, 1),
        volume_score=round(volume_score, 1),
        sector_score=round(sector_score, 1),
        deviation_score=round(deviation_score, 1),
        vol_ratio_score=round(vol_ratio_score, 1),
        order_imbalance_score=round(order_imbalance_score, 1),
        auction_turnover_score=round(auction_turnover_score, 1),
        amount_percentile_score=round(amount_percentile_score, 1),
        weights=weights_snapshot,
        factors_used=factors_used,
    )


def _has_volume_support(amount: float, neg_sorted_desc: List[float]) -> bool:
    """判断是否有量能支撑（金额位于市场上半区）。

    _rank_percentile 返回"严格大于 amount 的占比"，pct 小 = amount 大。
    pct <= 0.5 表示 amount 在上半区（含中位以上）。
    """
    pct = _rank_percentile(amount, neg_sorted_desc)
    return pct <= 0.5  # 上半区即承接有力


def _score_gap(gap_pct: float, amount: float = 0, neg_sorted_desc: Optional[List[float]] = None) -> float:
    """跳空分。正跳空 0-6% 线性映射 0-100；负跳空修复（bug3）：大资金承接给分。

    负跳空修复：原对 gap<=0 返回 0，与 bear_trap 诱空检测矛盾。现低开+量大给 40-60 分。
    """
    if gap_pct > 0:
        return min(100.0, gap_pct / 6.0 * 100.0)
    # 负跳空：判断是否有大资金承接
    has_volume = False
    if neg_sorted_desc is not None and amount > 0:
        has_volume = _has_volume_support(amount, neg_sorted_desc)
    if gap_pct == 0:
        return 40.0  # 平开
    if gap_pct < -8.0:
        return 40.0 if has_volume else 0.0  # 极端低开+承接=疑似诱空反转
    if gap_pct < -3.0:
        return 60.0 if has_volume else 10.0  # 低开+承接强
    return 30.0  # -3% ~ 0% 小幅低开


def _rank_percentile(value: float, neg_sorted_desc: List[float]) -> float:
    """计算 value 在降序列表中的百分位 (0~1)。bisect O(log N)。"""
    if not neg_sorted_desc or value <= 0:
        return 0.0
    idx = bisect.bisect_left(neg_sorted_desc, -value)
    return idx / len(neg_sorted_desc)


def _score_sector_resonance(
    gap_pct: float,
    industry: str,
    sector_gap_map: Optional[Dict[str, float]],
) -> float:
    if not sector_gap_map or not industry:
        return 50.0
    sector_avg_gap = sector_gap_map.get(industry, 0.0)
    if sector_avg_gap <= 0:
        return 50.0
    ratio = gap_pct / sector_avg_gap if sector_avg_gap > 0 else 1.0
    if ratio >= 1.5:
        return 100.0
    if ratio >= 1.0:
        return 80.0
    if ratio >= 0.8:
        return 60.0
    return 30.0


def _score_deviation(gap_pct: float, amount: float = 0,
                     neg_sorted_desc: Optional[List[float]] = None) -> float:
    """乖离分: 正跳空 3~5% 最理想；负跳空若大资金承接给 40 分基础（与 _score_gap 一致）。"""
    if gap_pct > 0:
        if gap_pct >= 8.0:
            return max(0.0, 60.0 - (gap_pct - 8.0) * 10.0)
        if gap_pct >= 5.0:
            return 60.0 + (8.0 - gap_pct) / 3.0 * 40.0
        if gap_pct >= 3.0:
            return 100.0
        if gap_pct >= 1.0:
            return 70.0 + (gap_pct - 1.0) / 2.0 * 30.0
        if gap_pct >= 0.5:
            return 40.0 + (gap_pct - 0.5) / 0.5 * 30.0
        return gap_pct / 0.5 * 40.0
    # 负跳空：大资金承接给基础分
    has_volume = False
    if neg_sorted_desc is not None and amount > 0:
        has_volume = _has_volume_support(amount, neg_sorted_desc)
    if gap_pct == 0:
        return 40.0
    return 40.0 if has_volume else 10.0


def _score_vol_ratio(snapshot: Dict[str, Any]) -> float:
    """量比（竞价量/昨日总量）。clist f10 直接取，>1 活跃。无数据给中位 30。"""
    vr = float(snapshot.get("volume_ratio", 0) or 0)
    if vr <= 0:
        return 30.0  # 无数据降级
    if vr >= 3.0:
        return 100.0
    if vr >= 2.0:
        return 90.0
    if vr >= 1.5:
        return 80.0
    if vr >= 1.0:
        return 65.0
    if vr >= 0.5:
        return 40.0
    return 20.0


def _score_order_imbalance(snapshot: Dict[str, Any]) -> float:
    """委比近似：无直接委比字段，用 amount/volume 偏离 open_price 近似。
    高价成交（avg>open）= 主动买盘偏强，低价成交 = 主动卖盘。映射到 0-100。"""
    amount = float(snapshot.get("amount", 0) or 0)
    volume = float(snapshot.get("volume", 0) or 0)
    open_price = float(snapshot.get("open_price", 0) or 0)
    if volume <= 0 or open_price <= 0:
        return 50.0  # 无数据中性
    avg_price = amount / volume
    ratio = avg_price / open_price  # >1 主动买，<1 主动卖
    return min(100.0, max(0.0, 50.0 + (ratio - 1.0) * 500.0))


def _score_auction_turnover(snapshot: Dict[str, Any],
                            sorted_turnover_desc: Optional[List[float]] = None) -> float:
    """竞价换手率百分位。新股适当加权。无数据给 30。"""
    turnover = float(snapshot.get("turnover", 0) or 0)
    if turnover <= 0:
        return 30.0
    if not sorted_turnover_desc:
        # 无全市场排序数据，用绝对值分档（换手% 0-5 线性映射 0-100）
        score = min(100.0, turnover / 5.0 * 100.0)
    else:
        # 构造负值升序列表用于 bisect
        neg = [-x for x in sorted_turnover_desc]
        pct = _rank_percentile(turnover, neg)
        score = pct * 100
    if snapshot.get("is_new_ipo"):
        score = min(100.0, score * 1.2)  # 新股加权
    return score
