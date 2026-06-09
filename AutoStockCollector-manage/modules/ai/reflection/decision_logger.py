from datetime import datetime
from typing import Any, Dict, Optional
from config.database import get_collection
from utils.logger import get_logger

logger = get_logger(__name__)


class DecisionLogger:
    def __init__(self):
        self.collection = get_collection("trading_memory")

    def log_decision(self, run_id: str, stock_code: str, decision: Dict[str, Any]) -> str:
        record = {
            "type": "trading_decision",
            "run_id": run_id,
            "stock_code": stock_code,
            "decision": decision.get("decision", ""),
            "bull_score": decision.get("bull_score"),
            "bear_score": decision.get("bear_score"),
            "confidence": decision.get("confidence"),
            "predicted_direction": "bullish",
            "timestamp": datetime.now().isoformat(),
            "evaluated": False,
        }
        if decision.get("bull_score", 50) > decision.get("bear_score", 50):
            record["predicted_direction"] = "bullish"
        elif decision.get("bear_score", 50) > decision.get("bull_score", 50):
            record["predicted_direction"] = "bearish"
        else:
            record["predicted_direction"] = "neutral"

        result = self.collection.insert_one(record)
        logger.info(f"Decision logged for {stock_code} (run: {run_id})")
        return str(result.inserted_id)

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
