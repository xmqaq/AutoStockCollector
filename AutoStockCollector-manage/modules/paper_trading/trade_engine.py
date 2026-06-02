from datetime import datetime
from typing import Any, Dict, List, Optional

COMMISSION_RATE = 0.001


class TradeEngine:
    def __init__(self):
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        self._trades = db["trade_records"]

    def _get_price(self, code: str) -> float:
        try:
            from core.storage.mongo_storage import KlineStorage
            storage = KlineStorage()
            kline = storage.find_one({"code": code}, sort=[("date", -1)])
            if kline:
                return float(kline.get("close", 0))
        except Exception:
            pass
        return 0.0

    def _get_name(self, code: str) -> str:
        try:
            from core.storage.mongo_storage import StockInfoStorage
            storage = StockInfoStorage()
            info = storage.get_by_code(code)
            if info:
                return info.get("name") or info.get("A股简称") or code
        except Exception:
            pass
        return code

    def get_positions(self, user_id: str = "default") -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$code",
                "name": {"$last": "$name"},
                "buy_shares": {"$sum": {"$cond": [{"$eq": ["$action", "buy"]}, "$shares", 0]}},
                "sell_shares": {"$sum": {"$cond": [{"$eq": ["$action", "sell"]}, "$shares", 0]}},
                "buy_amount": {"$sum": {"$cond": [{"$eq": ["$action", "buy"]}, "$amount", 0]}},
            }},
        ]
        groups = list(self._trades.aggregate(pipeline))

        positions = []
        for g in groups:
            shares_held = g["buy_shares"] - g["sell_shares"]
            if shares_held <= 0:
                continue
            avg_cost = g["buy_amount"] / g["buy_shares"] if g["buy_shares"] > 0 else 0
            price = self._get_price(g["_id"])
            if price <= 0:
                price = avg_cost
            market_value = shares_held * price
            cost_basis = shares_held * avg_cost
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
            positions.append({
                "code": g["_id"],
                "name": g["name"],
                "shares": shares_held,
                "avg_cost": round(avg_cost, 4),
                "current_price": price,
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "position_ratio": 0,
            })

        total_market = sum(p["market_value"] for p in positions)
        for p in positions:
            p["position_ratio"] = round(p["market_value"] / total_market * 100, 2) if total_market > 0 else 0

        return sorted(positions, key=lambda x: x["market_value"], reverse=True)

    def buy(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
    ) -> Dict[str, Any]:
        price = self._get_price(code)
        if price <= 0:
            raise ValueError(f"无法获取 {code} 的最新价格")

        amount = shares * price
        commission = round(amount * COMMISSION_RATE, 2)
        total_cost = amount + commission

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")

        cash = account_doc["cash_balance"]
        if cash < total_cost:
            raise ValueError(f"现金不足，需要 {total_cost:.2f}，可用 {cash:.2f}")

        cash_after = round(cash - total_cost, 2)
        record = {
            "user_id": user_id,
            "code": code,
            "name": self._get_name(code),
            "action": "buy",
            "shares": shares,
            "price": price,
            "amount": round(amount, 2),
            "commission": commission,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": datetime.now().isoformat(),
        }
        self._trades.insert_one(record)
        account.update_cash(user_id, cash_after)
        record.pop("_id", None)
        return record

    def sell(
        self,
        user_id: str,
        code: str,
        shares: int,
        ai_signal: Dict[str, Any],
        account,
    ) -> Dict[str, Any]:
        positions = self.get_positions(user_id)
        pos = next((p for p in positions if p["code"] == code), None)
        if not pos:
            raise ValueError(f"未持有 {code}")
        if pos["shares"] < shares:
            raise ValueError(f"持仓不足，当前 {pos['shares']} 股，尝试卖出 {shares} 股")

        price = self._get_price(code)
        if price <= 0:
            raise ValueError(f"无法获取 {code} 的最新价格")

        amount = shares * price
        commission = round(amount * COMMISSION_RATE, 2)
        proceeds = round(amount - commission, 2)

        account_doc = account.get(user_id)
        if not account_doc:
            raise ValueError("账户未初始化，请先设置初始资金")
        cash = account_doc["cash_balance"]
        cash_after = round(cash + proceeds, 2)

        record = {
            "user_id": user_id,
            "code": code,
            "name": pos["name"],
            "action": "sell",
            "shares": shares,
            "price": price,
            "amount": round(amount, 2),
            "commission": commission,
            "ai_signal": ai_signal,
            "cash_before": cash,
            "cash_after": cash_after,
            "traded_at": datetime.now().isoformat(),
        }
        self._trades.insert_one(record)
        account.update_cash(user_id, cash_after)
        record.pop("_id", None)
        return record
