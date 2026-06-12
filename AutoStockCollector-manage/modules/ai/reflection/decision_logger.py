from utils.helpers import beijing_now
from typing import Any, Dict, Optional
from config.database import get_collection
from utils.logger import get_logger

logger = get_logger(__name__)


class DecisionLogger:
    def __init__(self, collection=None):
        self.collection = collection if collection is not None else get_collection("trading_memory")

    def log_decision(self, run_id: str, stock_code: str, decision: Dict[str, Any]) -> str:
        date_key = beijing_now().strftime("%Y-%m-%d")
        record = {
            "type": "trading_decision",
            "run_id": run_id,
            "stock_code": stock_code,
            "date_key": date_key,
            "decision": decision.get("decision", ""),
            "bull_score": decision.get("bull_score"),
            "bear_score": decision.get("bear_score"),
            "confidence": decision.get("confidence"),
            "timestamp": beijing_now().isoformat(),
            "evaluated": False,
        }
        if decision.get("bull_score", 50) > decision.get("bear_score", 50):
            record["predicted_direction"] = "bullish"
        elif decision.get("bear_score", 50) > decision.get("bull_score", 50):
            record["predicted_direction"] = "bearish"
        else:
            record["predicted_direction"] = "neutral"

        # 同股同日只保留最后一条,反复生成报告不刷重复决策
        result = self.collection.update_one(
            {"type": "trading_decision", "stock_code": stock_code, "date_key": date_key},
            {"$set": record},
            upsert=True,
        )
        logger.info(f"Decision logged for {stock_code} (run: {run_id})")
        return str(getattr(result, "upserted_id", "") or "updated")

    def get_pending_evaluations(self) -> list:
        return list(self.collection.find(
            {"type": "trading_decision", "evaluated": False},
            sort=[("timestamp", -1)],
            limit=50,
        ))

    def get_history(self, stock_code: str, limit: int = 10) -> list:
        return list(self.collection.find(
            {"type": "trading_decision", "stock_code": stock_code},
            sort=[("timestamp", -1)],
            limit=limit,
        ))
