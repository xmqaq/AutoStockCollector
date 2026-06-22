"""开盘强度打分模型 (0-100)。"""
import bisect
from typing import Any, Dict, List, Optional

from .config import AuctionConfig
from .schemas import StrengthScore


def compute_strength(
    snapshot: Dict[str, Any],
    sorted_amounts_desc: List[float],
    neg_sorted_amounts_desc: List[float],
    industry_map: Dict[str, str],
    sector_gap_map: Optional[Dict[str, float]] = None,
) -> StrengthScore:
    """计算单只股票的开盘强度。

    参数:
        sorted_amounts_desc: 全市场竞价金额降序列表
        neg_sorted_amounts_desc: 负值升序列表，用于 bisect O(log N) 百分位查找
    """
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    code = snapshot.get("code", "")
    industry = industry_map.get(code, "")

    gap_score = _score_gap(gap_pct)
    vol_rank_pct = _rank_percentile(amount, neg_sorted_amounts_desc)
    volume_score = vol_rank_pct * 100
    sector_score = _score_sector_resonance(gap_pct, industry, sector_gap_map)
    deviation_score = _score_deviation(gap_pct)

    total = (
        gap_score * AuctionConfig.STRENGTH_WEIGHT_GAP
        + volume_score * AuctionConfig.STRENGTH_WEIGHT_VOLUME
        + sector_score * AuctionConfig.STRENGTH_WEIGHT_SECTOR
        + deviation_score * AuctionConfig.STRENGTH_WEIGHT_DEVIATION
    )

    return StrengthScore(
        score=min(100, max(0, int(round(total)))),
        gap_score=round(gap_score, 1),
        volume_score=round(volume_score, 1),
        sector_score=round(sector_score, 1),
        deviation_score=round(deviation_score, 1),
    )


def _score_gap(gap_pct: float) -> float:
    """基础分: 跳空幅度 0~6% 线性映射到 0~100。"""
    if gap_pct <= 0:
        return 0.0
    return min(100.0, gap_pct / 6.0 * 100.0)


def _rank_percentile(value: float, neg_sorted_desc: List[float]) -> float:
    """计算 value 在降序列表中的百分位 (0~1)。

    使用 bisect O(log N) 在负值升序列表中查找。
    """
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


def _score_deviation(gap_pct: float) -> float:
    """乖离分: 3~5% 最理想。使用分段线性插值消除不连续。"""
    abs_gap = abs(gap_pct)
    if abs_gap >= 8.0:
        return max(0.0, 60.0 - (abs_gap - 8.0) * 10.0)
    if abs_gap >= 5.0:
        return 60.0 + (8.0 - abs_gap) / 3.0 * 40.0
    if abs_gap >= 3.0:
        return 100.0
    if abs_gap >= 1.0:
        return 70.0 + (abs_gap - 1.0) / 2.0 * 30.0
    if abs_gap >= 0.5:
        return 40.0 + (abs_gap - 0.5) / 0.5 * 30.0
    return abs_gap / 0.5 * 40.0
