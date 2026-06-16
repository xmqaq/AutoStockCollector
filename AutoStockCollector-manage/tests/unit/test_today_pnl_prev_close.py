"""回归测试：持仓"今日%"昨收取值。

Bug: 盘中当日日K尚未入库，_get_yesterday_close 误把"前天"收盘当昨收，
导致今日% 变成两天累计涨幅（厦门钨业 +10% 显示 +21%，嘉元 +7% 显示 +23.66%）。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.paper_trading.trade_engine import TradeEngine


def _engine():
    # 跳过 __init__（其连接 MongoDB），仅测纯函数
    return TradeEngine.__new__(TradeEngine)


def _fake_kline_storage(klines):
    storage = MagicMock()
    storage.find_many.return_value = klines
    factory = MagicMock(return_value=storage)
    return patch("core.storage.mongo_storage.KlineStorage", factory)


class TestYesterdayClose(unittest.TestCase):
    def test_intraday_no_today_bar(self):
        """盘中：库里最新是昨日(06-15)，上一条是前天(06-12)。昨收应取 06-15。"""
        te = _engine()
        klines = [
            {"date": "2026-06-15", "close": 71.28},
            {"date": "2026-06-12", "close": 64.80},
        ]
        with patch.object(te, "_get_realtime_prev_close", return_value=None), \
             _fake_kline_storage(klines), \
             patch("modules.paper_trading.trade_engine.beijing_now",
                   return_value=datetime(2026, 6, 16, 14, 30)):
            self.assertEqual(te._get_yesterday_close("600549"), 71.28)

    def test_after_close_today_bar_present(self):
        """收盘后：库里最新是今日(06-16)，昨收取上一条 06-15。"""
        te = _engine()
        klines = [
            {"date": "2026-06-16", "close": 78.41},
            {"date": "2026-06-15", "close": 71.28},
        ]
        with patch.object(te, "_get_realtime_prev_close", return_value=None), \
             _fake_kline_storage(klines), \
             patch("modules.paper_trading.trade_engine.beijing_now",
                   return_value=datetime(2026, 6, 16, 16, 30)):
            self.assertEqual(te._get_yesterday_close("600549"), 71.28)

    def test_realtime_prev_close_preferred(self):
        """有腾讯实时昨收时优先采用（与现价同源，和券商一致）。"""
        te = _engine()
        with patch.object(te, "_get_realtime_prev_close", return_value=71.28):
            self.assertEqual(te._get_yesterday_close("600549"), 71.28)


if __name__ == "__main__":
    unittest.main()
