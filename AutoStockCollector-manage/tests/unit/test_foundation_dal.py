"""DAL 测试：用 mock storage 验证聚合逻辑，不连真实 DB。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import StockDataBundle, StockDAL


class TestStockDAL(unittest.TestCase):
    def _make_dal(self):
        kline = MagicMock()
        kline.find_many.return_value = [
            {"code": "SH600519", "date": "2026-05-28", "close": 20.0, "volume": 3000.0},
            {"code": "SH600519", "date": "2026-05-27", "close": 15.0, "volume": 1000.0},
            {"code": "SH600519", "date": "2026-05-26", "close": 15.0, "volume": 1000.0},
            {"code": "SH600519", "date": "2026-05-25", "close": 15.0, "volume": 1000.0},
            {"code": "SH600519", "date": "2026-05-24", "close": 15.0, "volume": 1000.0},
        ]
        info = MagicMock()
        info.get_by_code.return_value = {"code": "SH600519", "name": "贵州茅台", "pe": 15.0, "pb": 2.0}
        fund = MagicMock()
        fund.get_latest_flow.return_value = {"code": "SH600519", "main_net_inflow": 1e7}
        news = MagicMock()
        news.get_latest_news.return_value = [{"title": "利好消息", "publish_date": "2026-05-28"}]
        financial = MagicMock()
        financial.find_one.return_value = {"revenue_growth": 0.2, "roe": 0.18}
        dragon = MagicMock()
        dragon.find_many.return_value = []
        margin = MagicMock()
        margin.find_many.return_value = []
        return StockDAL(
            kline_storage=kline, info_storage=info, fund_flow_storage=fund,
            news_storage=news, financial_storage=financial,
            dragon_tiger_storage=dragon, margin_storage=margin,
        )

    def test_bundle_aggregates_all_dimensions(self):
        dal = self._make_dal()
        bundle = dal.get_stock_bundle("SH600519")
        self.assertIsInstance(bundle, StockDataBundle)
        self.assertEqual(bundle.code, "SH600519")
        self.assertEqual(bundle.name, "贵州茅台")
        self.assertEqual(bundle.closes, [20.0, 15.0, 15.0, 15.0, 15.0])
        self.assertEqual(bundle.volumes, [3000.0, 1000.0, 1000.0, 1000.0, 1000.0])
        self.assertEqual(bundle.pe, 15.0)
        self.assertEqual(bundle.main_net_inflow, 1e7)
        self.assertEqual(len(bundle.news), 1)
        self.assertEqual(bundle.financial.get("roe"), 0.18)

    def test_missing_info_yields_safe_defaults(self):
        dal = self._make_dal()
        dal.info_storage.get_by_code.return_value = None
        bundle = dal.get_stock_bundle("SH600519")
        self.assertEqual(bundle.name, "")
        self.assertIsNone(bundle.pe)

    def test_kline_queried_desc_by_date(self):
        dal = self._make_dal()
        dal.get_stock_bundle("SH600519")
        _, kwargs = dal.kline_storage.find_many.call_args
        self.assertEqual(kwargs.get("sort"), [("date", -1)])


if __name__ == "__main__":
    unittest.main()
