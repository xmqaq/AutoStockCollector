"""盘前竞价雷达 — Pydantic 模型。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class StrengthScore(BaseModel):
    score: int = 0
    # 原 4 维
    gap_score: float = 0.0
    volume_score: float = 0.0
    sector_score: float = 0.0
    deviation_score: float = 0.0
    # 新 4 维
    vol_ratio_score: float = 0.0          # 量比
    order_imbalance_score: float = 0.0    # 委比（近似）
    auction_turnover_score: float = 0.0   # 竞价换手
    amount_percentile_score: float = 0.0  # 竞价金额分位
    # 元数据
    weights: Dict[str, float] = {}        # 实际使用的权重快照
    factors_used: List[str] = []          # 参与计算的因子列表（缺失源不参与）


class TrapWarning(BaseModel):
    is_trap: bool = False
    trap_type: str = ""        # bull_trap | bear_trap
    reason: str = ""
    # 增强：特征明细（供打分/前端展示）
    signals: List[str] = []    # ["极端高开","无量高开","9:20撤单率高",...]
    severity: str = "medium"   # low | medium | high
    cancel_rate: Optional[float] = None  # 撤单率（若有二次采集）


class RadarStock(BaseModel):
    symbol: str
    name: str
    open_price: float = 0.0
    gap_pct: float = 0.0
    auction_amount: float = 0.0
    strength_score: int = 0
    strength_detail: Optional[StrengthScore] = None
    trap_warning: Optional[TrapWarning] = None
    industry: str = ""
    highlight: bool = False
    highlight_reason: str = ""


class RadarResult(BaseModel):
    date: str
    scan_time: str = ""
    status: str = "done"
    total_scanned: int = 0
    top_stocks: List[RadarStock] = []
    sector_leaders: List[Dict[str, str]] = []
    trap_warnings: List[Dict[str, Any]] = []
    summary: str = ""
    created_at: str = ""
