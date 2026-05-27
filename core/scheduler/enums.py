"""
任务状态和类型枚举定义
"""
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskType(Enum):
    KLINE_COLLECTION = "kline"
    STOCK_INFO_COLLECTION = "stock_info"
    FINANCIAL_COLLECTION = "financial"
    NEWS_COLLECTION = "news"
    FUND_FLOW_COLLECTION = "fund_flow"
    INCREMENTAL_COLLECTION = "incremental"
    BACKFILL_COLLECTION = "backfill"
    INDEX_COLLECTION = "index"
    DRAGON_TIGER_COLLECTION = "dragon_tiger"
    SECTOR_COLLECTION = "sector"
