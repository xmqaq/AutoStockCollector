"""权重优化器。基于 FusionBacktest 回测信号，平滑更新 fusion_weight_config 中的各市场状态权重。

平滑混合（new = old*0.7 + suggested*0.3）避免单次大幅跳变，渐进收敛。
样本不足（reliable=False）时跳过。
"""
from typing import Any, Dict

from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)

_DIMS = ("fundamental", "technical", "fund_flow", "valuation")
_STATES = ("bull", "bear", "volatile")
_COLLECTION = "fusion_weight_config"


class WeightOptimizer:
    def __init__(self, backtest=None):
        self._backtest = backtest  # 注入便于测试

    def _bt(self):
        if self._backtest is None:
            from modules.ai.fusion.backtest import FusionBacktest
            self._backtest = FusionBacktest()
        return self._backtest

    def get_current_weights(self, state: str) -> Dict[str, float]:
        from modules.ai.fusion.market_state import MarketStateDetector
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            doc = db[_COLLECTION].find_one({"state": state})
            if doc and doc.get("weights"):
                w = doc["weights"]
                if all(k in w for k in _DIMS):
                    return {k: float(w[k]) for k in _DIMS}
        except Exception:
            pass
        return dict(MarketStateDetector.WEIGHT_PRESETS[state])

    def run(self) -> Dict[str, Any]:
        signals = self._bt().get_optimization_signals()
        if not signals.get("reliable"):
            return {"skipped": True, "reason": "样本不足"}

        suggested_all = signals.get("suggested_weights", {})
        sample_counts = signals.get("sample_counts", {})

        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()

        states_updated = []
        changes: Dict[str, Dict[str, Dict[str, float]]] = {}
        now = beijing_now()

        for state in _STATES:
            suggested = suggested_all.get(state)
            if not suggested:
                continue
            old = self.get_current_weights(state)
            new = {d: round(old.get(d, 0.0) * 0.7 + float(suggested.get(d, 0.0)) * 0.3, 4)
                   for d in _DIMS}
            try:
                db[_COLLECTION].update_one(
                    {"state": state},
                    {"$set": {
                        "state": state,
                        "weights": new,
                        "updated_at": now,
                        "sample_count": int(sample_counts.get(state, 0)),
                        "old_weights": old,
                        "suggested_weights": suggested,
                    }},
                    upsert=True,
                )
                states_updated.append(state)
                changes[state] = {"before": old, "after": new}
            except Exception as e:
                logger.warning(f"[fusion] 权重写入失败 state={state}: {e}")

        return {
            "updated": bool(states_updated),
            "states_updated": states_updated,
            "changes": changes,
        }
