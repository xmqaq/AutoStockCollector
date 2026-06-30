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
        # 初始化是破坏性重置：交易记录与净值快照都要清，否则旧净值曲线会残留、和新账户对不上
        self._db["trade_records"].delete_many({"user_id": user_id})
        self._db["portfolio_snapshots"].delete_many({"user_id": user_id})
        self._db["paper_orders"].delete_many({"user_id": user_id})  # 挂单也一并清空
        now = beijing_now().isoformat()
        doc = {
            "user_id": user_id,
            "initial_capital": initial_capital,
            "cash_balance": initial_capital,
            "frozen_cash": 0.0,  # 买入挂单冻结的资金（尚未成交，不属可用现金）
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

    def freeze_cash(self, user_id: str, amount: float) -> None:
        """冻结资金：买入挂单时调用。cash_balance 不变，仅 frozen_cash 增加，
        表示这部分钱已锁定、不可再用于下单。"""
        self._col.update_one(
            {"user_id": user_id},
            {"$inc": {"frozen_cash": round(amount, 2)},
             "$set": {"updated_at": beijing_now().isoformat()}},
        )

    def unfreeze_cash(self, user_id: str, amount: float) -> None:
        """解冻资金：撤单或成交时调用。成交时先解冻再 update_cash 扣减。"""
        self._col.update_one(
            {"user_id": user_id},
            {"$inc": {"frozen_cash": -round(amount, 2)},
             "$set": {"updated_at": beijing_now().isoformat()}},
        )

    def get_available_cash(self, user_id: str = "default") -> float:
        """可用现金 = 现金余额 - 冻结资金。下单前用此值校验资金是否充足。"""
        doc = self.get(user_id)
        if not doc:
            return 0.0
        return round(doc.get("cash_balance", 0) - doc.get("frozen_cash", 0), 2)

    def deposit(self, user_id: str, amount: float) -> Dict[str, Any]:
        """非破坏性入金/出金。amount>0 入金，<0 出金。

        现金与初始资金同步增减，保证"总收益率=(净值-初始资金)/初始资金"
        的口径不被现金流污染（新入的钱不会被当成盈利/亏损）。
        """
        doc = self.get(user_id)
        if not doc:
            raise ValueError("账户未初始化，请先设置初始资金")
        new_cash = round(doc["cash_balance"] + amount, 2)
        if new_cash < 0:
            raise ValueError(f"现金不足，当前可用 {doc['cash_balance']:.2f} 元")
        new_initial = round(doc["initial_capital"] + amount, 2)
        if new_initial < 0:
            raise ValueError("出金额不能超过初始资金")
        self._col.update_one(
            {"user_id": user_id},
            {"$set": {
                "cash_balance": new_cash,
                "initial_capital": new_initial,
                "updated_at": beijing_now().isoformat(),
            }},
        )
        return self.get(user_id)
