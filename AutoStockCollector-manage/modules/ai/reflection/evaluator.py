from datetime import datetime, timedelta
from utils.helpers import beijing_now
from typing import Any, Dict, Optional
from config.database import get_collection
from utils.logger import get_logger

logger = get_logger(__name__)


def _default_kline_loader(code: str, limit: int) -> list:
    from core.storage.mongo_storage import KlineStorage
    return list(KlineStorage().find_many(
        {"code": code}, sort=[("date", -1)], limit=limit)) or []


class ReflectionEvaluator:
    _INDEX_CODES = ("sh000001", "SH000001")

    def __init__(self, collection=None, kline_loader=None):
        self.collection = collection if collection is not None else get_collection("trading_memory")
        self.kline_loader = kline_loader or _default_kline_loader

    def _index_return(self, decision_day: str) -> Optional[float]:
        """上证指数 决策日→现在 的收益率(%),无数据返回 None。"""
        klines = None
        for icode in self._INDEX_CODES:
            klines = self.kline_loader(icode, 300)
            if klines:
                break
        if not klines:
            return None
        try:
            cur = float(klines[0].get("close", 0))
            dec = None
            for k in klines:
                if str(k.get("date", ""))[:10] <= decision_day:
                    close_val = k.get("close")
                    if close_val is None:
                        continue
                    dec = float(close_val)
                    break
            if not dec or not cur:
                return None
            return (cur - dec) / dec * 100
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _judge(predicted: str, x: float, thr: float, thr_neutral: float) -> str:
        """x: 超额或绝对收益。三态判定。"""
        if predicted == "bullish":
            return "correct" if x >= thr else "wrong" if x <= -thr else "partial"
        if predicted == "bearish":
            return "correct" if x <= -thr else "wrong" if x >= thr else "partial"
        return "correct" if abs(x) <= thr_neutral else "partial"

    def evaluate(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stock_code = record.get("stock_code", "")
        timestamp_str = record.get("timestamp", "")
        try:
            decision_time = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None

        now = beijing_now()
        days_elapsed = (now - decision_time).days
        if days_elapsed < 1:
            return None

        try:
            klines = self.kline_loader(stock_code, days_elapsed + 10)
            if not klines:
                return None
            current_price = float(klines[0].get("close", 0))

            decision_day = timestamp_str[:10]
            decision_price = None
            for k in klines:  # 降序:从最新往回,首个 date<=决策日 即最接近决策日的一根
                if str(k.get("date", ""))[:10] <= decision_day:
                    close_val = k.get("close")
                    if close_val is None:
                        continue
                    decision_price = float(close_val)
                    break
            if decision_price is None:
                return None

            realized_return = (current_price - decision_price) / decision_price * 100 if decision_price else 0
            predicted = record.get("predicted_direction", "neutral")

            bench = self._index_return(decision_day)
            if bench is not None:
                excess = realized_return - bench
                accuracy = self._judge(predicted, excess, 2.0, 3.0)
                benchmark_mode = "index"
            else:
                excess = None
                thr = 2.0 if days_elapsed <= 3 else 4.0 if days_elapsed <= 10 else 6.0
                accuracy = self._judge(predicted, realized_return, thr, 3.0)
                benchmark_mode = "threshold"

            reflection = {
                "stock_code": stock_code,
                "decision_time": timestamp_str,
                "decision_price": round(decision_price, 2) if decision_price else None,
                "current_price": round(current_price, 2),
                "realized_return": round(realized_return, 2),
                "days_elapsed": days_elapsed,
                "predicted_direction": predicted,
                "accuracy": accuracy,
                "benchmark": benchmark_mode,
                "benchmark_return": round(bench, 2) if bench is not None else None,
                "excess_return": round(excess, 2) if excess is not None else None,
                "summary": (
                    f"{days_elapsed}天前预测{predicted},实际{realized_return:+.2f}%"
                    + (f"(同期上证{bench:+.2f}%,超额{excess:+.2f}%)" if bench is not None else "")
                    + f",判断{'正确' if accuracy == 'correct' else '部分正确' if accuracy == 'partial' else '错误'}"
                ),
            }

            self.collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"evaluated": True, "reflection": reflection}},
            )
            return reflection

        except Exception as e:
            logger.warning(f"Reflection evaluation failed for {stock_code}: {e}")
            return None

    def get_reflection_for_stock(self, stock_code: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one(
            {"type": "trading_decision", "stock_code": stock_code, "evaluated": True,
             "reflection": {"$exists": True}},
            sort=[("timestamp", -1)],
        )
        if doc:
            return doc.get("reflection")
        return None
