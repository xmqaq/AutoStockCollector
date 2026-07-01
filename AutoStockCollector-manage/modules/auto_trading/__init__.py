"""auto_trading — 融合竞价/PA/AI 三路信号的统一自动交易模块。

对外导出：
- UnifiedAutoTrader：编排器（cron 与 API 共用）
- auto_trade_bp：Flask blueprint（在 api/routes/__init__.py 注册）
"""
from .executor import UnifiedAutoTrader
from .api import auto_trade_bp

__all__ = ["UnifiedAutoTrader", "auto_trade_bp"]
