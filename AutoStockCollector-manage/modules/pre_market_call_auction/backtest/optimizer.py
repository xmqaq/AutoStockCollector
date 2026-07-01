"""参数寻优 — 网格搜索因子权重，最大化 sharpe × profit_factor。

需要历史数据积累（>30 交易日）才有效。寻优只对 weight_overrides 网格组合。
"""
import itertools
from typing import Any, Dict, List

from utils.logger import get_logger

from .replayer import AuctionBacktestReplayer
from .schemas import BacktestConfig

logger = get_logger(__name__)


class ParameterOptimizer:
    """网格搜索因子权重组合。"""

    def grid_search(self, base_config: BacktestConfig,
                    param_grid: Dict[str, List[float]]) -> Dict[str, Any]:
        """param_grid 例：{"gap": [0.15,0.20,0.25], "vol_ratio": [0.10,0.15,0.20]}
        对每个组合跑一次回测，返回按目标函数排序的结果。"""
        if not param_grid:
            return {"error": "param_grid 为空"}

        keys = list(param_grid.keys())
        combos = list(itertools.product(*[param_grid[k] for k in keys]))
        replayer = AuctionBacktestReplayer()
        results: List[Dict[str, Any]] = []

        for combo in combos:
            overrides = dict(zip(keys, combo))
            # 校验权重和≈1.0（容差 0.05）
            if abs(sum(overrides.values()) - 1.0) > 0.05:
                continue
            cfg = base_config.model_copy(update={"weight_overrides": overrides})
            try:
                bt = replayer.run(cfg)
                overall = bt.metrics.get("overall", {})
                sharpe = overall.get("sharpe", 0) or 0
                pf = overall.get("profit_factor", 0) or 0
                # profit_factor 可能是 inf
                pf = min(pf, 99.0) if pf != float("inf") else 99.0
                objective = sharpe * pf if pf != 0 else 0
                results.append({
                    "params": overrides,
                    "sharpe": sharpe, "win_rate": overall.get("win_rate", 0),
                    "profit_factor": pf, "total_trades": overall.get("total_trades", 0),
                    "objective": round(objective, 4),
                })
            except Exception as e:
                logger.warning(f"[Optimizer] combo {overrides} failed: {e}")

        results.sort(key=lambda x: -x["objective"])
        return {"best": results[0] if results else None, "all": results, "combos_tried": len(combos)}
