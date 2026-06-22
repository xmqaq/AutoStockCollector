"""盘前竞价雷达 — 仓位建议（基于开盘强度 + 风险信号）。"""
from dataclasses import dataclass, field
from typing import Optional

from .schemas import RadarStock

MAX_TOTAL_POSITION_PCT = 1.0  # 总仓位上限 100%
MAX_SINGLE_POSITION_PCT = 0.20  # 单票上限 20%
MIN_TRADE_SCORE = 60  # 低于该分数不交易


@dataclass
class PositionSuggestion:
    symbol: str = ""
    name: str = ""
    action: str = "skip"  # skip / observe / buy
    position_pct: float = 0.0  # 建议仓位百分比 (0~1)
    confidence: str = "low"  # low / medium / high
    reason: str = ""


@dataclass
class AuctionPositionSizer:
    """仓位计算器。

    Logic:
      - score >= 80, no trap  → buy, 10~20%, high confidence
      - score >= 60, no trap  → observe, 5~10%, medium confidence
      - score >= 80, has trap → observe, ≤5%, medium-low confidence
      - score < 60            → skip
      - Sector resonance (通过 strength_detail.sector_score) 做加减:
        sector_score >= 80   → position × 1.2 (最多到 MAX_SINGLE)
        sector_score <= 30   → position × 0.5
    """

    total_used_pct: float = 0.0  # 已用仓位
    suggestions: list = field(default_factory=list)

    def suggest(self, stock: RadarStock) -> PositionSuggestion:
        if not stock.strength_detail:
            return PositionSuggestion(
                symbol=stock.symbol, name=stock.name, reason="缺少强度详情"
            )

        score = stock.strength_score
        is_trap = stock.trap_warning is not None
        sector_score = stock.strength_detail.sector_score

        # 低于门槛不交易
        if score < MIN_TRADE_SCORE:
            return PositionSuggestion(
                symbol=stock.symbol, name=stock.name, reason=f"强度{score}<{MIN_TRADE_SCORE}"
            )

        # 基础仓位
        if score >= 80 and not is_trap:
            base = 0.15
            conf = "high"
            action = "buy"
        elif score >= 60 and not is_trap:
            base = 0.07
            conf = "medium"
            action = "observe"
        elif score >= 80 and is_trap:
            base = 0.05
            conf = "medium"
            action = "observe"
        else:
            base = 0.03
            conf = "low"
            action = "observe"

        # 板块共振调整
        if sector_score >= 80:
            base = min(base * 1.2, MAX_SINGLE_POSITION_PCT)
        elif sector_score <= 30:
            base = base * 0.5

        # 剩余仓位保护
        remaining = MAX_TOTAL_POSITION_PCT - self.total_used_pct
        final_pct = min(base, remaining, MAX_SINGLE_POSITION_PCT)
        final_pct = round(max(final_pct, 0.0), 4)

        if final_pct <= 0:
            action = "skip"
            conf = "low"

        suggestion = PositionSuggestion(
            symbol=stock.symbol,
            name=stock.name,
            action=action,
            position_pct=final_pct,
            confidence=conf,
            reason=self._build_reason(score, is_trap, sector_score, final_pct),
        )
        self.suggestions.append(suggestion)
        self.total_used_pct += final_pct
        return suggestion

    def _build_reason(
        self, score: int, is_trap: bool, sector_score: float, raw_pct: float
    ) -> str:
        parts = [f"强度{score}"]
        if is_trap:
            parts.append("诱多/诱空预警")
        if sector_score >= 80:
            parts.append("板块共振强劲")
        elif sector_score <= 30:
            parts.append("板块共振弱")
        parts.append(f"建议仓位{raw_pct*100:.0f}%")
        return "，".join(parts)
