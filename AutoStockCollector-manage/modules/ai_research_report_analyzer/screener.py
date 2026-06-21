"""标的筛选 & 长线打分。

过滤规则：
- 排除 ST、*ST、退市
- ROE > 8%
- 营收增速 > 0
- 非极端估值（PE < 100）
"""
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_code(code: str) -> str:
    """为 6 位纯数字代码添加交易所前缀。"""
    if len(code) >= 8:
        return code
    if code.startswith(("SH", "sh", "SZ", "sz")):
        return code.upper()
    if code.startswith(("6", "9", "7")):
        return f"SH{code}"
    return f"SZ{code}"


class Screener:
    """基本面筛选器。"""

    def __init__(self):
        self._db = DatabaseConfig.get_database()

    def filter(self, candidates: List[Dict]) -> List[Dict]:
        """基本面过滤。"""
        if not candidates:
            return []

        codes = [c["code"] for c in candidates if c.get("code")]
        if not codes:
            return candidates

        norm_codes = [_normalize_code(c) for c in codes]

        stock_infos = self._fetch_stock_info(norm_codes)
        financials = self._fetch_financials(norm_codes)
        valuations = self._fetch_valuations(norm_codes)

        results = []
        for cand in candidates:
            code = cand["code"]
            norm = _normalize_code(code)
            info = stock_infos.get(norm, stock_infos.get(code, {}))
            fin = financials.get(norm, financials.get(code, {}))
            val = valuations.get(norm, valuations.get(code, {}))

            if self._is_st_star(info, cand):
                logger.debug(f"[Screener] {code} excluded: ST/*ST")
                continue
            if not self._pass_roe(fin, val):
                logger.debug(f"[Screener] {code} excluded: ROE too low")
                continue
            if not self._pass_revenue_growth(fin):
                logger.debug(f"[Screener] {code} excluded: revenue decline")
                continue
            if not self._pass_valuation(val):
                logger.debug(f"[Screener] {code} excluded: extreme valuation")
                continue

            cand["pe"] = val.get("pe_dynamic") or val.get("pe") or 0
            cand["pb"] = val.get("pb") or 0
            roe_val = val.get("roe")
            roe_fin = fin.get("净资产收益率")
            cand["roe"] = self._parse_pct(roe_val) or self._parse_pct(roe_fin) or 0
            cand["industry"] = info.get("所属行业", "")
            cand["market_cap"] = val.get("total_mv", 0)
            cand["name"] = cand.get("name") or info.get("A股简称", "")
            results.append(cand)

        logger.info(
            f"[Screener] Filtered {len(results)}/{len(candidates)} candidates"
        )
        return results

    def score(self, candidates: List[Dict]) -> List[Dict]:
        """长线综合打分（0-100）。"""
        for c in candidates:
            score = 50

            roe = float(c.get("roe", 0) or 0)
            pe = float(c.get("pe", 0) or 0)
            mention = int(c.get("mention_count", 1))
            confidence = int(c.get("confidence", 3))

            if roe > 15:
                score += 20
            elif roe > 10:
                score += 12
            elif roe > 5:
                score += 5
            elif roe <= 0:
                score -= 15

            if 5 < pe < 20:
                score += 10
            elif 20 <= pe < 40:
                score += 5
            elif pe > 80 or pe <= 0:
                score -= 5

            score += min(mention * 5, 15)
            score += (confidence - 3) * 3

            c["score"] = max(0, min(100, score))
            c["score_label"] = self._label(score)

        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates

    def _fetch_stock_info(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取股票基本信息。"""
        try:
            docs = self._db["stock_info"].find(
                {"code": {"$in": codes}},
                {"code": 1, "A股简称": 1, "所属行业": 1},
            )
            return {d.get("code", ""): d for d in docs}
        except Exception as e:
            logger.warning(f"[Screener] fetch_stock_info error: {e}")
            return {}

    def _fetch_financials(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取最近一期财务数据。"""
        try:
            pipeline = [
                {"$match": {"code": {"$in": codes}}},
                {"$sort": {"report_date": -1}},
                {"$group": {
                    "_id": "$code",
                    "doc": {"$first": "$$ROOT"},
                }},
            ]
            docs = self._db["financial"].aggregate(pipeline)
            return {d["_id"]: d["doc"] for d in docs}
        except Exception as e:
            logger.warning(f"[Screener] fetch_financials error: {e}")
            return {}

    def _fetch_valuations(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取估值数据。"""
        try:
            docs = self._db["stock_valuation"].find(
                {"code": {"$in": codes}},
            )
            return {d.get("code", ""): d for d in docs}
        except Exception as e:
            logger.warning(f"[Screener] fetch_valuations error: {e}")
            return {}

    @staticmethod
    def _is_st_star(info: Dict, cand: Dict) -> bool:
        name = str(info.get("A股简称", cand.get("name", "")))
        if "ST" in name or "*ST" in name or "退市" in name:
            return True
        return False

    @staticmethod
    def _parse_pct(val) -> Optional[float]:
        """将百分比字符串/数值转为浮点数。"""
        if val is None:
            return None
        try:
            s = str(val).strip().replace("%", "").replace("％", "")
            return float(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _pass_roe(fin: Dict, val: Dict) -> bool:
        roe = Screener._parse_pct(val.get("roe")) or Screener._parse_pct(fin.get("净资产收益率"))
        if roe is None:
            return True
        return roe > 5

    @staticmethod
    def _pass_revenue_growth(fin: Dict) -> bool:
        growth = fin.get("营业总收入同比增长率")
        if growth is None:
            return True
        try:
            return float(growth) > 0
        except (ValueError, TypeError):
            return True

    @staticmethod
    def _pass_valuation(val: Dict) -> bool:
        pe = val.get("pe_dynamic") or val.get("pe")
        if pe is None:
            return True
        try:
            pe_f = float(pe)
            if pe_f <= 0:
                return True
            return pe_f < 200
        except (ValueError, TypeError):
            return True

    @staticmethod
    def _label(score: float) -> str:
        if score >= 80:
            return "strong_buy"
        elif score >= 65:
            return "buy"
        elif score >= 45:
            return "hold"
        elif score >= 30:
            return "sell"
        return "strong_sell"
