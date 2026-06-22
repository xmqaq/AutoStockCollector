"""盘前竞价雷达 — Pydantic 模型。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuctionSnapshot(BaseModel):
    """单只股票的竞价时刻快照（9:25）。"""
    code: str
    name: str
    date: str
    open_price: float = 0.0
    pre_close: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    gap_pct: float = 0.0
    collected_at: str = ""


class StrengthScore(BaseModel):
    score: int = 0
    gap_score: float = 0.0
    volume_score: float = 0.0
    sector_score: float = 0.0
    deviation_score: float = 0.0


class TrapWarning(BaseModel):
    is_trap: bool = False
    trap_type: str = ""
    reason: str = ""


class RadarStock(BaseModel):
    symbol: str
    name: str
    open_price: float = 0.0
    gap_pct: float = 0.0
    auction_amount: float = 0.0
    strength_score: int = 0
    strength_detail: Optional[StrengthScore] = None
    trap_warning: Optional[TrapWarning] = None
    sector_rank: int = 0
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
