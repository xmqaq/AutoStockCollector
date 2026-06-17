"""仓位管理增强：初始化清快照、入金/出金、交易统计口径、行情批量。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.paper_trading.account import PaperAccount
from modules.paper_trading.stats import PaperStats
from modules.paper_trading.trade_engine import TradeEngine


def _account_with_mocks():
    acc = PaperAccount.__new__(PaperAccount)
    acc._col = MagicMock()
    acc._db = {"trade_records": MagicMock(), "portfolio_snapshots": MagicMock()}
    return acc


class TestInitClearsSnapshots(unittest.TestCase):
    def test_init_deletes_snapshots(self):
        acc = _account_with_mocks()
        acc.init(100000.0, "default")
        acc._db["trade_records"].delete_many.assert_called_once_with({"user_id": "default"})
        acc._db["portfolio_snapshots"].delete_many.assert_called_once_with({"user_id": "default"})


class TestDepositWithdraw(unittest.TestCase):
    def test_deposit_bumps_cash_and_initial(self):
        acc = _account_with_mocks()
        acc.get = MagicMock(side_effect=[
            {"user_id": "default", "cash_balance": 1000.0, "initial_capital": 100000.0},
            {"user_id": "default", "cash_balance": 6000.0, "initial_capital": 105000.0},
        ])
        out = acc.deposit("default", 5000.0)
        # 现金与初始资金同步 +5000，保证总收益率口径不被现金流污染
        set_arg = acc._col.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_arg["cash_balance"], 6000.0)
        self.assertEqual(set_arg["initial_capital"], 105000.0)
        self.assertEqual(out["initial_capital"], 105000.0)

    def test_withdraw_reduces_both(self):
        acc = _account_with_mocks()
        acc.get = MagicMock(side_effect=[
            {"user_id": "default", "cash_balance": 8000.0, "initial_capital": 100000.0},
            {"user_id": "default", "cash_balance": 5000.0, "initial_capital": 97000.0},
        ])
        acc.deposit("default", -3000.0)
        set_arg = acc._col.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_arg["cash_balance"], 5000.0)
        self.assertEqual(set_arg["initial_capital"], 97000.0)

    def test_withdraw_insufficient_cash_raises(self):
        acc = _account_with_mocks()
        acc.get = MagicMock(return_value={"user_id": "default", "cash_balance": 1000.0, "initial_capital": 100000.0})
        with self.assertRaises(ValueError):
            acc.deposit("default", -2000.0)


class TestStatsMethodology(unittest.TestCase):
    def _stats_with_trades(self, trades):
        st = PaperStats.__new__(PaperStats)
        st._trades = MagicMock()
        st._trades.find.return_value = trades
        return st

    def test_profit_factor_uses_amounts_and_position_size(self):
        # 大仓位小盈利 vs 小仓位大亏损：按金额算盈亏比应 <1，按平均%会失真
        trades = [
            {"code": "A", "action": "buy", "shares": 1000, "price": 10.0},
            {"code": "A", "action": "sell", "shares": 1000, "price": 11.0},   # +1000
            {"code": "B", "action": "buy", "shares": 100, "price": 10.0},
            {"code": "B", "action": "sell", "shares": 100, "price": 5.0},      # -500
        ]
        s = self._stats_with_trades(trades).get_stats()
        self.assertEqual(s["total_trades"], 2)
        self.assertEqual(s["win_trades"], 1)
        self.assertEqual(s["loss_trades"], 1)
        # gross_profit=1000, gross_loss=500 -> 2.0
        self.assertEqual(s["profit_factor"], 2.0)

    def test_breakeven_not_counted_as_loss(self):
        trades = [
            {"code": "A", "action": "buy", "shares": 100, "price": 10.0},
            {"code": "A", "action": "sell", "shares": 100, "price": 10.0},  # 平本
        ]
        s = self._stats_with_trades(trades).get_stats()
        self.assertEqual(s["total_trades"], 1)
        self.assertEqual(s["win_trades"], 0)
        self.assertEqual(s["loss_trades"], 0)


class TestBatchQuotes(unittest.TestCase):
    def test_batch_parses_price_and_prev_close(self):
        te = TradeEngine.__new__(TradeEngine)
        fake = (
            'v_sh600549="1~厦门钨业~600549~78.41~71.28~74.00~1~2~3";\n'
            'v_sh688388="1~嘉元科技~688388~71.56~66.79~67.93~1~2~3";\n'
        )
        resp = MagicMock()
        resp.text = fake
        with patch("requests.get", return_value=resp):
            q = te._batch_tencent_quotes(["SH600549", "SH688388"])
        self.assertEqual(q["SH600549"], {"price": 78.41, "prev_close": 71.28})
        self.assertEqual(q["SH688388"], {"price": 71.56, "prev_close": 66.79})

    def test_batch_empty_codes(self):
        te = TradeEngine.__new__(TradeEngine)
        self.assertEqual(te._batch_tencent_quotes([]), {})


class TestPlatformConfig(unittest.TestCase):
    def _make(self, stored=None):
        from modules.platform.config import PlatformConfig
        pc = PlatformConfig.__new__(PlatformConfig)
        pc._col = MagicMock()
        pc._col.find_one.return_value = ({"_id": "default", **stored} if stored else None)
        PlatformConfig._cache = None  # 重置进程级共享缓存
        return pc

    def test_defaults_when_empty(self):
        from modules.platform.config import DEFAULTS
        cfg = self._make(None).get(force=True)
        self.assertEqual(cfg["buy_commission_rate"], DEFAULTS["buy_commission_rate"])
        self.assertEqual(cfg["min_commission"], 5.0)
        self.assertEqual(cfg["stamp_tax_rate"], 0.001)

    def test_stored_overrides_defaults(self):
        cfg = self._make({"buy_commission_rate": 0.00015}).get(force=True)
        self.assertEqual(cfg["buy_commission_rate"], 0.00015)
        self.assertEqual(cfg["stamp_tax_rate"], 0.001)  # 未覆盖项保留默认

    def test_update_validates_and_ignores_unknown(self):
        pc = self._make(None)
        pc.update({"buy_commission_rate": 0.0002, "bogus": 1})
        set_arg = pc._col.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_arg["buy_commission_rate"], 0.0002)
        self.assertNotIn("bogus", set_arg)

    def test_update_rejects_negative(self):
        with self.assertRaises(ValueError):
            self._make(None).update({"buy_commission_rate": -1})

    def test_update_rejects_rate_too_high(self):
        with self.assertRaises(ValueError):
            self._make(None).update({"stamp_tax_rate": 0.5})


class TestTradeEngineConfigurableFees(unittest.TestCase):
    def _make_engine(self):
        from modules.paper_trading.trade_engine import TradeEngine
        engine = TradeEngine.__new__(TradeEngine)
        engine._trades = MagicMock()
        return engine

    def test_buy_uses_configured_commission_rate(self):
        engine = self._make_engine()
        engine.get_current_price = MagicMock(return_value=(10.0, 'realtime'))
        engine._get_name = MagicMock(return_value="x")
        engine._fees = MagicMock(return_value={
            "buy_commission_rate": 0.002, "sell_commission_rate": 0.001,
            "min_commission": 1.0, "stamp_tax_rate": 0.001,
        })
        acct = MagicMock()
        acct.get.return_value = {"cash_balance": 100000.0, "initial_capital": 100000.0}
        record = engine.buy("default", "SH600000", 500, {}, acct)
        # amount=5000, commission=max(1, 5000*0.002=10)=10, total=5010 → 94990
        self.assertAlmostEqual(record["cash_after"], 94990.0, places=2)


if __name__ == "__main__":
    unittest.main()
