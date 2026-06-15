"""
价格预测分析器 — 支撑位/阻力位/目标价/止损价 + 仓位建议
基于波动率通道、Pivot Points 和技术指标
"""
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from core.storage.mongo_storage import KlineStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class PricePredictionAnalyzer:
    def __init__(self):
        self._kline = KlineStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        klines = list(self._kline.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=120,
        ))
        if not klines or len(klines) < 20:
            return self._empty("K线数据不足")

        closes = np.array([float(k["close"]) for k in klines], dtype=float)
        highs = np.array([float(k.get("high", k["close"])) for k in klines], dtype=float)
        lows = np.array([float(k.get("low", k["close"])) for k in klines], dtype=float)
        prices = closes[::-1]
        highs_asc = highs[::-1]
        lows_asc = lows[::-1]

        current = float(prices[-1])
        support, resistance = self._pivot_points(highs_asc, lows_asc, prices)
        bb_upper, bb_lower = self._bollinger_bands(prices)
        volatility = self._calc_volatility(prices)

        target_price = self._calc_target(current, resistance, volatility)
        stop_loss = self._calc_stop(current, support, volatility)
        buy_zone = self._calc_buy_zone(current, support, bb_lower)

        expected_return = round((target_price / current - 1) * 100, 2) if current > 0 else 0
        max_loss = round((1 - stop_loss / current) * 100, 2) if current > 0 else 0

        position_size = self._calc_position_size(volatility, expected_return, max_loss)
        risk_level = self._risk_level(volatility, max_loss)
        trading_advice = self._trading_advice(
            current, target_price, stop_loss, buy_zone[0], buy_zone[1],
            support, resistance, expected_return, max_loss, risk_level,
        )

        return {
            "current_price": round(current, 2),
            "support": round(float(support), 2),
            "resistance": round(float(resistance), 2),
            "bollinger_upper": round(float(bb_upper), 2),
            "bollinger_lower": round(float(bb_lower), 2),
            "target_price": round(float(target_price), 2),
            "stop_loss": round(float(stop_loss), 2),
            "buy_zone_low": round(float(buy_zone[0]), 2),
            "buy_zone_high": round(float(buy_zone[1]), 2),
            "expected_return": expected_return,
            "max_loss": max_loss,
            "volatility": round(float(volatility), 4),
            "position_size": round(float(position_size), 2),
            "risk_level": risk_level,
            "trading_advice": trading_advice,
        }

    def _pivot_points(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Tuple[float, float]:
        """计算支撑位和阻力位（基于最近20根K线）"""
        n = min(20, len(highs))
        recent_high = float(np.max(highs[-n:]))
        recent_low = float(np.min(lows[-n:]))
        recent_close = float(closes[-1])
        pivot = (recent_high + recent_low + recent_close) / 3
        resistance = 2 * pivot - recent_low
        support = 2 * pivot - recent_high
        return support, resistance

    def _bollinger_bands(self, prices: np.ndarray, window: int = 20, n_std: float = 2.0) -> Tuple[float, float]:
        """布林带上下轨"""
        if len(prices) < window:
            window = len(prices)
        ma = np.mean(prices[-window:])
        std = np.std(prices[-window:])
        upper = ma + n_std * std
        lower = ma - n_std * std
        return upper, lower

    def _calc_volatility(self, prices: np.ndarray) -> float:
        """年化波动率"""
        if len(prices) < 2:
            return 0.3
        returns = np.diff(prices) / prices[:-1]
        return float(np.std(returns[-60:]) * np.sqrt(252)) if len(returns) >= 60 else float(np.std(returns) * np.sqrt(252))

    def _calc_target(self, current: float, resistance: float, volatility: float) -> float:
        """短期目标价 = 阻力位 + 波动率调整"""
        target = resistance * (1 + volatility * 0.5)
        return max(target, current * 1.02)

    def _calc_stop(self, current: float, support: float, volatility: float) -> float:
        """止损价 = support - 波动率缓冲，或 -7% 绝对值（取较小值）"""
        vol_stop = support * (1 - volatility * 0.3)
        hard_stop = current * 0.93
        return max(vol_stop, hard_stop)

    def _calc_buy_zone(self, current: float, support: float, bb_lower: float) -> Tuple[float, float]:
        """买入区间 = support~bb_lower 之间"""
        low = min(support, bb_lower)
        high = max(support, bb_lower)
        if low >= current:
            return (current * 0.97, current * 0.99)
        return (round(low, 2), round(high, 2))

    def _calc_position_size(self, volatility: float, expected_return: float, max_loss: float) -> float:
        """建议仓位比例 0-1。基于凯利公式简化版"""
        if max_loss <= 0:
            return 0.05
        kelly = expected_return / max_loss * 0.5
        kelly = max(0.02, min(0.2, kelly))  # 单票仓位 2%-20%
        # 波动率调整
        if volatility > 0.5:
            kelly *= 0.5
        elif volatility > 0.3:
            kelly *= 0.75
        return max(0.01, kelly)

    def _risk_level(self, volatility: float, max_loss: float) -> str:
        if volatility > 0.5 or max_loss > 10:
            return "高"
        elif volatility > 0.3 or max_loss > 5:
            return "中"
        return "低"

    def _trading_advice(
        self, current: float, target: float, stop: float,
        buy_low: float, buy_high: float,
        support: float, resistance: float,
        expected_return: float, max_loss: float, risk_level: str,
    ) -> Dict[str, Any]:
        """生成可执行的买卖点建议"""
        rr_ratio = round(expected_return / max_loss, 2) if max_loss > 0 else 0

        # 判断当前价格相对位置
        if buy_low <= current <= buy_high:
            pos_text = "在买入区内"
        elif current < buy_low:
            pos_text = "低于买入区"
        else:
            pos_text = "高于买入区"

        # 距离目标价
        if current >= target:
            dist_text = "已到目标价"
        elif current >= target * 0.95:
            dist_text = "接近目标价"
        else:
            pct = round((target / current - 1) * 100, 1)
            dist_text = f"距目标还有+{pct}%"

        # 决策逻辑
        if current >= target:
            action = "卖出"
            action_signal = "sell"
            entry_reason = "价格已达到目标，建议止盈"
            exit_reason = f"止盈价{target:.2f}已到，锁定利润{expected_return:.1f}%"
        elif current <= stop * 1.03:
            action = "卖出"
            action_signal = "sell"
            entry_reason = f"价格接近止损{stop:.2f}，建议离场"
            exit_reason = f"止损价{stop:.2f}，最大亏损{max_loss:.1f}%"
        elif buy_low <= current <= buy_high and expected_return > max_loss * 1.5:
            action = "买入"
            action_signal = "buy"
            entry_reason = f"当前价格{current:.2f}在买入区({buy_low:.2f}~{buy_high:.2f})，盈亏比{rr_ratio}，建议建仓"
            exit_reason = f"止盈{target:.2f}(+{expected_return:.1f}%) / 止损{stop:.2f}(-{max_loss:.1f}%)"
        elif current < buy_low:
            action = "观望"
            action_signal = "watch"
            entry_reason = f"当前价格{current:.2f}低于买入区，等待回调至{buy_low:.2f}~{buy_high:.2f}"
            exit_reason = "等待价格进入买入区再考虑建仓"
        else:
            action = "持有"
            action_signal = "hold"
            entry_reason = f"当前在买入区之上，已持仓者可继续持有至{target:.2f}"
            exit_reason = f"不跌破止损{stop:.2f}则持有，目标{target:.2f}(+{expected_return:.1f}%)"

        return {
            "action": action,
            "action_signal": action_signal,
            "entry_reason": entry_reason,
            "exit_reason": exit_reason,
            "entry_price_range": {"low": round(buy_low, 2), "high": round(buy_high, 2)},
            "take_profit": round(target, 2),
            "stop_loss": round(stop, 2),
            "expected_return": expected_return,
            "max_loss": max_loss,
            "risk_reward_ratio": rr_ratio,
            "current_position": pos_text,
            "distance_to_target": dist_text,
        }

    def _empty(self, reason: str) -> Dict:
        return {
            "current_price": 0,
            "support": 0,
            "resistance": 0,
            "bollinger_upper": 0,
            "bollinger_lower": 0,
            "target_price": 0,
            "stop_loss": 0,
            "buy_zone_low": 0,
            "buy_zone_high": 0,
            "expected_return": 0,
            "max_loss": 0,
            "volatility": 0,
            "position_size": 0,
            "risk_level": "未知",
            "error": reason,
            "trading_advice": {
                "action": "数据不足",
                "action_signal": "unknown",
                "entry_reason": reason,
                "exit_reason": reason,
                "entry_price_range": {"low": 0, "high": 0},
                "take_profit": 0, "stop_loss": 0,
                "expected_return": 0, "max_loss": 0,
                "risk_reward_ratio": 0,
                "current_position": "未知",
                "distance_to_target": "未知",
            },
        }
