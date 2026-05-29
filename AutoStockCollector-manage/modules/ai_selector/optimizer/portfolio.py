"""
Optimizer模块 - 组合优化、仓位管理、风控
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class Position:
    code: str
    name: str
    weight: float
    entry_price: float
    current_price: float
    shares: int
    pnl: float
    pnl_percent: float


@dataclass
class Portfolio:
    positions: List[Position]
    total_value: float
    cash: float
    total_pnl: float
    total_pnl_percent: float


class PortfolioOptimizer:
    def __init__(self, max_stocks: int = 10, max_position: float = 0.20, min_position: float = 0.02):
        self.max_stocks = max_stocks
        self.max_position = max_position
        self.min_position = min_position

    def optimize(
        self,
        selection_results: List[Dict[str, Any]],
        total_value: float,
        market_phase: str = "consolidation"
    ) -> List[Dict[str, Any]]:
        if not selection_results:
            return []

        sorted_results = sorted(
            selection_results,
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:self.max_stocks]

        if market_phase == "bull":
            weights = self._calculate_bull_weights(sorted_results)
        elif market_phase == "bear":
            weights = self._calculate_bear_weights(sorted_results)
        else:
            weights = self._calculate_balanced_weights(sorted_results)

        optimized = []
        for i, result in enumerate(sorted_results):
            weight = weights[i] if i < len(weights) else self.min_position

            if weight > self.max_position:
                weight = self.max_position

            entry_price = result.get("current_price", result.get("target_price", 0))
            if entry_price <= 0:
                continue

            shares = int((total_value * weight) / entry_price / 100) * 100

            optimized.append({
                "code": result["code"],
                "name": result.get("name", ""),
                "weight": round(weight, 4),
                "shares": shares,
                "entry_price": entry_price,
                "estimated_value": round(shares * entry_price, 2),
                "score": result.get("score", 0),
                "recommendation": result.get("recommendation", "观望"),
                "stop_loss": result.get("stop_loss", entry_price * 0.95),
                "target_price": result.get("target_price", entry_price * 1.15),
                "risk_level": result.get("risk_level", "medium")
            })

        return optimized

    def _calculate_bull_weights(self, results: List[Dict[str, Any]]) -> List[float]:
        total_score = sum(r.get("score", 50) for r in results)
        if total_score == 0:
            return [1.0 / len(results)] * len(results)

        base_weights = [r.get("score", 50) / total_score for r in results]

        max_weight = min(self.max_position * 1.2, 0.30)
        adjusted = []
        for w in base_weights:
            if w > max_weight:
                w = max_weight
            adjusted.append(w)

        total = sum(adjusted)
        return [w / total * sum(base_weights) if total > 0 else w for w in adjusted]

    def _calculate_bear_weights(self, results: List[Dict[str, Any]]) -> List[float]:
        defensive = [r for r in results if r.get("risk_level") in ["low", "medium"]]
        if not defensive:
            defensive = results[:3] if len(results) >= 3 else results

        weights = []
        for r in results:
            if r in defensive:
                weights.append(1.0)
            else:
                weights.append(0.5)

        total = sum(weights)
        if total == 0:
            return [self.min_position] * len(results)

        return [self.min_position + (w / total) * (self.max_position * 0.5 - self.min_position) for w in weights]

    def _calculate_balanced_weights(self, results: List[Dict[str, Any]]) -> List[float]:
        equal_weight = 1.0 / len(results) if results else 0

        score_weight = []
        total_score = sum(r.get("score", 50) for r in results)
        for r in results:
            score = r.get("score", 50)
            score_weight.append(score / total_score if total_score > 0 else equal_weight)

        final_weights = []
        for sw in score_weight:
            w = sw * 0.6 + equal_weight * 0.4
            if w < self.min_position:
                w = self.min_position
            final_weights.append(w)

        return final_weights


class RiskController:
    def __init__(
        self,
        max_portfolio_loss: float = 0.15,
        max_single_loss: float = 0.08,
        max_correlation: float = 0.7
    ):
        self.max_portfolio_loss = max_portfolio_loss
        self.max_single_loss = max_single_loss
        self.max_correlation = max_correlation

    def check_risk(
        self,
        portfolio: Portfolio,
        market_volatility: float = 0.2
    ) -> Dict[str, Any]:
        warnings = []
        should_rebalance = False

        if portfolio.total_pnl_percent <= -self.max_portfolio_loss * 100:
            warnings.append("组合最大回撤超限，建议减仓")
            should_rebalance = True

        for pos in portfolio.positions:
            if pos.pnl_percent <= -self.max_single_loss * 100:
                warnings.append(f"{pos.code} 亏损超限，建议止损")
                should_rebalance = True

        if market_volatility > 0.35:
            warnings.append("市场波动率较高，建议降低仓位")
            should_rebalance = True

        return {
            "warnings": warnings,
            "should_rebalance": should_rebalance,
            "risk_level": "high" if len(warnings) >= 2 else "medium" if warnings else "low"
        }

    def calculate_stop_loss(
        self,
        entry_price: float,
        market_phase: str = "consolidation",
        volatility: float = 0.2
    ) -> float:
        base_loss = {
            "bull": 0.07,
            "consolidation": 0.05,
            "bear": 0.04
        }.get(market_phase, 0.05)

        if volatility > 0.3:
            base_loss *= 0.8

        return round(entry_price * (1 - base_loss), 2)

    def calculate_take_profit(
        self,
        entry_price: float,
        market_phase: str = "consolidation",
        volatility: float = 0.2
    ) -> float:
        base_profit = {
            "bull": 0.15,
            "consolidation": 0.10,
            "bear": 0.06
        }.get(market_phase, 0.10)

        if volatility > 0.3:
            base_profit *= 0.7

        return round(entry_price * (1 + base_profit), 2)


portfolio_optimizer = PortfolioOptimizer()
risk_controller = RiskController()