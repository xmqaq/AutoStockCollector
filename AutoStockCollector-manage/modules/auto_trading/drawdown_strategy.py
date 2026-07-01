"""DrawdownStrategy — 追踪回撤止盈/减仓 + 最大回撤硬止损。

重构要点：
- DrawdownChecker 不再自己调 engine.sell，改为只评估，返回 _DrawdownVerdict，
  交 DecisionEngine 仲裁（消除原 bug 9：与主决策双卖出叠加）。
- PeakTracker / DrawdownStrategyManager 不变（配置与峰值仍持久化到 Mongo）。
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from config.database import DatabaseConfig
from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)

_DRAWDOWN_COLLECTION = "auto_trading_drawdown_config"
_PEAK_COLLECTION = "auto_trading_peak_tracker"


@dataclass
class DrawdownStrategyConfig:
    enabled: bool = False
    trailing_stop_pct: float = 5.0
    trailing_action: str = "sell"      # sell | reduce
    reduce_ratio: float = 0.5
    profit_lock_enabled: bool = True
    profit_lock_threshold: float = 3.0
    max_drawdown_pct: float = 15.0
    updated_at: str = ""


DEFAULTS = DrawdownStrategyConfig()


class PeakTracker:
    """追踪每个持仓自建仓以来的最高价。"""

    def _col(self):
        return DatabaseConfig.get_database()[_PEAK_COLLECTION]

    def get_all(self) -> Dict[str, float]:
        docs = self._col().find({})
        return {d["code"]: d["peak_price"] for d in docs}

    def get(self, code: str) -> Optional[float]:
        doc = self._col().find_one({"code": code})
        return doc["peak_price"] if doc else None

    def update(self, code: str, peak_price: float):
        now = beijing_now().isoformat()
        self._col().update_one(
            {"code": code},
            {"$set": {"peak_price": peak_price, "updated_at": now}},
            upsert=True,
        )

    def remove(self, code: str):
        self._col().delete_one({"code": code})

    def remove_all(self):
        self._col().delete_many({})


class DrawdownStrategyManager:
    """持久化 drawdown 配置（单文档）。"""

    def _col(self):
        return DatabaseConfig.get_database()[_DRAWDOWN_COLLECTION]

    def load(self) -> DrawdownStrategyConfig:
        try:
            doc = self._col().find_one({})
            if doc:
                return DrawdownStrategyConfig(
                    enabled=doc.get("enabled", DEFAULTS.enabled),
                    trailing_stop_pct=doc.get("trailing_stop_pct", DEFAULTS.trailing_stop_pct),
                    trailing_action=doc.get("trailing_action", DEFAULTS.trailing_action),
                    reduce_ratio=doc.get("reduce_ratio", DEFAULTS.reduce_ratio),
                    profit_lock_enabled=doc.get("profit_lock_enabled", DEFAULTS.profit_lock_enabled),
                    profit_lock_threshold=doc.get("profit_lock_threshold", DEFAULTS.profit_lock_threshold),
                    max_drawdown_pct=doc.get("max_drawdown_pct", DEFAULTS.max_drawdown_pct),
                    updated_at=doc.get("updated_at", ""),
                )
        except Exception as e:
            logger.warning(f"[drawdown] Load config failed: {e}")
        return DrawdownStrategyConfig()

    def save(self, cfg: DrawdownStrategyConfig):
        try:
            cfg.updated_at = beijing_now().isoformat()
            self._col().replace_one({}, asdict(cfg), upsert=True)
            logger.info(f"[drawdown] Config saved: trailing={cfg.trailing_stop_pct}% action={cfg.trailing_action}")
        except Exception as e:
            logger.error(f"[drawdown] Save config failed: {e}")
            raise

    def to_dict(self, cfg: DrawdownStrategyConfig) -> Dict:
        return {
            "enabled": cfg.enabled,
            "trailing_stop_pct": cfg.trailing_stop_pct,
            "trailing_action": cfg.trailing_action,
            "reduce_ratio": cfg.reduce_ratio,
            "profit_lock_enabled": cfg.profit_lock_enabled,
            "profit_lock_threshold": cfg.profit_lock_threshold,
            "max_drawdown_pct": cfg.max_drawdown_pct,
            "updated_at": cfg.updated_at,
        }

    def from_dict(self, d: Dict) -> DrawdownStrategyConfig:
        return DrawdownStrategyConfig(
            enabled=d.get("enabled", DEFAULTS.enabled),
            trailing_stop_pct=d.get("trailing_stop_pct", DEFAULTS.trailing_stop_pct),
            trailing_action=d.get("trailing_action", DEFAULTS.trailing_action),
            reduce_ratio=d.get("reduce_ratio", DEFAULTS.reduce_ratio),
            profit_lock_enabled=d.get("profit_lock_enabled", DEFAULTS.profit_lock_enabled),
            profit_lock_threshold=d.get("profit_lock_threshold", DEFAULTS.profit_lock_threshold),
            max_drawdown_pct=d.get("max_drawdown_pct", DEFAULTS.max_drawdown_pct),
        )


@dataclass
class DrawdownVerdict:
    """drawdown 评估结果（不执行）。对应 decision_engine._DrawdownVerdict 的运行时形态。"""
    hit: bool = False
    action: str = ""        # sell | reduce
    shares: int = 0
    reason: str = ""
    priority: int = 0


class DrawdownChecker:
    """评估持仓是否触发回撤规则，返回 DrawdownVerdict（不执行交易）。"""

    def __init__(self):
        self._config_mgr = DrawdownStrategyManager()
        self._peak_tracker = PeakTracker()

    def evaluate_one(self, pos: dict) -> Optional[DrawdownVerdict]:
        """对单个持仓评估。返回 DrawdownVerdict 或 None（未触发）。同时更新 peak。"""
        cfg = self._config_mgr.load()
        if not cfg.enabled:
            return None

        code = pos.get("code", "")
        shares = pos.get("shares", 0)
        current_price = pos.get("current_price", 0)
        avg_cost = pos.get("avg_cost", 0)
        if not code or shares <= 0 or current_price <= 0 or avg_cost <= 0:
            return None

        # 更新峰值
        current_peak = self._peak_tracker.get(code) or 0
        if current_price > current_peak:
            self._peak_tracker.update(code, current_price)
            current_peak = current_price
        if current_peak <= 0:
            return None

        max_dd = (current_peak - current_price) / current_peak * 100
        pnl_pct = (current_price - avg_cost) / avg_cost * 100
        if max_dd <= 0:
            return None

        return self._evaluate(cfg, max_dd, pnl_pct, shares, code)

    def cleanup_closed(self, held_codes):
        """持仓已平仓 → 清理 peak 记录。"""
        try:
            for code, peak in self._peak_tracker.get_all().items():
                if code not in held_codes:
                    self._peak_tracker.remove(code)
        except Exception as e:
            logger.warning(f"[drawdown] cleanup failed: {e}")

    def _evaluate(self, cfg: DrawdownStrategyConfig, max_dd: float, pnl_pct: float,
                  shares: int, code: str) -> Optional[DrawdownVerdict]:
        # 90: 最大回撤硬止损
        if max_dd >= cfg.max_drawdown_pct:
            return DrawdownVerdict(hit=True, action="sell", shares=shares,
                                   reason=f"最大回撤{cfg.max_drawdown_pct}%止损 (当前回撤{max_dd:.1f}%)",
                                   priority=90)

        # 利润锁定未达 → 不触发追踪回撤（避免微利被震出）
        if cfg.profit_lock_enabled and pnl_pct < cfg.profit_lock_threshold:
            return None

        # 70: 追踪回撤
        if max_dd >= cfg.trailing_stop_pct:
            if cfg.trailing_action == "reduce" and shares >= 200:
                reduce_qty = max((int(shares * cfg.reduce_ratio) // 100) * 100, 100)
                return DrawdownVerdict(hit=True, action="reduce", shares=reduce_qty,
                                       reason=f"追踪回撤{cfg.trailing_stop_pct}%减仓 (回撤{max_dd:.1f}%)",
                                       priority=70)
            return DrawdownVerdict(hit=True, action="sell", shares=shares,
                                   reason=f"追踪回撤{cfg.trailing_stop_pct}%止盈 (回撤{max_dd:.1f}%)",
                                   priority=70)
        return None
