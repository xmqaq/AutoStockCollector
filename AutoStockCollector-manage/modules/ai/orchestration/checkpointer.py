import json
from datetime import datetime
from utils.helpers import beijing_now
from typing import Any, Dict, Optional
from config.database import get_collection
from utils.logger import get_logger

logger = get_logger(__name__)


class MongoCheckpointer:
    def __init__(self):
        self.collection = get_collection("orchestration_checkpoints")

    def save(self, run_id: str, state: Dict[str, Any]) -> None:
        try:
            self.collection.update_one(
                {"run_id": run_id},
                {"$set": {
                    "state": state,
                    "updated_at": beijing_now().isoformat(),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Checkpointer save failed: {e}")

    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.collection.find_one({"run_id": run_id})
            if doc:
                return doc.get("state")
        except Exception as e:
            logger.warning(f"Checkpointer load failed: {e}")
        return None

    def list_runs(self, limit: int = 20) -> list:
        try:
            docs = self.collection.find(
                {}, {"_id": 0, "run_id": 1, "updated_at": 1}
            ).sort("updated_at", -1).limit(limit)
            return list(docs)
        except Exception as e:
            logger.warning(f"Checkpointer list failed: {e}")
            return []

    def delete(self, run_id: str) -> bool:
        try:
            self.collection.delete_one({"run_id": run_id})
            return True
        except Exception as e:
            logger.warning(f"Checkpointer delete failed: {e}")
            return False
