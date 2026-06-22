"""Pydantic 模型 — 请求/响应。"""
import re
from typing import Any, Dict, List, Optional, Annotated
from pydantic import BaseModel, Field, field_validator

VALID_TIMEFRAMES = {"daily", "weekly", "monthly", "5m", "15m", "30m", "60m"}

SYMBOL_RE = re.compile(r"^\d{6}$")


class PriceActionRequest(BaseModel):
    symbols: List[str] = Field(..., description="股票代码列表（6位数字）")
    timeframe: str = Field(default="daily", description="K 线周期")
    account_risk: float = Field(default=0.02, ge=0.01, le=0.1, description="单笔风险比例")
    account_balance: float = Field(default=100000, ge=10000, description="账户总资金")

    @field_validator("symbols")
    @classmethod
    def check_symbols(cls, v: List[str]) -> List[str]:
        for s in v:
            if not SYMBOL_RE.match(s) and not re.match(r"^(SH|SZ|BJ)\d{6}$", s):
                raise ValueError(f"无效股票代码: {s}")
            if len(v) > 50:
                raise ValueError("单次最多分析 50 只股票")
        return v

    @field_validator("timeframe")
    @classmethod
    def check_timeframe(cls, v: str) -> str:
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"无效 timeframe: {v}，可选: {', '.join(sorted(VALID_TIMEFRAMES))}")
        return v


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
