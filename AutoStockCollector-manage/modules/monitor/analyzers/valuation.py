"""
估值面分析器 — PE/PB 行业调整评分
参考量化选股和AI Foundation Factors 估值评分体系
"""
from typing import Any, Dict, Optional, Tuple
from core.storage.mongo_storage import ValuationStorage, StockInfoStorage
from utils.logger import get_logger

logger = get_logger(__name__)

_FINANCE_KEYWORDS = ["金融", "地产", "银行", "保险", "证券", "房地产", "能源"]
_HIGH_PE_KEYWORDS = ["科技", "医药", "消费", "软件", "医疗", "生物", "半导体", "互联网", "电子", "信息", "人工智能", "芯片", "创新"]

def _f(v) -> Optional[float]:
    if v is None: return None
    try:
        fv = float(v)
        return fv if fv != 0 else None
    except (ValueError, TypeError):
        return None

class ValuationAnalyzer:
    def __init__(self):
        self._val = ValuationStorage()
        self._info = StockInfoStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        val = self._val.get_by_code(code)
        info = self._info.get_by_code(code)
        industry = (info.get("industry") or info.get("所属行业", "") or "")

        if not val:
            return self._empty_result("估值数据不足")

        pe = _f(val.get("pe_dynamic")) or _f(val.get("pe"))
        pb = _f(val.get("pb"))
        ps = _f(val.get("ps"))
        pcf = _f(val.get("pcf"))

        pe_score, pe_detail = self._score_pe(pe, industry)
        pb_score, pb_detail = self._score_pb(pb)
        ps_score = self._score_ps(ps)
        pcf_score = self._score_pcf(pcf)

        total = pe_score + pb_score + ps_score + pcf_score
        total = max(10, min(90, total))

        reasons = []
        if pe_detail: reasons.append(pe_detail)
        if pb_detail: reasons.append(pb_detail)

        signal = self._signal_from_score(total)

        return {
            "score": round(total, 1),
            "signal": signal,
            "reasons": reasons[:3],
            "details": {
                "pe": round(pe, 2) if pe else None,
                "pb": round(pb, 2) if pb else None,
                "ps": round(ps, 2) if ps else None,
                "pcf": round(pcf, 2) if pcf else None,
                "industry": industry,
                "pe_score": round(pe_score, 1),
                "pb_score": round(pb_score, 1),
                "industry_adj": self._industry_type(industry),
            },
        }

    def _score_pe(self, pe: Optional[float], industry: str) -> Tuple[float, str]:
        if pe is None or pe <= 0:
            return 25, ""

        is_finance = any(kw in industry for kw in _FINANCE_KEYWORDS)
        is_high_pe = any(kw in industry for kw in _HIGH_PE_KEYWORDS)

        if is_finance:
            if pe <= 8:  return 40, f"PE{pe:.1f} 金融低估"
            elif pe <= 15: return 36, f"PE{pe:.1f} 金融合理偏低"
            elif pe <= 25: return 26, ""
            else: return 14, f"PE{pe:.0f} 金融偏高"
        elif is_high_pe:
            if pe <= 25: return 40, f"PE{pe:.1f} 成长股低估"
            elif pe <= 40: return 34, f"PE{pe:.1f} 成长股合理"
            elif pe <= 70: return 22, ""
            else: return 10, f"PE{pe:.0f} 成长股偏高"
        else:
            if pe <= 15: return 40, f"PE{pe:.1f} 低估值"
            elif pe <= 25: return 34, f"PE{pe:.1f} 估值合理"
            elif pe <= 40: return 26, ""
            elif pe <= 70: return 14, f"PE{pe:.0f} 估值偏高"
            else: return 6, f"PE{pe:.0f} 高估值"

    def _score_pb(self, pb: Optional[float]) -> Tuple[float, str]:
        if pb is None or pb <= 0:
            return 20, ""
        if pb <= 1: return 35, f"PB{pb:.2f} 破净"
        elif pb <= 2: return 30, f"PB{pb:.2f} 低估"
        elif pb <= 4: return 22, ""
        elif pb <= 8: return 12, ""
        else: return 5, f"PB{pb:.2f} 偏高"

    def _score_ps(self, ps: Optional[float]) -> float:
        if ps is None or ps <= 0:
            return 10
        if ps <= 1: return 15
        elif ps <= 5: return 13
        elif ps <= 10: return 10
        else: return 5

    def _score_pcf(self, pcf: Optional[float]) -> float:
        if pcf is None or pcf <= 0:
            return 5
        if pcf <= 10: return 10
        elif pcf <= 20: return 8
        else: return 5

    def _industry_type(self, industry: str) -> str:
        if any(kw in industry for kw in _FINANCE_KEYWORDS): return "金融"
        if any(kw in industry for kw in _HIGH_PE_KEYWORDS): return "成长"
        return "传统"

    def _signal_from_score(self, score: float) -> str:
        if score >= 75: return "strong_buy"
        elif score >= 62: return "buy"
        elif score >= 38: return "hold"
        elif score >= 25: return "sell"
        else: return "strong_sell"

    def _empty_result(self, reason: str) -> Dict:
        return {
            "score": 50.0, "signal": "hold",
            "reasons": [reason],
            "details": {"industry": "", "pe_score": 0, "pb_score": 0, "industry_adj": ""},
        }
