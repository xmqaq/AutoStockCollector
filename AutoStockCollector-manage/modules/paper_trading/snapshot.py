from datetime import datetime
from typing import Any, Dict, List, Optional


class PortfolioSnapshot:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._col = db["portfolio_snapshots"]
        self._col.create_index([("user_id", 1), ("date", -1)], unique=True)

    def record(self, user_id: str, account, engine) -> Optional[Dict[str, Any]]:
        account_doc = account.get(user_id)
        if not account_doc:
            return None

        positions, _ = engine.get_positions(user_id)
        cash = account_doc["cash_balance"]
        initial = account_doc["initial_capital"]
        market_value = sum(p["market_value"] for p in positions)
        net_value = cash + market_value
        profit_amount = net_value - initial
        profit_pct = (profit_amount / initial * 100) if initial > 0 else 0

        today = datetime.now().strftime("%Y-%m-%d")
        doc = {
            "user_id": user_id,
            "date": today,
            "net_value": round(net_value, 2),
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "profit_amount": round(profit_amount, 2),
            "profit_pct": round(profit_pct, 2),
            "initial_capital": initial,
            "positions_detail": [
                {"code": p["code"], "name": p["name"], "shares": p["shares"],
                 "price": p["current_price"], "market_value": p["market_value"]}
                for p in positions
            ],
            "updated_at": datetime.now().isoformat(),
        }
        self._col.update_one(
            {"user_id": user_id, "date": today},
            {"$set": doc},
            upsert=True,
        )
        doc.pop("_id", None)
        return doc

    def get_history(self, user_id: str = "default", limit: int = 365) -> List[Dict[str, Any]]:
        docs = list(self._col.find(
            {"user_id": user_id},
            {"_id": 0, "positions_detail": 0},
            sort=[("date", 1)],
            limit=limit,
        ))
        return docs

    def has_today(self, user_id: str = "default") -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._col.find_one({"user_id": user_id, "date": today}) is not None

    def ensure_today(self, user_id: str, account, engine) -> None:
        if not self.has_today(user_id):
            self.record(user_id, account, engine)
