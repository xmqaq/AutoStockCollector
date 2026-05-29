"""
基本面价值选股策略
"""
from typing import List, Dict, Any
from .base import BaseStrategy, SelectionResult
from modules.ai.ai_analyzer import ai_analyzer
from utils.logger import get_logger


logger = get_logger(__name__)


class ValueStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="基本面价值选股",
            description="基于基本面价值选股"
        )
        self.min_score = 55.0
        self.max_stocks = 20

    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage

        info_storage = StockInfoStorage()

        filtered = []
        for code in codes:
            info = info_storage.get_by_code(code)
            if not info:
                continue

            name = info.get("name", "")
            if any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                continue

            pe = info.get("pe")
            if pe and (pe < 0 or pe > 100):
                continue

            filtered.append(code)

        return filtered

    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage

        kline_storage = KlineStorage()
        info_storage = StockInfoStorage()

        factors = {}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=20
        )

        if klines:
            current = klines[0].get("close", 0)
            factors["current_price"] = current
            factors["name"] = klines[0].get("name", "")

            if len(klines) >= 2 and klines[1].get("close", 0) > 0:
                factors["change_pct"] = (current - klines[1].get("close", 0)) / klines[1].get("close", 0) * 100
            else:
                factors["change_pct"] = 0
        else:
            factors["current_price"] = 0
            factors["name"] = ""
            factors["change_pct"] = 0

        info = info_storage.get_by_code(code)
        if info:
            factors["pe"] = info.get("pe") or 0
            factors["pb"] = info.get("pb") or 0
            factors["roe"] = info.get("roe") or 0
            factors["market_cap"] = info.get("market_cap") or 0
            factors["fundamental_score"] = self._calculate_valuation_score(info)
        else:
            factors["pe"] = 0
            factors["pb"] = 0
            factors["roe"] = 0
            factors["market_cap"] = 0
            factors["fundamental_score"] = 50.0

        factors["technical_score"] = 50.0
        factors["sentiment_score"] = 50.0
        factors["fund_flow_score"] = 50.0

        return factors

    def _calculate_valuation_score(self, info: Dict[str, Any]) -> float:
        score = 50.0

        pe = info.get("pe")
        if pe and 5 < pe < 25:
            score += 15
        elif pe and 0 < pe <= 5:
            score += 10
        elif pe and 25 <= pe < 40:
            score += 5
        elif pe and pe >= 40:
            score -= 15

        pb = info.get("pb")
        if pb and 0.5 < pb < 3:
            score += 10
        elif pb and pb >= 3:
            score -= 5

        roe = info.get("roe")
        if roe and roe > 15:
            score += 15
        elif roe and roe > 10:
            score += 10
        elif roe and roe < 0:
            score -= 15

        return max(0, min(100, score))

    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        valuation = factors.get("fundamental_score", 50.0)
        pe = factors.get("pe", 0)
        pb = factors.get("pb", 0)

        base_score = valuation

        if pe and pe < 0:
            base_score *= 0.8

        return max(0, min(100, base_score))