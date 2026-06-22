"""开盘强度打分模型 (0-100)。

打分公式（可调参）：
  基础分 (40%) → 跳空幅度 Gap %
  量能分 (30%) → 竞价成交额排名百分位
  共振分 (20%) → 个股 vs 板块涨幅对比
  乖离分 (10%) → 竞价价格相对昨收的适中度
"""
from typing import Any, Dict, List, Optional

from .config import AuctionConfig
from .schemas import StrengthScore

_W = AuctionConfig


def compute_strength(
    snapshot: Dict[str, Any],
    all_amounts: List[float],
    sector_gap_map: Optional[Dict[str, float]] = None,
) -> StrengthScore:
    """计算单只股票的开盘强度。"""
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    code = snapshot.get("code", "")
    industry = _get_industry(code)

    # 基础分 (40%) — 跳空幅度，正贡献加分，负贡献低分
    gap_score = _score_gap(gap_pct)

    # 量能分 (30%) — 竞价成交额全市场排名
    vol_rank_pct = _rank_percentile(amount, all_amounts)
    volume_score = vol_rank_pct * 100

    # 共振分 (20%) — 个股 vs 板块
    sector_score = _score_sector_resonance(gap_pct, industry, sector_gap_map)

    # 乖离分 (10%) — 极端高开扣分
    deviation_score = _score_deviation(gap_pct)

    total = (
        gap_score * _W.STRENGTH_WEIGHT_GAP
        + volume_score * _W.STRENGTH_WEIGHT_VOLUME
        + sector_score * _W.STRENGTH_WEIGHT_SECTOR
        + deviation_score * _W.STRENGTH_WEIGHT_DEVIATION
    )

    return StrengthScore(
        score=min(100, max(0, int(round(total)))),
        gap_score=round(gap_score, 1),
        volume_score=round(volume_score, 1),
        sector_score=round(sector_score, 1),
        deviation_score=round(deviation_score, 1),
    )


def _score_gap(gap_pct: float) -> float:
    """基础分: 跳空幅度 0~6% 线性映射到 0~100，>6% 也满分，负跳空0分。"""
    if gap_pct <= 0:
        return 0.0
    return min(100.0, gap_pct / 6.0 * 100.0)


def _rank_percentile(value: float, all_values: List[float]) -> float:
    """值在全体中的排名百分位 (0~1)。"""
    if not all_values or value <= 0:
        return 0.0
    sorted_vals = sorted(all_values, reverse=True)
    rank = sum(1 for v in sorted_vals if v >= value)
    return rank / len(sorted_vals)


def _score_sector_resonance(
    gap_pct: float,
    industry: str,
    sector_gap_map: Optional[Dict[str, float]],
) -> float:
    """共振分: 个股跳空 > 板块平均跳空 → 高分。"""
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
    """乖离分: 3~5% 最理想（有空间又不极端），越高或越低扣分。"""
    abs_gap = abs(gap_pct)
    if 3.0 <= abs_gap <= 5.0:
        return 100.0
    if 1.0 <= abs_gap < 3.0:
        return 70.0
    if 5.0 < abs_gap <= 8.0:
        return 60.0
    if 0.5 <= abs_gap < 1.0:
        return 40.0
    if abs_gap > 8.0:
        return 20.0
    return 0.0


def _get_industry(code: str) -> str:
    """从 stock_info 查询行业归属。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["stock_info"].find_one({"code": code}, {"所属行业": 1})
        if doc:
            return doc.get("所属行业", "")
    except Exception:
        pass
    return ""


def compute_sector_gaps(snapshots: List[Dict]) -> Dict[str, float]:
    """计算各板块平均跳空幅度。"""
    sector_stocks: Dict[str, List[float]] = {}
    for snap in snapshots:
        industry = _get_industry(snap.get("code", ""))
        if not industry:
            continue
        gap = snap.get("gap_pct", 0.0)
        if industry not in sector_stocks:
            sector_stocks[industry] = []
        sector_stocks[industry].append(gap)

    result = {}
    for ind, gaps in sector_stocks.items():
        if gaps:
            result[ind] = sum(gaps) / len(gaps)
    return result
