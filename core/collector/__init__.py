"""
数据采集模块初始化
"""
from .base import BaseCollector
from .kline_collector import KlineCollector
from .stock_info_collector import StockInfoCollector
from .financial_collector import FinancialCollector
from .news_collector import NewsCollector
from .fund_flow_collector import FundFlowCollector
from .block_collector import BlockCollector
from .index_collector import IndexCollector

__all__ = [
    "BaseCollector",
    "KlineCollector",
    "StockInfoCollector",
    "FinancialCollector",
    "NewsCollector",
    "FundFlowCollector",
    "BlockCollector",
    "IndexCollector",
]