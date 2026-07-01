"""诱多/诱空识别 — 9 类规则（原 6 类 + 3 类实战特征）。

原 6 类：极端高开/无量高开/末尾量高开/通用量不足/低开放量/极端低开中量。
新增 3 类：
  7. 9:20 撤单率（二次采集对比，或量比偏离近似）
  8. 竞价量集中度（高开+量比低+金额高 → 量集中前段尾段缩量）
  9. 板块联动诱多（板块诱多率高 + 该股高开）

TrapWarning 扩 signals[]/severity/cancel_rate。detect_trap 编排多个 _check，聚合返回。
"""
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import TrapWarning

logger = get_logger(__name__)


def detect_trap(
    snapshot: Dict[str, Any],
    sorted_amounts: list,
    thresholds: Optional[Dict[str, float]] = None,
    pre_snapshot: Optional[Dict[str, Any]] = None,
    sector_trap_rate: Optional[Dict[str, float]] = None,
) -> TrapWarning:
    """识别单只股票的诱多/诱空信号（9 类规则聚合）。

    参数:
        snapshot: 单个股票的 9:25 快照
        sorted_amounts: 全市场竞价金额降序列表
        thresholds: 预计算分位阈值
        pre_snapshot: 9:20 预筛快照（可选，ENABLE_DUAL_SNAPSHOT 时用于算撤单率）
        sector_trap_rate: {industry: 板块内高开无量股占比}（可选，板块联动用）
    """
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    pre_close = snapshot.get("pre_close", 0.0)

    if pre_close <= 0:
        return TrapWarning()
    n = len(sorted_amounts)
    if not thresholds or n == 0:
        return TrapWarning()

    # 逐规则检测，聚合 signals
    checks = [
        _check_extreme_high_open(snapshot),
        _check_high_open_no_volume(snapshot, thresholds),
        _check_high_open_tail_volume(snapshot, thresholds),
        _check_high_open_insufficient_volume(snapshot, thresholds),
        _check_bear_trap_volume(snapshot, thresholds, n),
        _check_extreme_low_open(snapshot, thresholds, n),
        _check_cancel_rate(snapshot, pre_snapshot),
        _check_volume_concentration(snapshot, thresholds),
        _check_sector_trap(snapshot, sector_trap_rate),
    ]

    signals: List[str] = []
    trap_type = ""
    cancel_rate: Optional[float] = None
    for w in checks:
        if w.is_trap:
            signals.extend(w.signals or [w.reason])
            if not trap_type:
                trap_type = w.trap_type
            if w.cancel_rate is not None:
                cancel_rate = w.cancel_rate

    if not signals:
        return TrapWarning()

    severity = _severity(signals, gap_pct)
    return TrapWarning(
        is_trap=True,
        trap_type=trap_type or ("bull_trap" if gap_pct > 0 else "bear_trap"),
        reason="；".join(signals),
        signals=signals,
        severity=severity,
        cancel_rate=cancel_rate,
    )


def _severity(signals: List[str], gap_pct: float) -> str:
    """聚合严重度：命中数多或极端高开 → high。"""
    if len(signals) >= 3 or abs(gap_pct) >= 8:
        return "high"
    if len(signals) >= 2:
        return "medium"
    return "low"


# ── 规则 1：极端高开 ──
def _check_extreme_high_open(snapshot: Dict) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    if gap_pct > 8.0:
        return TrapWarning(is_trap=True, trap_type="bull_trap", reason=f"极端高开{gap_pct:.1f}%，大概率回补缺口",
                           signals=[f"极端高开{gap_pct:.1f}%"])
    return TrapWarning()


# ── 规则 2：高开 > 5% 且金额低于中位数（无量高开）──
def _check_high_open_no_volume(snapshot: Dict, thresholds: Dict) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct > 5.0 and amount < thresholds["median"]:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"高开{gap_pct:.1f}%但竞价金额仅{_fmt_amount(amount)}，低于市场中位值",
                           signals=["无量高开"])
    return TrapWarning()


# ── 规则 3：高开 > 3% 且金额末尾 20% ──
def _check_high_open_tail_volume(snapshot: Dict, thresholds: Dict) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct > 3.0 and amount <= thresholds["bottom20_pct"]:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"高开{gap_pct:.1f}%但竞价金额仅{_fmt_amount(amount)}，位于末尾20%",
                           signals=["末尾量高开"])
    return TrapWarning()


# ── 规则 4：通用高开量不足 ──
def _check_high_open_insufficient_volume(snapshot: Dict, thresholds: Dict) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct > AuctionConfig.TRAP_FALLBACK_THRESHOLD * 100 and amount < thresholds["vol_min_threshold"]:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"高开{gap_pct:.1f}%但量不足（低于{AuctionConfig.TRAP_VOLUME_RATIO_MIN:.0%}分位）",
                           signals=["量能不足"])
    return TrapWarning()


