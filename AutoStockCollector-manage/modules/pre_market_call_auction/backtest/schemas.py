"""回测数据模型。"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class BacktestConfig(BaseModel):
    start_date: str
    end_date: str
    exit_strategy: str = "close"  # close(当日收盘) | next_open(次日开盘) | eod_1450(14:50价)
    top_n: int = 30
    min_score: int = 0
    weight_overrides: Dict[str, float] = {}  # 可选：覆盖默认因子权重


class BacktestTrade(BaseModel):
    date: str
    code: str
    name: str = ""
    strength_score: int = 0
    gap_pct: float = 0.0
    open_price: float = 0.0
    exit_price: float = 0.0
    return_pct: float = 0.0
    strength_detail: Dict[str, Any] = {}
    trap_warning: Optional[Dict[str, Any]] = None


class BacktestResult(BaseModel):
    trades: List[Dict[str, Any]] = []
    config: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    days_scanned: int = 0
