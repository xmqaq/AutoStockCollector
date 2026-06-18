"""涨停/跌停检测 — 基于 kline 数据判断是否涨停/跌停及连板天数"""
from typing import Any, Dict, Optional
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class LimitUpAnalyzer:
    def analyze(self, code: str) -> Dict[str, Any]:
        try:
            db = DatabaseConfig.get_database()
            prefix = code[:2]
            bare = code[2:] if prefix in ("SH", "SZ") else code
            candidates = [code, f"SH{bare}", f"SZ{bare}"] if bare != code else [code]
            klines = list(db["kline"].find(
                {"code": {"$in": candidates}},
                sort=[("date", -1)],
                limit=10,
            ))
            if not klines:
                return {}

            result = {
                "is_limit_up": False,
                "is_limit_down": False,
                "consecutive_limit_days": 0,
                "limit_type": None,
            }

            consecutive = 0
            for i, k in enumerate(klines):
                change = self._calc_change(k)
                if change is None:
                    break
                is_limit = change >= 9.8
                is_limit_dn = change <= -9.8
                if i == 0:
                    result["is_limit_up"] = is_limit
                    result["is_limit_down"] = is_limit_dn
                    result["limit_type"] = "涨停" if is_limit else ("跌停" if is_limit_dn else None)
                if is_limit or is_limit_dn:
                    consecutive += 1
                else:
                    break
            result["consecutive_limit_days"] = consecutive

            k0 = klines[0]
            result["change_pct"] = self._calc_change(k0)
            result["turnover_rate"] = float(k0.get("turnover", k0.get("turnover_rate", 0) or 0))
            result["volume_ratio"] = self._calc_volume_ratio(klines)
            result["amount"] = float(k0.get("amount", 0) or 0)
            return result
        except Exception as e:
            logger.debug(f"LimitUp analyze {code} failed: {e}")
            return {}

    def _calc_change(self, kline: Dict) -> Optional[float]:
        close = float(kline.get("close", kline.get("收盘价", 0) or 0))
        pre = float(kline.get("pre_close", kline.get("昨收", 0) or 0))
        if pre and pre > 0 and close:
            return round((close - pre) / pre * 100, 2)
        return None

    def _calc_volume_ratio(self, klines: list) -> float:
        if len(klines) < 2:
            return 1.0
        cur_vol = float(klines[0].get("volume", klines[0].get("成交量", 0) or 0))
        avg_vol = sum(
            float(k.get("volume", k.get("成交量", 0) or 0)) for k in klines[1:6]
        ) / min(len(klines[1:6]), 5)
        return round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
