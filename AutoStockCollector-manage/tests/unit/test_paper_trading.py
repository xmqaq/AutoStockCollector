"""模拟盘模块单元测试：mock MongoDB，不依赖真实数据库。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPaperAccount(unittest.TestCase):
    def _make_account(self):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {
                "paper_account": MagicMock(),
                "trade_records": MagicMock(),
            }
            from modules.paper_trading.account import PaperAccount
            acct = PaperAccount()
            acct._col = MagicMock()
            acct._db = {"trade_records": MagicMock()}
            return acct

    def test_init_sets_cash_equal_to_capital(self):
        acct = self._make_account()
        acct._col.replace_one = MagicMock()
        result = acct.init(100000.0)
        self.assertEqual(result["cash_balance"], 100000.0)
        self.assertEqual(result["initial_capital"], 100000.0)
        self.assertEqual(result["user_id"], "default")

    def test_init_clears_trade_records(self):
        acct = self._make_account()
        acct._col.replace_one = MagicMock()
        acct.init(50000.0)
        acct._db["trade_records"].delete_many.assert_called_once_with({"user_id": "default"})

    def test_get_returns_none_when_not_initialized(self):
        acct = self._make_account()
        acct._col.find_one.return_value = None
        self.assertIsNone(acct.get())

    def test_get_strips_mongo_id(self):
        acct = self._make_account()
        acct._col.find_one.return_value = {
            "_id": "mongo_id",
            "user_id": "default",
            "initial_capital": 100000.0,
            "cash_balance": 90000.0,
        }
        result = acct.get()
        self.assertNotIn("_id", result)
        self.assertEqual(result["cash_balance"], 90000.0)

    def test_update_cash_calls_update_one(self):
        acct = self._make_account()
        acct._col.update_one = MagicMock()
        acct.update_cash("default", 75000.0)
        acct._col.update_one.assert_called_once()
        args = acct._col.update_one.call_args[0]
        self.assertEqual(args[0], {"user_id": "default"})
        self.assertEqual(args[1]["$set"]["cash_balance"], 75000.0)
