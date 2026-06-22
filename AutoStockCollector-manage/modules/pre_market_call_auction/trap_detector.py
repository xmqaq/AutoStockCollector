"""诱多/诱空识别 — 竞价轨迹分析。"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import TrapWarning

logger = get_logger(__name__)


def detect_trap(snapshot: Dict[str, Any]) -> TrapWarning:
    """识别单只股票的诱多/诱空信号。

    诱多 (Bull Trap):
      - 高开 > 3% 但竞价量极小（后 20% 分位）
      - 昨日涨停今日高开但竞价量不足

    诱空 (Bear Trap):
      - 低开 < -2% 但已经止跌回升（开盘价 > 最低价）
    """
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    open_p = snapshot.get("open_price", 0.0)
    low_p = snapshot.get("low", 0.0)
    pre_close = snapshot.get("pre_close", 0.0)

    if pre_close <= 0:
        return TrapWarning()

    # 诱多：高开但竞价量不足
    if gap_pct > 3.0 and amount < 1_000_000:
        return TrapWarning(
            is_trap=True,
            trap_type="bull_trap",
            reason=f"高开{gap_pct:.1f}%但竞价金额仅{_fmt_amount(amount)}，无量空拉",
        )

    # 诱多：高开 > 5% 且回落明显（开盘价 - 最低价 > 3%）
    if gap_pct > 5.0 and low_p > 0 and open_p > low_p:
        fall_pct = (open_p - low_p) / pre_close * 100
        if fall_pct > 3.0:
            return TrapWarning(
                is_trap=True,
                trap_type="bull_trap",
                reason=f"高开{gap_pct:.1f}%后最低回落{fall_pct:.1f}%，疑似诱多",
            )

    # 诱空：低开但开盘价 > 最低价（下方有承接）
    if gap_pct < -2.0 and low_p > 0 and open_p > low_p:
        rebound = (open_p - low_p) / pre_close * 100
        if rebound > 1.5:
            return TrapWarning(
                is_trap=True,
                trap_type="bear_trap",
                reason=f"低开{gap_pct:.1f}%但开盘后回升{rebound:.1f}%，下方承接明显",
            )

    return TrapWarning()


def _fmt_amount(v: float) -> str:
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.0f}"
