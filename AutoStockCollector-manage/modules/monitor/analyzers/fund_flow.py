"""
主力资金流量分析 — 生成短线和长线资金面评分与信号
- 短期: 近3-5日主力净流入趋势、日内动量
- 长期: 近20-60日主力资金积累/派发趋势
"""
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from core.storage.mongo_storage import FundFlowStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class FundFlowAnalyzer:
    SHORT_WINDOW = 5
    LONG_WINDOW = 60

    def __init__(self):
        self._storage = FundFlowStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        flows = self._get_flows(code)
        if not flows:
            return self._empty_result("暂无资金流向数据")

        short = self._analyze_short_term(flows)
        long_ = self._analyze_long_term(flows)
        combined = self._combine(short, long_)
        return {
            "short_term": short,
            "long_term": long_,
            **combined,
            "data_points": len(flows),
        }

    def _get_flows(self, code: str) -> List[Dict[str, Any]]:
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        candidates = [code]
        if code == bare:
            prefix = "SH" if bare.startswith(("6", "9")) else "SZ"
            candidates.append(f"{prefix}{bare}")
        records = self._storage.find_many(
            {"code": {"$in": candidates}},
            sort=[("date", -1)],
            limit=self.LONG_WINDOW,
        )
        result = []
        for r in records:
            r.pop("_id", None)
            r.pop("_updated_at", None)
            result.append(r)
        return result

    def _analyze_short_term(self, flows: List[Dict]) -> Dict[str, Any]:
        recent = flows[:self.SHORT_WINDOW]
        if not recent:
            return self._empty_sub("数据不足")

        net_inflows = [float(f.get("main_net_inflow", 0)) for f in recent]
        avg_net = np.mean(net_inflows)
        total_net = np.sum(net_inflows)
        consecutive_days = self._count_consecutive(net_inflows)

        # 趋势方向: 最近日净流入 vs 前几日均值
        if len(net_inflows) >= 2:
            trend = "流入" if net_inflows[0] > net_inflows[-1] else "流出"
            trend_strength = abs(net_inflows[0] - np.mean(net_inflows[1:]))
        else:
            trend = "中性"
            trend_strength = 0.0

        score = self._score_from_net(total_net, avg_net, consecutive_days, is_short=True)
        signal = self._signal_from_score(score)

        reasons = []
        if total_net > 0:
            reasons.append(f"近{self.SHORT_WINDOW}日主力净流入{_fmt(total_net)}")
        else:
            reasons.append(f"近{self.SHORT_WINDOW}日主力净流出{_fmt(abs(total_net))}")
        if consecutive_days >= 3:
            reasons.append(f"连续{consecutive_days}日净流入")
        elif consecutive_days <= -3:
            reasons.append(f"连续{abs(consecutive_days)}日净流出")
        if trend != "中性":
            reasons.append(f"趋势{trend}")

        return {
            "score": round(score, 1),
            "signal": signal,
            "total_net": round(total_net, 2),
            "avg_daily_net": round(avg_net, 2),
            "consecutive_days": consecutive_days,
            "trend": trend,
            "reasons": reasons[:3],
        }

    def _analyze_long_term(self, flows: List[Dict]) -> Dict[str, Any]:
        window = flows[:self.LONG_WINDOW]
        if len(window) < 10:
            return self._empty_sub("长期数据不足")

        net_inflows = [float(f.get("main_net_inflow", 0)) for f in window]
        total_net = np.sum(net_inflows)
        avg_net = np.mean(net_inflows)
        std_net = np.std(net_inflows) if len(net_inflows) > 1 else 0

        # 分阶段对比: 近期 vs 远期
        mid = len(window) // 2
        recent_half = np.mean(net_inflows[:mid]) if mid > 0 else 0
        older_half = np.mean(net_inflows[mid:]) if len(net_inflows) > mid else 0

        accumulation = recent_half > older_half  # 近期流入更强 = 正在积累
        div_ratio = (recent_half - older_half) / (abs(older_half) + 1)

        score = self._score_from_net(total_net, avg_net, 0, is_short=False)
        score += 10 if accumulation else -10  # 趋势加分
        score = max(0, min(100, score))

        signal = self._signal_from_score(score)

        reasons = []
        if total_net > 0:
            reasons.append(f"近{self.LONG_WINDOW}日主力累计净流入{_fmt(total_net)}")
        else:
            reasons.append(f"近{self.LONG_WINDOW}日主力累计净流出{_fmt(abs(total_net))}")
        if accumulation:
            reasons.append("近期资金加速流入，呈积累态势")
        else:
            reasons.append("近期资金流入放缓，有派发迹象")
        if std_net > 1:
            reasons.append("资金波动较大")

        return {
            "score": round(score, 1),
            "signal": signal,
            "total_net": round(total_net, 2),
            "avg_daily_net": round(avg_net, 2),
            "accumulation": accumulation,
            "reasons": reasons[:3],
        }

    def _count_consecutive(self, net_inflows: List[float]) -> int:
        """连续正天数 (负数为连续流出)"""
        count = 0
        for v in net_inflows:
            if v > 0:
                count += 1
            elif v < 0:
                count -= 1
            else:
                break
        return count

    def _score_from_net(self, total: float, avg: float, consec: int, is_short: bool) -> float:
        """根据净流入量打分 0-100"""
        scale = 1e7 if is_short else 5e7
        base = 50 + (total / scale) * 20
        base += consec * 3  # 连续性加分
        return max(0, min(100, base))

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
        """综合短/长期资金面结论"""
        score = short.get("score", 50) * 0.5 + long_.get("score", 50) * 0.5
        signal = self._signal_from_score(score)
        return {"composite_score": round(score, 1), "composite_signal": signal}

    def _empty_result(self, reason: str) -> Dict:
        return {
            "short_term": self._empty_sub(reason),
            "long_term": self._empty_sub(reason),
            "composite_score": 50.0,
            "composite_signal": "hold",
            "data_points": 0,
        }

    def _empty_sub(self, reason: str) -> Dict:
        return {
            "score": 50.0,
            "signal": "hold",
            "total_net": 0.0,
            "avg_daily_net": 0.0,
            "consecutive_days": 0,
            "trend": "中性",
            "accumulation": False,
            "reasons": [reason],
        }


def _fmt(v: float) -> str:
    """自动格式化金额: 万/亿"""
    av = abs(v)
    if av >= 1e8:
        return f"{v/1e8:.2f}亿"
    if av >= 1e4:
        return f"{v/1e4:.0f}万"
    return f"{v:.0f}"
