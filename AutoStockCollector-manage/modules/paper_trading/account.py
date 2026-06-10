from datetime import datetime
from utils.helpers import beijing_now
from typing import Optional, Dict, Any


class PaperAccount:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._col = db["paper_account"]
        self._db = db

    def get(self, user_id: str = "default") -> Optional[Dict[str, Any]]:
        doc = self._col.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
        return doc

    def init(self, initial_capital: float, user_id: str = "default") -> Dict[str, Any]:
        self._db["trade_records"].delete_many({"user_id": user_id})
        now = beijing_now().isoformat()
        doc = {
            "user_id": user_id,
            "initial_capital": initial_capital,
            "cash_balance": initial_capital,
            "created_at": now,
            "updated_at": now,
        }
        self._col.replace_one({"user_id": user_id}, doc, upsert=True)
        return doc

    def update_cash(self, user_id: str, new_balance: float) -> None:
        self._col.update_one(
            {"user_id": user_id},
            {"$set": {"cash_balance": new_balance, "updated_at": beijing_now().isoformat()}},
        )
