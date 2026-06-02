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


class TestTradeEngine(unittest.TestCase):
    def _make_engine(self):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {"trade_records": MagicMock()}
            from modules.paper_trading.trade_engine import TradeEngine
            engine = TradeEngine()
            engine._trades = MagicMock()
            return engine

    def _make_account_mock(self, cash=100000.0):
        acct = MagicMock()
        acct.get.return_value = {
            "user_id": "default",
            "initial_capital": 100000.0,
            "cash_balance": cash,
        }
        return acct

    def test_buy_deducts_cash_and_commission(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine._get_name = MagicMock(return_value="测试股票")
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=100000.0)

        record = engine.buy("default", "SH600000", 500, {}, acct)

        # amount=5000, commission=5, total_cost=5005
        self.assertAlmostEqual(record["cash_after"], 94995.0, places=2)
        self.assertEqual(record["action"], "buy")
        self.assertEqual(record["shares"], 500)
        acct.update_cash.assert_called_once_with("default", 94995.0)

    def test_buy_raises_when_insufficient_cash(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock(cash=100.0)  # only 100, need 5005

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("现金不足", str(ctx.exception))

    def test_buy_raises_when_price_unavailable(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=0.0)
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("无法获取", str(ctx.exception))

    def test_sell_adds_proceeds_to_cash(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=12.0)
        engine.get_positions = MagicMock(return_value=[
            {"code": "SH600000", "name": "测试股票", "shares": 500}
        ])
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=50000.0)

        record = engine.sell("default", "SH600000", 300, {}, acct)

        # amount=3600, commission=3.6, proceeds=3596.4
        self.assertAlmostEqual(record["cash_after"], 53596.4, places=1)
        self.assertEqual(record["action"], "sell")

    def test_sell_raises_when_shares_insufficient(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine.get_positions = MagicMock(return_value=[
            {"code": "SH600000", "name": "测试股票", "shares": 100}
        ])
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 500, {}, acct)
        self.assertIn("持仓不足", str(ctx.exception))

    def test_sell_raises_when_no_position(self):
        engine = self._make_engine()
        engine._get_price = MagicMock(return_value=10.0)
        engine.get_positions = MagicMock(return_value=[])
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 100, {}, acct)
        self.assertIn("未持有", str(ctx.exception))

    def test_get_positions_aggregates_buy_minus_sell(self):
        engine = self._make_engine()
        engine._trades.aggregate = MagicMock(return_value=[
            {
                "_id": "SH600000",
                "name": "测试股票",
                "buy_shares": 1000,
                "sell_shares": 300,
                "buy_amount": 10000.0,
            }
        ])
        engine._get_price = MagicMock(return_value=11.0)

        positions = engine.get_positions("default")

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["shares"], 700)
        self.assertAlmostEqual(positions[0]["avg_cost"], 10.0, places=4)

    def test_get_positions_excludes_fully_sold(self):
        engine = self._make_engine()
        engine._trades.aggregate = MagicMock(return_value=[
            {
                "_id": "SH600000",
                "name": "测试股票",
                "buy_shares": 500,
                "sell_shares": 500,
                "buy_amount": 5000.0,
            }
        ])
        engine._get_price = MagicMock(return_value=10.0)

        positions = engine.get_positions("default")
        self.assertEqual(len(positions), 0)
