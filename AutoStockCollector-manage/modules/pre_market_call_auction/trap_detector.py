"""诱多/诱空识别 — 纯 9:25 竞价快照分析，不依赖盘中价格。"""
from typing import Any, Dict, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import TrapWarning

logger = get_logger(__name__)


def detect_trap(
    snapshot: Dict[str, Any],
    sorted_amounts: list,
    thresholds: Optional[Dict[str, float]] = None,
) -> TrapWarning:
    """识别单只股票的诱多/诱空信号。

    参数:
        snapshot: 单个股票的快照
        sorted_amounts: 全市场竞价金额降序列表（由调用者预排序）
        thresholds: 预计算的分位阈值（median/bottom20_pct/top20_pct/vol_min_threshold）
    """
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    pre_close = snapshot.get("pre_close", 0.0)

    if pre_close <= 0:
        return TrapWarning()

    n = len(sorted_amounts)
    if not thresholds or n == 0:
        return TrapWarning()

    # ---- 诱多 ----
    if gap_pct > 8.0:
        return TrapWarning(
            is_trap=True,
            trap_type="bull_trap",
            reason=f"极端高开{gap_pct:.1f}%，大概率回补缺口",
        )

    # 高开 > 5% 且金额低于市场中位数 → 无量高开
    if gap_pct > 5.0 and amount < thresholds["median"]:
        return TrapWarning(
            is_trap=True,
            trap_type="bull_trap",
            reason=f"高开{gap_pct:.1f}%但竞价金额仅{_fmt_amount(amount)}，低于市场中位值",
        )

    # 高开 > 3% 且金额位于末尾 20%
    if gap_pct > 3.0 and amount <= thresholds["bottom20_pct"]:
        return TrapWarning(
            is_trap=True,
            trap_type="bull_trap",
            reason=f"高开{gap_pct:.1f}%但竞价金额仅{_fmt_amount(amount)}，位于末尾20%",
        )

    # 通用：高开超过 TRAP_FALLBACK 且量低于阈值分位
    if gap_pct > AuctionConfig.TRAP_FALLBACK_THRESHOLD * 100 and amount < thresholds["vol_min_threshold"]:
        return TrapWarning(
            is_trap=True,
            trap_type="bull_trap",
            reason=f"高开{gap_pct:.1f}%但量不足（低于{AuctionConfig.TRAP_VOLUME_RATIO_MIN:.0%}分位）",
        )

    # ---- 诱空 ----
    # 低开 < -3% 且金额位于顶部 20%
    if gap_pct < -3.0 and n > 100 and amount >= thresholds["top20_pct"]:
        return TrapWarning(
            is_trap=True,
            trap_type="bear_trap",
            reason=f"低开{gap_pct:.1f}%但竞价金额{_fmt_amount(amount)}位于顶部20%，有大资金承接",
        )

    # 极端低开 < -8% → 即使量小也可能是恐慌过度
    if gap_pct < -8.0 and n > 100 and amount >= thresholds["median"]:
        return TrapWarning(
            is_trap=True,
            trap_type="bear_trap",
            reason=f"极端低开{gap_pct:.1f}%但竞价量高于中位值，疑似恐慌诱空",
        )

    return TrapWarning()


def _fmt_amount(v: float) -> str:
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.0f}"
