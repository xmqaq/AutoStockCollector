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
            acct._db = {"trade_records": MagicMock(), "portfolio_snapshots": MagicMock()}
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
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine._get_name = MagicMock(return_value="测试股票")
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=100000.0)

        record = engine.buy("default", "SH600000", 500, {}, acct)

        # amount=5000, commission=max(5, 5000*0.0003)=5, total_cost=5005
        self.assertAlmostEqual(record["cash_after"], 94995.0, places=2)
        self.assertEqual(record["action"], "buy")
        self.assertEqual(record["shares"], 500)
        acct.update_cash.assert_called_once_with("default", 94995.0)

    def test_buy_raises_when_insufficient_cash(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock(cash=100.0)  # only 100, need 5005

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("现金不足", str(ctx.exception))

    def test_buy_raises_when_price_unavailable(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(0.0, 'none'))
        engine._get_name = MagicMock(return_value="测试股票")
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.buy("default", "SH600000", 500, {}, acct)
        self.assertIn("无法获取", str(ctx.exception))

    def test_sell_adds_proceeds_to_cash(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(12.0, 'realtime'))
        engine.get_positions = MagicMock(return_value=([
            {"code": "SH600000", "name": "测试股票", "shares": 500, "avg_cost": 10.0}
        ], False))
        engine._trades.insert_one = MagicMock()
        acct = self._make_account_mock(cash=50000.0)

        record = engine.sell("default", "SH600000", 300, {}, acct)

        # amount=3600, stamp_tax=3.6, commission=max(5, 3600*0.0003)=5, total_fee=8.6
        self.assertAlmostEqual(record["cash_after"], 50000.0 + 3600 - 8.6, places=1)
        self.assertEqual(record["action"], "sell")

    def test_sell_raises_when_shares_insufficient(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine.get_positions = MagicMock(return_value=([
            {"code": "SH600000", "name": "测试股票", "shares": 100}
        ], False))
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 500, {}, acct)
        self.assertIn("持仓不足", str(ctx.exception))

    def test_sell_raises_when_no_position(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine.get_positions = MagicMock(return_value=([], False))
        acct = self._make_account_mock()

        with self.assertRaises(ValueError) as ctx:
            engine.sell("default", "SH600000", 100, {}, acct)
        self.assertIn("未持有", str(ctx.exception))

    def test_get_positions_aggregates_buy_minus_sell(self):
        engine = self._make_engine()
        engine._trades.find = MagicMock(return_value=[
            {"action": "buy", "code": "SH600000", "name": "测试股票", "shares": 1000,
             "price": 10.0, "amount": 10000.0, "total_cost": 10000.0, "traded_at": "2026-01-01T10:00:00"},
            {"action": "sell", "code": "SH600000", "name": "测试股票", "shares": 300,
             "price": 11.0, "traded_at": "2026-01-02T10:00:00"},
        ])
        engine._batch_tencent_quotes = MagicMock(return_value={})
        engine.get_current_price = MagicMock(return_value=(11.0, 'realtime'))
        engine._get_yesterday_close = MagicMock(return_value=10.5)

        positions, _ = engine.get_positions("default")

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["shares"], 700)
        # 卖出按均价等比例冲减成本：成本 10000×700/1000=7000，均价 10.0
        self.assertAlmostEqual(positions[0]["avg_cost"], 10.0, places=4)

    def test_get_positions_excludes_fully_sold(self):
        engine = self._make_engine()
        engine._trades.find = MagicMock(return_value=[
            {"action": "buy", "code": "SH600000", "name": "测试股票", "shares": 500,
             "price": 10.0, "amount": 5000.0, "total_cost": 5000.0, "traded_at": "2026-01-01T10:00:00"},
            {"action": "sell", "code": "SH600000", "name": "测试股票", "shares": 500,
             "price": 10.0, "traded_at": "2026-01-02T10:00:00"},
        ])
        engine._batch_tencent_quotes = MagicMock(return_value={})
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine._get_yesterday_close = MagicMock(return_value=10.0)

        positions, _ = engine.get_positions("default")
        self.assertEqual(len(positions), 0)

    def test_get_positions_rebuy_after_sell_uses_latest_cost(self):
        """卖空后再以不同价买回，成本应反映新买入价，而非全历史均值。"""
        engine = self._make_engine()
        engine._trades.find = MagicMock(return_value=[
            {"action": "buy", "code": "SH600000", "name": "测试股票", "shares": 100,
             "price": 10.0, "amount": 1000.0, "total_cost": 1000.0, "traded_at": "2026-01-01T10:00:00"},
            {"action": "sell", "code": "SH600000", "name": "测试股票", "shares": 100,
             "price": 12.0, "traded_at": "2026-01-02T10:00:00"},
            {"action": "buy", "code": "SH600000", "name": "测试股票", "shares": 100,
             "price": 20.0, "amount": 2000.0, "total_cost": 2000.0, "traded_at": "2026-01-03T10:00:00"},
        ])
        engine._batch_tencent_quotes = MagicMock(return_value={})
        engine.get_current_price = MagicMock(return_value=(20.0, 'realtime'))
        engine._get_yesterday_close = MagicMock(return_value=20.0)

        positions, _ = engine.get_positions("default")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["shares"], 100)
        self.assertAlmostEqual(positions[0]["avg_cost"], 20.0, places=4)


class TestPaperStats(unittest.TestCase):
    def _make_stats(self, trades):
        with patch("config.database.DatabaseConfig.get_database") as mock_db:
            mock_db.return_value = {"trade_records": MagicMock()}
            from modules.paper_trading.stats import PaperStats
            s = PaperStats()
            s._trades = MagicMock()
            s._trades.find.return_value = trades
            return s

    def _trade(self, action, code, shares, price, traded_at, cash_after=0):
        return {
            "action": action, "code": code, "shares": shares,
            "price": price, "traded_at": traded_at, "cash_after": cash_after,
        }

    def test_win_rate_100_when_all_profitable(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 100, 12.0, "2026-01-10T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["win_trades"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertAlmostEqual(result["win_rate"], 100.0, places=1)

    def test_win_rate_0_when_all_losses(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 100, 8.0, "2026-01-10T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["win_trades"], 0)
        self.assertAlmostEqual(result["win_rate"], 0.0, places=1)

    def test_partial_sell_creates_one_completed_pair(self):
        trades = [
            self._trade("buy", "SH600000", 500, 10.0, "2026-01-01T10:00:00"),
            self._trade("sell", "SH600000", 200, 11.0, "2026-01-05T10:00:00"),
        ]
        s = self._make_stats(trades)
        result = s.get_stats()
        self.assertEqual(result["total_trades"], 1)

    def test_empty_trades_returns_zeros(self):
        s = self._make_stats([])
        result = s.get_stats()
        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["win_rate"], 0)
        self.assertEqual(result["profit_factor"], 0)

    def test_nav_returns_sorted_series(self):
        trades = [
            self._trade("buy", "SH600000", 100, 10.0, "2026-01-01T10:00:00", cash_after=99000.0),
            self._trade("sell", "SH600000", 100, 12.0, "2026-01-10T10:00:00", cash_after=101200.0),
        ]
        acct = MagicMock()
        acct.get.return_value = {"initial_capital": 100000.0}
        s = self._make_stats(trades)
        nav = s.get_nav("default", acct)
        self.assertEqual(len(nav), 2)
        self.assertEqual(nav[0]["date"], "2026-01-01")
        self.assertAlmostEqual(nav[1]["nav"], 1.012, places=3)
