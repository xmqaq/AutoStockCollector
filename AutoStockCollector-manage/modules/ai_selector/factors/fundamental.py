"""
基本面因子库
"""
from typing import List, Dict, Any, Optional
from .base import FactorBase, FactorData, factor_registry
from utils.logger import get_logger


logger = get_logger(__name__)


class ValuationFactor(FactorBase):
    def __init__(self):
        super().__init__(name="valuation", category="fundamental")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        stock_info = kwargs.get("stock_info")
        if not stock_info:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        pe = stock_info.get("pe") or 0
        pb = stock_info.get("pb") or 0
        ps = stock_info.get("ps") or 0
        roe = stock_info.get("roe") or 0
        market_cap = stock_info.get("market_cap") or 0

        score = 50.0

        if pe and 5 < pe < 25:
            score += 15
        elif pe and 0 < pe <= 5:
            score += 10
        elif pe and 25 <= pe < 40:
            score += 5
        elif pe and pe >= 40:
            score -= 15

        if pb and 0.5 < pb < 3:
            score += 10
        elif pb and 0 < pb <= 0.5:
            score += 5
        elif pb and pb >= 3:
            score -= 5

        if roe and roe > 15:
            score += 15
        elif roe and roe > 10:
            score += 10
        elif roe and roe > 5:
            score += 5
        elif roe and roe < 0:
            score -= 15

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=stock_info.get("name", ""),
            date=stock_info.get("date", ""),
            values={
                "pe": float(pe) if pe else 0.0,
                "pb": float(pb) if pb else 0.0,
                "ps": float(ps) if ps else 0.0,
                "roe": float(roe) if roe else 0.0,
                "market_cap": float(market_cap) if market_cap else 0.0,
                "valuation_score": score
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class GrowthFactor(FactorBase):
    def __init__(self):
        super().__init__(name="growth", category="fundamental")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        stock_info = kwargs.get("stock_info")
        if not stock_info:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        revenue_growth = stock_info.get("revenue_growth") or 0
        profit_growth = stock_info.get("profit_growth") or 0
        asset_growth = stock_info.get("asset_growth") or 0

        score = 50.0

        if profit_growth and profit_growth > 30:
            score = 85.0
        elif profit_growth and profit_growth > 15:
            score = 75.0
        elif profit_growth and profit_growth > 0:
            score = 60.0
        elif profit_growth and profit_growth < -20:
            score = 30.0
        elif profit_growth and profit_growth < 0:
            score = 45.0

        if revenue_growth and revenue_growth > 20:
            score = min(100, score + 10)
        elif revenue_growth and revenue_growth < 0:
            score = max(0, score - 10)

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=stock_info.get("name", ""),
            date=stock_info.get("date", ""),
            values={
                "revenue_growth": float(revenue_growth) if revenue_growth else 0.0,
                "profit_growth": float(profit_growth) if profit_growth else 0.0,
                "asset_growth": float(asset_growth) if asset_growth else 0.0,
                "growth_score": score
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class FinancialHealthFactor(FactorBase):
    def __init__(self):
        super().__init__(name="financial_health", category="fundamental")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        stock_info = kwargs.get("stock_info")
        if not stock_info:
            return FactorData(code=code, name="", date="", values={}, score=50.0)

        current_ratio = stock_info.get("current_ratio") or 1.5
        debt_ratio = stock_info.get("debt_ratio") or 0.5
        quick_ratio = stock_info.get("quick_ratio") or 1.0

        score = 50.0

        if debt_ratio and debt_ratio < 0.4:
            score += 15
        elif debt_ratio and debt_ratio < 0.6:
            score += 10
        elif debt_ratio and debt_ratio >= 0.7:
            score -= 15

        if current_ratio and current_ratio > 2:
            score += 10
        elif current_ratio and current_ratio > 1:
            score += 5
        elif current_ratio and current_ratio < 1:
            score -= 10

        if quick_ratio and quick_ratio > 1:
            score += 5

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=stock_info.get("name", ""),
            date=stock_info.get("date", ""),
            values={
                "current_ratio": float(current_ratio) if current_ratio else 0.0,
                "debt_ratio": float(debt_ratio) if debt_ratio else 0.0,
                "quick_ratio": float(quick_ratio) if quick_ratio else 0.0,
                "health_score": score
            },
            score=score
        )
        self._save_to_cache(result)
        return result


factor_registry.register(ValuationFactor())
factor_registry.register(GrowthFactor())
factor_registry.register(FinancialHealthFactor())