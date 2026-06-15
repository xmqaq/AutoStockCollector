"""
技术面分析器 — MA趋势、RSI、MACD等基础技术指标
输出短/长期技术面信号
"""
import numpy as np
from typing import Any, Dict, List, Optional
from core.storage.mongo_storage import KlineStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    SHORT_DAYS = 60

    def __init__(self):
        self._kline = KlineStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        klines = self._get_klines(code)
        if not klines or len(klines) < 20:
            return self._empty_result("K线数据不足")

        closes = np.array([float(k["close"]) for k in klines], dtype=float)
        prices = closes[::-1]  # 时间正序

        short = self._analyze_short_term(prices)
        long_ = self._analyze_long_term(prices)
        combined = self._combine(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **combined,
            "current_price": float(prices[-1]) if len(prices) > 0 else 0,
        }

    def _get_klines(self, code: str) -> List[Dict[str, Any]]:
        return list(self._kline.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=120,
        ))

    def _analyze_short_term(self, prices: np.ndarray) -> Dict[str, Any]:
        if len(prices) < 10:
            return self._score(50, "hold", ["数据不足"])

        ma5 = np.mean(prices[-5:]) if len(prices) >= 5 else prices[-1]
        ma10 = np.mean(prices[-10:]) if len(prices) >= 10 else prices[-1]
        ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else None
        current = prices[-1]

        reasons = []
        # MA趋势 (30%)
        if ma20 and current > ma5 > ma10 > ma20:
            trend_score = 85
            reasons.append("强多头排列")
        elif current > ma5 > ma10:
            trend_score = 70
            reasons.append("短期多头排列")
        elif current < ma5 < ma10:
            trend_score = 30
            reasons.append("短期空头排列")
        elif current > ma5:
            trend_score = 60
            reasons.append("站上5日均线")
        else:
            trend_score = 40
            reasons.append("跌破5日均线")

        # MACD (25%)
        macd_score = self._calc_macd_score(prices)

        # RSI (20%)
        rsi = self._calc_rsi(prices, 14)
        rsi_score = 50
        if rsi >= 70:
            rsi_score = 20
            reasons.append(f"RSI{rsi:.0f} 超买")
        elif 60 <= rsi < 70:
            rsi_score = 65
        elif 45 <= rsi < 60:
            rsi_score = 75
        elif 30 <= rsi < 45:
            rsi_score = 50
        elif rsi < 30:
            rsi_score = 80
            reasons.append(f"RSI{rsi:.0f} 超卖")

        # 价格动量 (15%)
        mom_score = self._calc_momentum(prices)

        # 成交量 (10%)
        vol_score = self._calc_volume_score(prices, trend_score, reasons)

        breakdown = {"均线趋势": trend_score, "MACD": macd_score, "RSI": rsi_score, "动量": mom_score, "成交量": vol_score}
        score = trend_score * 0.30 + macd_score * 0.25 + rsi_score * 0.20 + mom_score * 0.15 + vol_score * 0.10
        score = max(0, min(100, score))
        signal = self._signal_from_score(score)

        return {
            "score": round(score, 1),
            "signal": signal,
            "reasons": reasons[:3],
            "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
        }

    def _analyze_long_term(self, prices: np.ndarray) -> Dict[str, Any]:
        if len(prices) < 50:
            return self._score(50, "hold", ["长期数据不足"])

        ma20 = np.mean(prices[-20:])
        ma60 = np.mean(prices[-60:]) if len(prices) >= 60 else np.mean(prices)
        ma120 = np.mean(prices[-120:]) if len(prices) >= 120 else None
        current = prices[-1]

        reasons = []

        # MA趋势 (60%)
        if ma120 and current > ma20 > ma60 > ma120:
            trend_score = 85
            reasons.append("长期强多头")
        elif current > ma20 > ma60:
            trend_score = 70
            reasons.append("中长期多头趋势")
        elif current < ma20 < ma60:
            trend_score = 25
            reasons.append("中长期空头趋势")
        elif current > ma20:
            trend_score = 55
            reasons.append("站上20日均线")
        else:
            trend_score = 35
            reasons.append("低于20日均线")

        # 波动率风险 (-20分)
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns[-60:]) * np.sqrt(252) if len(returns) >= 60 else np.std(returns) * np.sqrt(252)
        vol_penalty = 0
        if volatility > 0.5:
            vol_penalty = 20
            reasons.append("高波动风险")
        elif volatility > 0.35:
            vol_penalty = 10

        # 长期动量 (20%)
        if len(prices) >= 60:
            long_mom = (prices[-1] / prices[-61] - 1) * 100 if prices[-61] > 0 else 0
            if long_mom > 30: mom_score = 80
            elif long_mom > 15: mom_score = 70
            elif long_mom > 5: mom_score = 55
            elif long_mom > -5: mom_score = 45
            elif long_mom > -15: mom_score = 30
            else: mom_score = 20
        else:
            mom_score = 50

        # 稳定性 (20%)
        stability = max(0, 100 - vol_penalty * 3)

        breakdown = {"均线趋势": trend_score, "长期动量": mom_score, "稳定性": stability}
        score = trend_score * 0.60 + mom_score * 0.20 + stability * 0.20 - vol_penalty
        score = max(0, min(100, score))
        signal = self._signal_from_score(score)

        return {
            "score": round(score, 1),
            "signal": signal,
            "reasons": reasons[:3],
            "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
            "volatility": round(volatility, 4),
        }

    def _calc_macd_score(self, prices: np.ndarray) -> float:
        if len(prices) < 27:
            return 50
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        dif = ema12[-1] - ema26[-1]
        dea = np.mean([ema12[i] - ema26[i] for i in range(-9, 0)]) if len(prices) >= 35 else dif
        bar = dif - dea
        prev_dif = ema12[-2] - ema26[-2] if len(ema12) >= 2 else dif
        prev_dea = np.mean([ema12[i] - ema26[i] for i in range(-10, -1)]) if len(prices) >= 36 else dea
        prev_bar = prev_dif - prev_dea

        if dif > dea and bar > 0 and bar > prev_bar:
            return 85
        elif dif > dea and bar > 0:
            return 70
        elif dif > dea:
            return 55
        elif dif < dea and abs(bar) < abs(prev_bar):
            return 40
        elif dif < dea and bar < prev_bar:
            return 20
        else:
            return 35

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros(len(prices))
        multiplier = 2 / (period + 1)
        result[0] = prices[0]
        for i in range(1, len(prices)):
            result[i] = (prices[i] - result[i-1]) * multiplier + result[i-1]
        return result

    def _calc_momentum(self, prices: np.ndarray) -> float:
        if len(prices) < 21:
            return 50
        n = min(20, len(prices) - 1)
        mom = (prices[-1] / prices[-(n+1)] - 1) * 100
        if mom > 30: return 30
        elif mom > 15: return 85
        elif mom > 8: return 70
        elif mom > 3: return 55
        elif mom > 0: return 45
        elif mom > -5: return 35
        else: return 20

    def _calc_volume_score(self, prices: np.ndarray, trend_score: float, reasons: list) -> float:
        if len(prices) < 15:
            return 50
        recent_vol = np.std(prices[-5:])
        prev_vol = np.std(prices[-15:-5])
        if prev_vol <= 0:
            return 50
        vol_ratio = recent_vol / prev_vol
        if vol_ratio > 1.5 and trend_score >= 60:
            reasons.append("放量上涨")
            return 75
        elif vol_ratio > 1.5 and trend_score <= 40:
            reasons.append("放量下跌")
            return 25
        elif vol_ratio > 1.2:
            return 60
        elif vol_ratio < 0.7:
            return 35
        return 50

    def _calc_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices[-(period+1):])
        gains = np.sum(deltas[deltas > 0])
        losses = abs(np.sum(deltas[deltas < 0]))
        if losses == 0:
            return 100.0 if gains > 0 else 50.0
        rs = gains / losses
        return 100 - (100 / (1 + rs))

    def _signal_from_score(self, score: float) -> str:
        if score >= 75:
            return "strong_buy"
        elif score >= 62:
            return "buy"
        elif score >= 38:
            return "hold"
        elif score >= 25:
            return "sell"
        else:
            return "strong_sell"

    def _combine(self, short: Dict, long_: Dict) -> Dict:
        score = short.get("score", 50) * 0.5 + long_.get("score", 50) * 0.5
        signal = self._signal_from_score(score)
        return {"composite_score": round(score, 1), "composite_signal": signal}

    def _score(self, score: float, signal: str, reasons: List[str], **extra) -> Dict:
        return {
            "score": score,
            "signal": signal,
            "reasons": reasons,
            **extra,
        }

    def _empty_result(self, reason: str) -> Dict:
        return {
            "short_term": self._score(50, "hold", [reason]),
            "long_term": self._score(50, "hold", [reason]),
            "composite_score": 50.0,
            "composite_signal": "hold",
            "current_price": 0,
        }
