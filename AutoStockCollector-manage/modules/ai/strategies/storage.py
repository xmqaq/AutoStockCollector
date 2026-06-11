from typing import Any, Dict, List, Optional
from datetime import datetime
from core.storage.mongo_storage import MongoStorage


class StrategyStorage(MongoStorage):
    def __init__(self):
        super().__init__("strategy_rules")
        self.create_index([("type", 1), ("enabled", 1)])
        self.create_index([("name", 1)], unique=True)

    def list_by_type(self, strategy_type: str, enabled_only: bool = False) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"type": strategy_type}
        if enabled_only:
            query["enabled"] = True
        return list(self.find_many(query, sort=[("updated_at", -1)]))

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"name": name})

    def upsert_strategy(self, doc: Dict[str, Any]) -> str:
        now = datetime.now()
        doc["updated_at"] = now
        if "_id" not in doc:
            doc["created_at"] = now
            oid = self.insert_one(doc)
            return oid
        else:
            from bson import ObjectId
            oid = doc.pop("_id")
            if isinstance(oid, str):
                oid = ObjectId(oid)
            self.update_one({"_id": oid}, {"$set": doc})
            return str(oid)
