"""
技术因子库
"""
from typing import List, Dict, Any, Optional
import numpy as np
from .base import FactorBase, FactorData, factor_registry
from utils.logger import get_logger


logger = get_logger(__name__)


class TrendFactor(FactorBase):
    def __init__(self):
        super().__init__(name="trend", category="technical")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 5:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        closes = np.array([k.get("close", 0) for k in kline_data])
        volumes = np.array([k.get("volume", 0) for k in kline_data])

        ma5 = np.mean(closes[:5])
        ma10 = np.mean(closes[:10]) if len(closes) >= 10 else ma5
        ma20 = np.mean(closes[:20]) if len(closes) >= 20 else ma5
        ma60 = np.mean(closes[:60]) if len(closes) >= 60 else ma5

        current = closes[0]

        score = 50.0
        trend_score = 0.0
        if current > ma5 > ma10 > ma20:
            trend_score = 40.0
        elif current > ma5 > ma20:
            trend_score = 25.0
        elif current < ma5 < ma10 < ma20:
            trend_score = 10.0
        elif current < ma5 < ma20:
            trend_score = 20.0

        change_pct = 0.0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (current - closes[1]) / closes[1] * 100
        change_score = min(30.0, max(-30.0, change_pct * 3))

        score = trend_score + change_score + 10
        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "current_price": float(current),
                "ma5": float(ma5),
                "ma10": float(ma10),
                "ma20": float(ma20),
                "ma60": float(ma60),
                "change_pct": float(change_pct),
                "trend_strength": trend_score
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class VolumeFactor(FactorBase):
    def __init__(self):
        super().__init__(name="volume", category="technical")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 5:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        volumes = np.array([k.get("volume", 0) for k in kline_data])
        closes = np.array([k.get("close", 0) for k in kline_data])

        current_vol = volumes[0]
        avg_vol = np.mean(volumes[1:]) if len(volumes) > 1 else current_vol
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

        price_change = 0.0
        if len(closes) >= 2 and closes[1] > 0:
            price_change = (closes[0] - closes[1]) / closes[1] * 100

        score = 50.0
        if vol_ratio > 2.0:
            score += 25
        elif vol_ratio > 1.5:
            score += 15
        elif vol_ratio < 0.5:
            score -= 15

        if price_change > 5:
            score += 10
        elif price_change < -5:
            score -= 10

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "current_volume": float(current_vol),
                "avg_volume": float(avg_vol),
                "volume_ratio": float(vol_ratio),
                "price_change": float(price_change)
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class MomentumFactor(FactorBase):
    def __init__(self):
        super().__init__(name="momentum", category="technical")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 5:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        closes = np.array([k.get("close", 0) for k in kline_data])

        changes = []
        for i in range(min(5, len(closes) - 1)):
            if closes[i + 1] > 0:
                change = (closes[i] - closes[i + 1]) / closes[i + 1] * 100
                changes.append(change)

        score = 50.0
        if changes:
            recent_3 = changes[:3] if len(changes) >= 3 else changes
            sum_change = sum(recent_3)
            avg_change = sum_change / len(recent_3)

            if all(c > 0 for c in recent_3) and sum_change > 5:
                score = 80.0
            elif all(c > 0 for c in recent_3) and sum_change > 2:
                score = 70.0
            elif all(c < 0 for c in recent_3) and sum_change < -5:
                score = 30.0
            elif all(c < 0 for c in recent_3) and sum_change < -2:
                score = 40.0
            else:
                score = 50.0 + avg_change * 2

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "momentum_5d": float(sum(changes[:5])) if len(changes) >= 5 else float(sum(changes)),
                "avg_change": float(sum(changes) / len(changes)) if changes else 0.0,
                "positive_days": sum(1 for c in changes if c > 0),
                "negative_days": sum(1 for c in changes if c < 0)
            },
            score=score
        )
        self._save_to_cache(result)
        return result


class VolatilityFactor(FactorBase):
    def __init__(self):
        super().__init__(name="volatility", category="technical")

    def calculate(self, code: str, kline_data: List[Dict[str, Any]], **kwargs) -> FactorData:
        cached = self._get_from_cache(code, "")
        if cached:
            return cached

        if len(kline_data) < 10:
            return FactorData(code=code, name=code, date="", values={}, score=50.0)

        closes = np.array([k.get("close", 0) for k in kline_data])

        returns = []
        for i in range(len(closes) - 1):
            if closes[i + 1] > 0:
                ret = (closes[i] - closes[i + 1]) / closes[i + 1]
                returns.append(ret)

        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.0

        score = 50.0
        if 0.15 < volatility < 0.25:
            score = 70.0
        elif volatility < 0.15:
            score = 60.0
        elif volatility > 0.35:
            score = 40.0

        score = max(0, min(100, score))

        result = FactorData(
            code=code,
            name=kline_data[0].get("name", ""),
            date=kline_data[0].get("date", ""),
            values={
                "daily_volatility": float(np.std(returns)) if len(returns) > 1 else 0.0,
                "annualized_volatility": float(volatility),
                "max_price": float(np.max(closes)),
                "min_price": float(np.min(closes)),
                "price_range": float(np.max(closes) - np.min(closes))
            },
            score=score
        )
        self._save_to_cache(result)
        return result


factor_registry.register(TrendFactor())
factor_registry.register(VolumeFactor())
factor_registry.register(MomentumFactor())
factor_registry.register(VolatilityFactor())