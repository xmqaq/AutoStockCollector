"""
AI智能选股模块
结合多方面因素推荐股票
"""
from typing import List, Dict, Any, Optional
import random
from datetime import datetime
from core.storage.mongo_storage import KlineStorage, StockInfoStorage, FundFlowStorage
from modules.ai.ai_key_manager import ai_key_manager
from utils.logger import get_logger


logger = get_logger(__name__)


class SmartPicker:
    def __init__(self):
        self.kline_storage = KlineStorage()
        self.info_storage = StockInfoStorage()
        self.fund_flow_storage = FundFlowStorage()

    def pick(
        self,
        top_n: int = 10,
        factors: List[str] = None,
    ) -> List[Dict[str, Any]]:
        if factors is None:
            factors = ["trend", "volume", "value", "fund_flow"]
        scores: Dict[str, Dict[str, Any]] = {}
        all_codes = self._get_tradeable_codes()
        for code in all_codes:
            scores[code] = self._score_stock(code, factors)
        ranked = sorted(
            scores.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )[:top_n]
        return [{"code": code, **data} for code, data in ranked]

    def _get_tradeable_codes(self, limit: int = 500) -> List[str]:
        klines = self.kline_storage.find_many(
            {},
            projection={"code": 1},
            limit=limit,
        )
        return list({k.get("code") for k in klines if k.get("code")})

    def _score_stock(self, code: str, factors: List[str]) -> Dict[str, Any]:
        scores = {}
        total = 0
        if "trend" in factors:
            scores["trend"] = self._trend_score(code)
            total += scores["trend"]
        if "volume" in factors:
            scores["volume"] = self._volume_score(code)
            total += scores["volume"]
        if "value" in factors:
            scores["value"] = self._value_score(code)
            total += scores["value"]
        if "fund_flow" in factors:
            scores["fund_flow"] = self._fund_flow_score(code)
            total += scores["fund_flow"]
        if "momentum" in factors:
            scores["momentum"] = self._momentum_score(code)
            total += scores["momentum"]
        return {"scores": scores, "total": total / max(len(factors), 1)}

    def _trend_score(self, code: str) -> float:
        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=20,
        )
        if len(klines) < 5:
            return 50
        closes = [k.get("close", 0) for k in klines]
        ma5 = sum(closes[:5]) / 5
        ma20 = sum(closes[:20]) / min(len(closes), 20)
        current = closes[0]
        score = 50.0
        if current > ma5 > ma20:
            score = 80.0
        elif current > ma5:
            score = 65.0
        elif current < ma5 < ma20:
            score = 30.0
        return score

    def _volume_score(self, code: str) -> float:
        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=10,
        )
        if len(klines) < 5:
            return 50
        volumes = [k.get("volume", 0) for k in klines]
        avg_vol = sum(volumes[1:]) / max(len(volumes) - 1, 1)
        current_vol = volumes[0]
        if avg_vol > 0 and current_vol > avg_vol * 1.5:
            return min(95, 50 + (current_vol / avg_vol) * 10)
        return 50

    def _value_score(self, code: str) -> float:
        info = self.info_storage.get_by_code(code)
        if not info:
            return 50
        pe = info.get("pe")
        pb = info.get("pb")
        score = 50.0
        if pe and 5 < pe < 25:
            score += 15
        if pb and 0.5 < pb < 3:
            score += 10
        return min(100, score)

    def _fund_flow_score(self, code: str) -> float:
        flow = self.fund_flow_storage.get_latest_flow(code)
        if not flow:
            return 50
        main_inflow = flow.get("main_net_inflow", 0)
        if main_inflow > 1e7:
            return 80
        elif main_inflow > 0:
            return 60
        return 40

    def _momentum_score(self, code: str) -> float:
        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=5,
        )
        if len(klines) < 3:
            return 50
        changes = []
        for i in range(len(klines) - 1):
            prev = klines[i + 1].get("close", 0)
            curr = klines[i].get("close", 0)
            if prev > 0:
                changes.append((curr - prev) / prev * 100)
        if not changes:
            return 50
        if all(c > 0 for c in changes[-3:]) and sum(changes[-3:]) > 5:
            return 80
        if all(c < 0 for c in changes[-3:]) and sum(changes[-3:]) < -5:
            return 30
        return 50


smart_picker = SmartPicker()
