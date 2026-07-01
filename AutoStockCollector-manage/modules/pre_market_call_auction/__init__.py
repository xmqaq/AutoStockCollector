"""盘前竞价雷达模块 — 集合竞价扫描、4+维打分、诱骗检测、自动交易信号、盘中追踪、回测。

对外导出：
- auction_bp：Flask blueprint（在 api/routes/__init__.py 注册）
- run_auction_scan / get_status：扫描入口
- TrackingStore / IntradayPricer / RiskDashboard / AuctionSignalEmitter：拆分后的组件
- 向后兼容函数：update_realtime_prices / get_intraday_data / get_risk_summary / auto_close_positions
"""
from .api import auction_bp
from .radar_service import run_auction_scan, get_status
from .tracking_store import TrackingStore
from .intraday_pricer import IntradayPricer, update_realtime_prices, get_intraday_data
from .risk_dashboard import RiskDashboard, get_risk_summary
from .signal_emitter import AuctionSignalEmitter, auto_close_positions, auto_trade_top_stocks

__all__ = [
    "auction_bp", "run_auction_scan", "get_status",
    "TrackingStore", "IntradayPricer", "RiskDashboard", "AuctionSignalEmitter",
    "update_realtime_prices", "get_intraday_data", "get_risk_summary",
    "auto_close_positions", "auto_trade_top_stocks",
]
