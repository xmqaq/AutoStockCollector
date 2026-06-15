"""
基本面分析器 — 盈利、估值、成长性
主要贡献于长期投资建议
"""
from typing import Any, Dict, Optional
from core.storage.mongo_storage import FinancialStorage, ValuationStorage, StockInfoStorage
from utils.logger import get_logger

logger = get_logger(__name__)


def _f(v) -> Optional[float]:
    """安全转为 float，字符串/None/零值 → None"""
    if v is None:
        return None
    try:
        fv = float(v)
        return fv if fv != 0 else None
    except (ValueError, TypeError):
        return None


class FundamentalAnalyzer:
    """基本面评分 → 长期信号"""

    def __init__(self):
        self._fin = FinancialStorage()
        self._val = ValuationStorage()
        self._info = StockInfoStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        val = self._val.get_by_code(code)
        fin = self._get_latest_financial(code)
        info = self._info.get_by_code(code)

        if not val and not fin:
            return self._empty_result("基本面数据不足")

        score = 50.0
        reasons = []
        details = {}

        if val:
            pe = _f(val.get("pe_dynamic")) or _f(val.get("pe"))
            pb = _f(val.get("pb"))
            roe = _f(val.get("roe"))
            details["pe"] = round(pe, 2) if pe else None
            details["pb"] = round(pb, 2) if pb else None
            details["roe"] = round(roe, 2) if roe else None

            if pe and pe < 15:
                score += 15
                reasons.append(f"PE{pe:.1f} 低估值")
            elif pe and pe <= 30:
                score += 8
                reasons.append(f"PE{pe:.1f} 估值合理")
            elif pe and pe > 60:
                score -= 10
                reasons.append(f"PE{pe:.0f} 估值偏高")

            if pb and pb < 1.5:
                score += 8
                reasons.append(f"PB{pb:.2f} 破净边缘")

            if roe and roe > 15:
                score += 10
                reasons.append(f"ROE{roe:.1f}% 盈利能力强")
            elif roe and roe > 8:
                score += 5

        if fin:
            np_ = _f(fin.get("净利润"))
            np_growth = _f(fin.get("净利润同比增长率"))
            roe_f = _f(fin.get("净资产收益率"))
            eps = _f(fin.get("基本每股收益"))

            details["net_profit"] = round(np_, 2) if np_ else None
            details["net_profit_growth"] = round(np_growth, 2) if np_growth else None
            details["roe_fin"] = round(roe_f, 2) if roe_f else None
            details["eps"] = round(eps, 2) if eps else None

            if np_growth and np_growth > 20:
                score += 15
                reasons.append(f"净利润增长{np_growth:.1f}% 高成长")
            elif np_growth and np_growth > 0:
                score += 5
                reasons.append(f"净利润正增长{np_growth:.1f}%")

            if np_growth and np_growth < -20:
                score -= 15
                reasons.append(f"净利润下滑{np_growth:.1f}%")

            if roe_f and roe_f > 15:
                score += 10
                reasons.append(f"ROE{roe_f:.1f}% 盈利优秀")

        if info:
            details["industry"] = info.get("industry") or info.get("所属行业", "")
            details["name"] = info.get("A股简称", info.get("name", ""))

        score = max(0, min(100, score))
        signal = self._signal_from_score(score)

        return {
            "score": round(score, 1),
            "signal": signal,
            "reasons": reasons[:4],
            "details": details,
        }

    def _get_latest_financial(self, code: str) -> Optional[Dict[str, Any]]:
        records = list(self._fin.find_many(
            {"code": code, "report_type": "annual"},
            sort=[("report_date", -1)],
            limit=1,
        ))
        if records:
            r = records[0]
            r.pop("_id", None)
            return r
        return None

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

    def _empty_result(self, reason: str) -> Dict:
        return {
            "score": 50.0,
            "signal": "hold",
            "reasons": [reason],
            "details": {},
        }
