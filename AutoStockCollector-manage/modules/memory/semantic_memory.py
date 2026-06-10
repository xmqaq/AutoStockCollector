"""长期知识库 - 自动挖掘用户投资规律"""
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Dict, List, Optional
from collections import Counter, defaultdict
from config.database import DatabaseConfig
from modules.memory.models import InvestmentPattern, HoldingRecord, MemoryConfig


class SemanticMemory:
    """长期知识库：自动挖掘用户投资模式，存于 MongoDB"""

    COLLECTION_PATTERNS = "memory_patterns"

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = DatabaseConfig.get_database()
        return self._db

    # ==================== 模式分析 ====================

    def analyze_patterns(self, user_id: str) -> List[InvestmentPattern]:
        trades = self._get_user_trades(user_id)
        if not trades:
            return []

        patterns = []

        sector_analysis = self._analyze_sector_winrates(trades)
        patterns.extend(sector_analysis)

        horizon_analysis = self._analyze_horizon_winrates(trades)
        patterns.extend(horizon_analysis)

        signal_analysis = self._analyze_signal_winrates(trades)
        patterns.extend(signal_analysis)

        self._save_patterns(user_id, patterns)
        return patterns

    def _get_user_trades(self, user_id: str) -> List[HoldingRecord]:
        from modules.memory.episodic_memory import EpisodicMemory
        return EpisodicMemory().get_trade_history(user_id, limit=200)

    def _analyze_sector_winrates(self, trades: List[HoldingRecord]) -> List[InvestmentPattern]:
        sector_trades = defaultdict(list)
        for t in trades:
            if t.sell_date and t.pnl is not None:
                from core.storage.mongo_storage import StockInfoStorage
                try:
                    info = StockInfoStorage().get_by_code(t.code)
                    sector = (info or {}).get("industry", "未知")
                except Exception:
                    sector = "未知"
                sector_trades[sector].append(t)

        patterns = []
        for sector, sector_trades_list in sector_trades.items():
            if len(sector_trades_list) < 3:
                continue
            wins = sum(1 for t in sector_trades_list if t.pnl and t.pnl > 0)
            winrate = wins / len(sector_trades_list)
            if winrate >= 0.6:
                patterns.append(InvestmentPattern(
                    user_id=trades[0].user_id,
                    pattern_type="winning_sector",
                    description=f"你在{sector}行业的历史胜率高达{winrate:.0%}（{wins}/{len(sector_trades_list)}）",
                    conditions={"sector": sector, "min_samples": len(sector_trades_list)},
                    confidence=round(winrate, 2),
                    discovered_at=beijing_now().isoformat(),
                ))
            elif winrate <= 0.35:
                patterns.append(InvestmentPattern(
                    user_id=trades[0].user_id,
                    pattern_type="losing_sector",
                    description=f"你在{sector}行业的胜率较低（{winrate:.0%}），建议谨慎参与",
                    conditions={"sector": sector, "min_samples": len(sector_trades_list)},
                    confidence=round(1 - winrate, 2),
                    discovered_at=beijing_now().isoformat(),
                ))
        return patterns

    def _analyze_horizon_winrates(self, trades: List[HoldingRecord]) -> List[InvestmentPattern]:
        closed = [t for t in trades if t.sell_date and t.pnl is not None]
        if len(closed) < 5:
            return []

        from datetime import datetime as dt
        for t in closed:
            try:
                buy = dt.strptime(t.buy_date, "%Y-%m-%d")
                sell = dt.strptime(t.sell_date, "%Y-%m-%d")
                t.holding_days = (sell - buy).days
            except Exception:
                t.holding_days = 30

        short = [t for t in closed if t.holding_days <= 20]
        medium = [t for t in closed if 20 < t.holding_days <= 60]
        long_term = [t for t in closed if t.holding_days > 60]

        patterns = []
        for label, group in [("短期（≤20天）", short), ("中期（20-60天）", medium), ("长期（>60天）", long_term)]:
            if len(group) >= 3:
                wins = sum(1 for t in group if t.pnl and t.pnl > 0)
                winrate = wins / len(group)
                total_pnl = sum(t.pnl or 0 for t in group)
                if winrate > 0.55 or total_pnl > 0:
                    patterns.append(InvestmentPattern(
                        user_id=trades[0].user_id,
                        pattern_type="horizon_performance",
                        description=f"你的{label}持仓表现最佳（胜率{winrate:.0%}，总盈亏{total_pnl:+.0f}）",
                        conditions={"horizon": label, "winrate": winrate, "total_pnl": total_pnl},
                        confidence=round(max(winrate, 0.5), 2),
                        discovered_at=beijing_now().isoformat(),
                    ))
        return patterns

    def _analyze_signal_winrates(self, trades: List[HoldingRecord]) -> List[InvestmentPattern]:
        closed = [t for t in trades if t.sell_date and t.pnl is not None and t.reason]
        if len(closed) < 5:
            return []

        reason_trades = defaultdict(list)
        for t in closed:
            reason = t.reason[:20]
            reason_trades[reason].append(t)

        patterns = []
        for reason, group in reason_trades.items():
            if len(group) < 2:
                continue
            wins = sum(1 for t in group if t.pnl and t.pnl > 0)
            winrate = wins / len(group)
            avg_return = sum(t.pnl or 0 for t in group) / len(group)
            if winrate >= 0.6 and avg_return > 0:
                patterns.append(InvestmentPattern(
                    user_id=trades[0].user_id,
                    pattern_type="winning_signal",
                    description=f"基于「{reason}」的买入策略成功率{winrate:.0%}，平均收益{avg_return:.1f}",
                    conditions={"signal_pattern": reason, "winrate": winrate, "avg_return": avg_return},
                    confidence=round(winrate, 2),
                    discovered_at=beijing_now().isoformat(),
                ))
        return patterns

    # ==================== 模式存储 ====================

    def _save_patterns(self, user_id: str, patterns: List[InvestmentPattern]):
        self.db[self.COLLECTION_PATTERNS].delete_many({"user_id": user_id})
        if patterns:
            self.db[self.COLLECTION_PATTERNS].insert_many([
                p.to_dict() for p in patterns
            ])

    def get_patterns(self, user_id: str) -> List[InvestmentPattern]:
        docs = self.db[self.COLLECTION_PATTERNS].find(
            {"user_id": user_id},
            sort=[("confidence", -1)],
        )
        return [InvestmentPattern.from_dict(d) for d in docs]

    def get_top_patterns(self, user_id: str, limit: int = 5) -> List[InvestmentPattern]:
        return self.get_patterns(user_id)[:limit]

    # ==================== 统计 ====================

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        patterns = self.get_patterns(user_id)
        return {
            "pattern_count": len(patterns),
            "winning_patterns": sum(1 for p in patterns if "winning" in p.pattern_type),
            "losing_patterns": sum(1 for p in patterns if "losing" in p.pattern_type),
            "top_patterns": [p.to_dict() for p in patterns[:3]],
        }
