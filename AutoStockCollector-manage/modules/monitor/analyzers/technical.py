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
        current = prices[-1]

        # MA趋势
        trend_score = 50
        reasons = []
        if current > ma5 > ma10:
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

        # RSI (14)
        rsi = self._calc_rsi(prices, 14)
        rsi_score = 50
        if rsi >= 70:
            rsi_score = 20
            reasons.append(f"RSI{rsi:.0f} 超买")
        elif rsi <= 30:
            rsi_score = 80
            reasons.append(f"RSI{rsi:.0f} 超卖")
        elif rsi >= 60:
            rsi_score = 65
        elif rsi <= 40:
            rsi_score = 35

        # 成交量 (最近5日 vs 前10日)
        vol_score = 50
        if len(prices) >= 15:
            recent_vol = np.std(prices[-5:])
            prev_vol = np.std(prices[-15:-5])
            if prev_vol > 0:
                vol_ratio = recent_vol / prev_vol
                if vol_ratio > 1.5 and trend_score >= 60:
                    vol_score = 70
                    reasons.append("放量上涨")
                elif vol_ratio > 1.5 and trend_score <= 40:
                    vol_score = 30
                    reasons.append("放量下跌")

        score = trend_score * 0.5 + rsi_score * 0.3 + vol_score * 0.2
        score = max(0, min(100, score))
        signal = self._signal_from_score(score)

        return self._score(round(score, 1), signal, reasons[:3])

    def _analyze_long_term(self, prices: np.ndarray) -> Dict[str, Any]:
        if len(prices) < 50:
            return self._score(50, "hold", ["长期数据不足"])

        ma20 = np.mean(prices[-20:])
        ma60 = np.mean(prices[-60:]) if len(prices) >= 60 else np.mean(prices)
        current = prices[-1]

        reasons = []
        score = 50

        if current > ma20 > ma60:
            score = 70
            reasons.append("中长期多头趋势")
        elif current < ma20 < ma60:
            score = 30
            reasons.append("中长期空头趋势")
        elif current > ma20:
            score = 60
            reasons.append("站上20日均线")
        else:
            score = 40
            reasons.append("跌破20日均线")

        # 波动率风险
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns[-60:]) * np.sqrt(252) if len(returns) >= 60 else np.std(returns) * np.sqrt(252)
        if volatility > 0.4:
            score -= 10
            reasons.append("高波动风险")
            score = max(0, score)

        signal = self._signal_from_score(score)
        return self._score(round(score, 1), signal, reasons[:3], volatility=round(volatility, 4))

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
        elif score >= 60:
            return "buy"
        elif score >= 40:
            return "hold"
        elif score >= 20:
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
