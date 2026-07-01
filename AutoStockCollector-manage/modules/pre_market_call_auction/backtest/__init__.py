"""回测引擎子包 — 历史竞价快照回放 + 绩效指标 + 参数寻优。

对外导出 AuctionBacktestReplayer / compute_metrics / ParameterOptimizer。
"""
from .replayer import AuctionBacktestReplayer
from .metrics import compute_metrics
from .optimizer import ParameterOptimizer

__all__ = ["AuctionBacktestReplayer", "compute_metrics", "ParameterOptimizer"]
