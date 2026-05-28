"""
API数据模型/模式定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskTypeEnum(str, Enum):
    KLINE = "kline"
    STOCK_INFO = "stock_info"
    FINANCIAL = "financial"
    NEWS = "news"
    FUND_FLOW = "fund_flow"
    INCREMENTAL = "incremental"
    BACKFILL = "backfill"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class KlineData(BaseModel):
    code: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    adjust: Optional[str] = "qfq"


class StockInfo(BaseModel):
    code: str
    name: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[str] = None
    total_share: Optional[float] = None
    float_share: Optional[float] = None


class FinancialData(BaseModel):
    code: str
    report_date: str
    total_revenue: Optional[float] = None
    net_profit: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    equity: Optional[float] = None


class NewsItem(BaseModel):
    title: str
    content: Optional[str] = None
    publish_date: str
    source: Optional[str] = None
    url: Optional[str] = None
    code: Optional[str] = None
    news_type: Optional[str] = "general"


class FundFlowData(BaseModel):
    code: str
    date: str
    close: float
    volume: float
    main_net_inflow: Optional[float] = None
    main_net_inflow_ratio: Optional[float] = None


class CreateTaskRequest(BaseModel):
    task_type: TaskTypeEnum
    params: Dict[str, Any] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    strategy: str
    codes: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    initial_cash: float = 1000000
    commission: float = 0.001
    slippage: float = 0.001


class WatchlistRequest(BaseModel):
    user_id: str = "default"
    code: str
    group_id: str = "default"
    priority: int = 0


class AIAnalysisRequest(BaseModel):
    code: str
    type: str = "comprehensive"
    strategies: Optional[List[str]] = None


class ValidationRequest(BaseModel):
    codes: List[str] = Field(default_factory=list)
    data_type: str = "kline"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    status: TaskStatusEnum
    progress: int = 0
    total: int = 0
    success: int = 0
    failed: int = 0
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class KlineResponse(BaseModel):
    code: str
    name: Optional[str] = None
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    change_pct: Optional[float] = None


class BacktestReport(BaseModel):
    strategy: str
    start_date: str
    end_date: str
    initial_cash: float
    final_value: float
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int


class AIAnalysisResult(BaseModel):
    code: str
    analysis_type: str
    score: float
    recommendation: str
    reasons: List[str]
    risk_factors: List[str] = Field(default_factory=list)
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)