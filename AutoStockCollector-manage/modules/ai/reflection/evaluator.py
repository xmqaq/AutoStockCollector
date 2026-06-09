from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from config.database import get_collection
from utils.logger import get_logger

logger = get_logger(__name__)


class ReflectionEvaluator:
    def __init__(self):
        self.collection = get_collection("trading_memory")

    def evaluate(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        stock_code = record.get("stock_code", "")
        timestamp_str = record.get("timestamp", "")
        try:
            decision_time = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            return None

        now = datetime.now()
        days_elapsed = (now - decision_time).days
        if days_elapsed < 1:
            return None

        try:
            from core.storage.mongo_storage import KlineStorage
            storage = KlineStorage()
            klines = list(storage.find_many(
                {"code": stock_code},
                sort=[("date", -1)],
                limit=1,
            ))
            if not klines:
                return None
            current_price = float(klines[0].get("close", 0))

            klines_at_decision = list(storage.find_many(
                {"code": stock_code},
                sort=[("date", -1)],
                limit=days_elapsed + 5,
            ))
            decision_price = None
            for k in reversed(klines_at_decision):
                if k.get("date", "") <= timestamp_str[:10]:
                    decision_price = float(k.get("close", 0))
                    break
            if not decision_price:
                decision_price = float(klines_at_decision[-1].get("close", 0)) if klines_at_decision else current_price

            realized_return = (current_price - decision_price) / decision_price * 100 if decision_price else 0
            predicted = record.get("predicted_direction", "neutral")

            accuracy = "correct"
            if predicted == "bullish" and realized_return < -2:
                accuracy = "wrong"
            elif predicted == "bearish" and realized_return > 2:
                accuracy = "wrong"
            elif predicted == "neutral" and abs(realized_return) > 3:
                accuracy = "partial"

            reflection = {
                "stock_code": stock_code,
                "decision_time": timestamp_str,
                "decision_price": round(decision_price, 2) if decision_price else None,
                "current_price": round(current_price, 2),
                "realized_return": round(realized_return, 2),
                "days_elapsed": days_elapsed,
                "predicted_direction": predicted,
                "accuracy": accuracy,
                "summary": (
                    f"{days_elapsed}天前预测{predicted}，实际收益{realized_return:+.2f}%，判断{'正确' if accuracy == 'correct' else '部分正确' if accuracy == 'partial' else '错误'}"
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