# ── 规则 5：低开 <-3% 且量顶部 20%（诱空，大资金承接）──
def _check_bear_trap_volume(snapshot: Dict, thresholds: Dict, n: int) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct < -3.0 and n > 100 and amount >= thresholds["top20_pct"]:
        return TrapWarning(is_trap=True, trap_type="bear_trap",
                           reason=f"低开{gap_pct:.1f}%但竞价金额{_fmt_amount(amount)}位于顶部20%，有大资金承接",
                           signals=["低开放量承接"])
    return TrapWarning()


# ── 规则 6：极端低开 <-8% 且量高于中位数 ──
def _check_extreme_low_open(snapshot: Dict, thresholds: Dict, n: int) -> TrapWarning:
    gap_pct = snapshot.get("gap_pct", 0.0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct < -8.0 and n > 100 and amount >= thresholds["median"]:
        return TrapWarning(is_trap=True, trap_type="bear_trap",
                           reason=f"极端低开{gap_pct:.1f}%但竞价量高于中位值，疑似恐慌诱空",
                           signals=["极端低开中量"])
    return TrapWarning()


# ── 规则 7：9:20 撤单率（二次采集对比，或无数据时跳过）──
def _check_cancel_rate(snapshot: Dict, pre_snapshot: Optional[Dict]) -> TrapWarning:
    """9:20 前后快照对比：9:20 量远大于 9:25 → 大量撤单 → 诱多。"""
    if not pre_snapshot:
        return TrapWarning()
    pre_vol = pre_snapshot.get("volume", 0) or 0
    cur_vol = snapshot.get("volume", 0) or 0
    if pre_vol <= 0 or cur_vol <= 0:
        return TrapWarning()
    cancel_rate = 1 - cur_vol / pre_vol
    gap_pct = snapshot.get("gap_pct", 0.0)
    if cancel_rate > AuctionConfig.TRAP_CANCEL_RATE_THRESHOLD and gap_pct > 3:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"9:20后撤单率{cancel_rate:.0%}，竞价量大幅缩水，疑似假单诱多",
                           signals=[f"9:20撤单率{cancel_rate:.0%}"], cancel_rate=cancel_rate)
    return TrapWarning()


# ── 规则 8：竞价量集中度（高开+量比低+金额高 → 量集中前段尾段缩量）──
def _check_volume_concentration(snapshot: Dict, thresholds: Dict) -> TrapWarning:
    """高开但量比低且金额高 → 量集中在开盘前段，尾段缩量 = 诱多。"""
    gap_pct = snapshot.get("gap_pct", 0.0)
    vr = float(snapshot.get("volume_ratio", 0) or 0)
    amount = snapshot.get("amount", 0.0)
    if gap_pct > 5.0 and 0 < vr < 0.8 and amount > thresholds["median"]:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"高开{gap_pct:.1f}%但量比仅{vr:.1f}，竞价量集中前段尾段缩量",
                           signals=["量集中前段"])
    return TrapWarning()


# ── 规则 9：板块联动诱多 ──
def _check_sector_trap(snapshot: Dict, sector_trap_rate: Optional[Dict[str, float]]) -> TrapWarning:
    """该股所属板块的诱多率（高开无量股占比）超阈值且该股高开 → 板块性诱多。"""
    if not sector_trap_rate:
        return TrapWarning()
    industry = snapshot.get("industry", "")
    gap_pct = snapshot.get("gap_pct", 0.0)
    rate = sector_trap_rate.get(industry, 0)
    if rate > AuctionConfig.TRAP_SECTOR_RATE_THRESHOLD and gap_pct > 3:
        return TrapWarning(is_trap=True, trap_type="bull_trap",
                           reason=f"板块{industry}诱多率{rate:.0%}，联动风险",
                           signals=[f"板块联动诱多{rate:.0%}"])
    return TrapWarning()


def compute_sector_trap_rate(snapshots: List[Dict], industry_map: Dict[str, str],
                             thresholds: Dict) -> Dict[str, float]:
    """预计算各板块的诱多率（板块内高开+无量股占比），供规则 9 用。"""
    sector_total: Dict[str, int] = {}
    sector_trap: Dict[str, int] = {}
    for snap in snapshots:
        code = snap.get("code", "")
        industry = industry_map.get(code, "")
        if not industry:
            continue
        gap_pct = snap.get("gap_pct", 0.0)
        amount = snap.get("amount", 0.0)
        sector_total[industry] = sector_total.get(industry, 0) + 1
        if gap_pct > 3.0 and amount < thresholds.get("median", 0):
            sector_trap[industry] = sector_trap.get(industry, 0) + 1
    return {ind: (sector_trap.get(ind, 0) / cnt if cnt > 0 else 0)
            for ind, cnt in sector_total.items()}


def _fmt_amount(v: float) -> str:
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.0f}"
