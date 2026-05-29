"""
资金异动主力跟踪策略
"""
from typing import List, Dict, Any
import numpy as np
from .base import BaseStrategy, SelectionResult
from utils.logger import get_logger


logger = get_logger(__name__)


class FundFlowStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="资金异动主力跟踪",
            description="基于资金异动主力跟踪选股"
        )
        self.min_score = 65.0
        self.max_stocks = 20

    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage, FundFlowStorage

        info_storage = StockInfoStorage()
        flow_storage = FundFlowStorage()

        filtered = []
        for code in codes:
            info = info_storage.get_by_code(code)
            if not info:
                continue

            name = info.get("name", "")
            if any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                continue

            flow = flow_storage.get_latest_flow(code)
            if flow:
                main_inflow = flow.get("main_net_inflow", 0)
                if main_inflow > 0:
                    filtered.append(code)

        return filtered

    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, FundFlowStorage

        kline_storage = KlineStorage()
        flow_storage = FundFlowStorage()

        factors = {}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            volumes = [k.get("volume", 0) for k in klines]
            current = closes[0]

            factors["current_price"] = current
            factors["name"] = klines[0].get("name", "")

            ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current
            factors["ma20"] = ma20
            factors["trend"] = 1 if current > ma20 else -1

            if len(closes) >= 2 and closes[1] > 0:
                factors["change_pct"] = (current - closes[1]) / closes[1] * 100
            else:
                factors["change_pct"] = 0

            avg_vol = np.mean(volumes[1:]) if len(volumes) > 1 else volumes[0]
            factors["volume_ratio"] = volumes[0] / avg_vol if avg_vol > 0 else 1.0

            factors["technical_score"] = self._calculate_technical_score(factors)
        else:
            factors["current_price"] = 0
            factors["name"] = ""
            factors["ma20"] = 0
            factors["trend"] = 0
            factors["change_pct"] = 0
            factors["volume_ratio"] = 1.0
            factors["technical_score"] = 50.0

        flow = flow_storage.get_latest_flow(code)
        if flow:
            factors["main_net_inflow"] = flow.get("main_net_inflow", 0)
            factors["retail_net_inflow"] = flow.get("retail_net_inflow", 0)
            factors["fund_flow_score"] = self._calculate_flow_score(flow)
        else:
            factors["main_net_inflow"] = 0
            factors["retail_net_inflow"] = 0
            factors["fund_flow_score"] = 50.0

        factors["sentiment_score"] = 50.0
        factors["fundamental_score"] = 50.0

        return factors

    def _calculate_technical_score(self, factors: Dict[str, float]) -> float:
        score = 50.0

        if factors.get("trend", 0) > 0:
            score += 15

        if factors.get("volume_ratio", 1) > 1.5:
            score += 15
        elif factors.get("volume_ratio", 1) > 1.2:
            score += 10

        change_pct = factors.get("change_pct", 0)
        if change_pct > 3:
            score += 10
        elif change_pct < -3:
            score -= 10

        return max(0, min(100, score))

    def _calculate_flow_score(self, flow: Dict[str, Any]) -> float:
        main_inflow = flow.get("main_net_inflow", 0)
        retail_inflow = flow.get("retail_net_inflow", 0)

        score = 50.0

        if main_inflow > 1e8:
            score = 85.0
        elif main_inflow > 5e7:
            score = 75.0
        elif main_inflow > 1e7:
            score = 65.0
        elif main_inflow > 0:
            score = 55.0
        elif main_inflow < -1e8:
            score = 25.0

        if retail_inflow < 0 and main_inflow > 0:
            score = min(100, score + 10)

        return score

    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        flow_score = factors.get("fund_flow_score", 50.0)
        technical_score = factors.get("technical_score", 50.0)
        volume_ratio = factors.get("volume_ratio", 1.0)

        total_score = flow_score * 0.6 + technical_score * 0.4

        if volume_ratio > 2.0:
            total_score = min(100, total_score + 5)

        return max(0, min(100, total_score))