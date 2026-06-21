"""Pydantic 模型 — 请求/响应。"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PriceActionRequest(BaseModel):
    symbols: List[str] = Field(..., description="股票代码列表")
    timeframe: str = Field(default="daily", description="K 线周期: daily/weekly/30m/5m")
    account_risk: float = Field(default=0.02, ge=0.01, le=0.1, description="单笔风险比例")
    account_balance: float = Field(default=100000, ge=10000, description="账户总资金")


class ZoneInfo(BaseModel):
    type: str
    price_min: float
    price_max: float
    strength: Optional[int] = None
    tested: Optional[bool] = None


class TradePlan(BaseModel):
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    position_size: int
    position_value: float
    risk_per_share: float
    total_risk: float
    r_r_ratio: str


class StockSignal(BaseModel):
    symbol: str
    name: Optional[str] = ""
    current_price: float = 0
    signal: str = "NO_TRADE"
    confidence: int = 0
    trend: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    zones: List[Dict[str, Any]] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    fib_levels: Optional[Dict[str, float]] = None
    atr: float = 0
    sweeps_detected: int = 0
    trade_plan: Optional[TradePlan] = None
    error: Optional[str] = None
