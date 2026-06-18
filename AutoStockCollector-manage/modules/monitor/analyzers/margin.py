"""融资融券分析器 — 融资余额变化趋势、融券占比"""
from typing import Any, Dict
from core.storage.mongo_storage import MarginStorage
from utils.logger import get_logger

logger = get_logger(__name__)


class MarginAnalyzer:
    WINDOW = 20

    def __init__(self):
        self._storage = MarginStorage()

    def analyze(self, code: str) -> Dict[str, Any]:
        try:
            bare = code[2:] if code[:2] in ("SH", "SZ") else code
            candidates = [code, bare]
            records = list(self._storage.find_many(
                {"code": {"$in": candidates}},
                sort=[("date", -1)],
                limit=self.WINDOW,
            ))
            if not records:
                return {}

            # 融资余额趋势
            balances = [float(r.get("rzye", r.get("margin_balance", 0) or 0)) for r in records]
            current_balance = balances[0] if balances else 0
            avg_balance = sum(balances) / len(balances) if balances else 0
            balance_change_pct = round((current_balance - avg_balance) / avg_balance * 100, 2) if avg_balance > 0 else 0

            # 融券余量
            short_volumes = [float(r.get("rqyl", r.get("short_volume", 0) or 0)) for r in records]
            current_short = short_volumes[0] if short_volumes else 0
            avg_short = sum(short_volumes) / len(short_volumes) if short_volumes else 0
            short_change_pct = round((current_short - avg_short) / avg_short * 100, 2) if avg_short > 0 else 0

            # 融券占比
            total = current_balance + current_short * 10 if current_short > 0 else current_balance
            short_ratio = round(current_short * 10 / total * 100, 2) if total > 0 else 0

            return {
                "margin_balance": round(current_balance, 2),
                "margin_balance_change_pct": balance_change_pct,
                "short_volume": round(current_short, 2),
                "short_change_pct": short_change_pct,
                "short_ratio": short_ratio,
                "trend": "加杠杆" if balance_change_pct > 5 else "去杠杆" if balance_change_pct < -5 else "平稳",
                "short_trend": "融券增加" if short_change_pct > 10 else "融券减少" if short_change_pct < -10 else "平稳",
            }
        except Exception as e:
            logger.debug(f"Margin analyze {code} failed: {e}")
            return {}
