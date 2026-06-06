"""DAL 测试：用 mock storage 验证聚合逻辑，不连真实 DB / 不发网络请求。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import StockDataBundle, StockDAL


def _make_dal():
    kline = MagicMock()
    kline.find_many.return_value = [
        {"code": "SH600519", "date": "2026-05-28", "close": 20.0, "volume": 3000.0},
        {"code": "SH600519", "date": "2026-05-27", "close": 15.0, "volume": 1000.0},
        {"code": "SH600519", "date": "2026-05-26", "close": 15.0, "volume": 1000.0},
        {"code": "SH600519", "date": "2026-05-25", "close": 15.0, "volume": 1000.0},
        {"code": "SH600519", "date": "2026-05-24", "close": 15.0, "volume": 1000.0},
    ]
    info = MagicMock()
    info.get_by_code.return_value = {"code": "SH600519", "name": "贵州茅台"}
    fund = MagicMock()
    fund.find_many.return_value = [{"code": "SH600519", "main_net_inflow": 1e7}]
    fund.get_latest_flow.return_value = {"code": "SH600519", "main_net_inflow": 1e7}
    news = MagicMock()
    news.get_latest_news.return_value = [{"title": "利好消息", "publish_date": "2026-05-28"}]
    financial = MagicMock()
    # find_many returns list for TTM calculation; first record is latest
    financial.find_many.return_value = [
        {"code": "SH600519", "report_date": "2025-12-31", "净利润": 80e8, "营业收入": 150e8,
         "roe": 28.5, "每股净资产": 70.0, "基本每股收益": 63.5},
    ]
    dragon = MagicMock()
    dragon.find_many.return_value = []
    margin = MagicMock()
    margin.find_many.return_value = []
    return StockDAL(
        kline_storage=kline, info_storage=info, fund_flow_storage=fund,
        news_storage=news, financial_storage=financial,
        dragon_tiger_storage=dragon, margin_storage=margin,
    )


class TestStockDAL(unittest.TestCase):
    @patch.object(StockDAL, "_fetch_ttm_valuation", return_value={"pe": 21.5, "pb": 8.2, "total_mv": None})
    @patch.object(StockDAL, "_fetch_realtime_price", return_value=None)
    def test_bundle_aggregates_all_dimensions(self, _mock_price, _mock_ttm):
        dal = _make_dal()
        bundle = dal.get_stock_bundle("SH600519")
        self.assertIsInstance(bundle, StockDataBundle)
        self.assertEqual(bundle.code, "SH600519")
        self.assertEqual(bundle.name, "贵州茅台")
        self.assertEqual(bundle.closes, [20.0, 15.0, 15.0, 15.0, 15.0])
        self.assertEqual(bundle.volumes, [3000.0, 1000.0, 1000.0, 1000.0, 1000.0])
        self.assertAlmostEqual(bundle.pe, 21.5)
        self.assertAlmostEqual(bundle.pb, 8.2)
        self.assertIsNotNone(bundle.roe)
        self.assertGreater(bundle.roe, 0)
        self.assertAlmostEqual(bundle.main_net_inflow, 1e7)  # 元（新代码：直接解析为浮点）
        self.assertEqual(len(bundle.news), 1)

    @patch.object(StockDAL, "_fetch_ttm_valuation", return_value={"pe": None, "pb": None, "total_mv": None})
    @patch.object(StockDAL, "_fetch_realtime_price", return_value=None)
    def test_missing_info_yields_safe_defaults(self, _mock_price, _mock_ttm):
        dal = _make_dal()
        dal.info_storage.get_by_code.return_value = None
        dal.financial_storage.find_many.return_value = []
        bundle = dal.get_stock_bundle("SH600519")
        self.assertEqual(bundle.name, "")
        self.assertIsNone(bundle.pe)

    @patch.object(StockDAL, "_fetch_ttm_valuation", return_value={"pe": None, "pb": None, "total_mv": None})
    @patch.object(StockDAL, "_fetch_realtime_price", return_value=None)
    def test_kline_queried_desc_by_date(self, _mock_price, _mock_ttm):
        dal = _make_dal()
        dal.get_stock_bundle("SH600519")
        call_args_list = dal.kline_storage.find_many.call_args_list
        # First call is the klines query
        _, kwargs = call_args_list[0]
        self.assertEqual(kwargs.get("sort"), [("date", -1)])

    @patch.object(StockDAL, "_fetch_ttm_valuation", return_value={"pe": None, "pb": None, "total_mv": None})
    @patch.object(StockDAL, "_fetch_realtime_price", return_value=None)
    def test_fallback_pe_uses_annual_eps(self, _mock_price, _mock_ttm):
        """当 TTM API 不可用时，回退到财报 EPS 计算 PE/PB。"""
        dal = _make_dal()
        # 年报：EPS=63.5, BPS=70.0，收盘价=20.0（测试值）
        bundle = dal.get_stock_bundle("SH600519")
        # 年报（Q4）不需要年化：pe = 20/63.5 ≈ 0.31（只是检查非 None 且合理）
        # 注意：测试收盘价仅 20，与真实茅台无关
        self.assertIsNotNone(bundle.pe)
        self.assertIsNotNone(bundle.pb)

    @patch.object(StockDAL, "_fetch_ttm_valuation", return_value={"pe": None, "pb": None, "total_mv": None})
    @patch.object(StockDAL, "_fetch_realtime_price", return_value=None)
    def test_q1_eps_annualized(self, _mock_price, _mock_ttm):
        """Q1 报告（ISO 日期 -03-31）的 EPS 应乘以 4 年化。"""
        dal = _make_dal()
        dal.financial_storage.find_many.return_value = [
            {"code": "SH600519", "report_date": "2025-03-31",
             "基本每股收益": 15.0, "每股净资产": 70.0},
        ]
        bundle = dal.get_stock_bundle("SH600519")
        # price=20, eps=15×4=60, pe=20/60≈0.33; BPS=70, pb=20/70≈0.29
        self.assertIsNotNone(bundle.pe)
        self.assertAlmostEqual(bundle.pe, round(20.0 / (15.0 * 4), 2))


class TestReportQuarter(unittest.TestCase):
    """_report_quarter 辅助函数各种格式识别"""
    def _q(self, s):
        return StockDAL._report_quarter(s)

    def test_iso_q1(self):
        self.assertEqual(self._q("2025-03-31"), 1)

    def test_iso_q2(self):
        self.assertEqual(self._q("2025-06-30"), 2)

    def test_iso_q3(self):
        self.assertEqual(self._q("2025-09-30"), 3)

    def test_iso_annual(self):
        self.assertEqual(self._q("2024-12-31"), 4)

    def test_chinese_q1(self):
        self.assertEqual(self._q("2025年一季报"), 1)

    def test_chinese_halfyear(self):
        self.assertEqual(self._q("2025年半年报"), 2)

    def test_chinese_q3(self):
        self.assertEqual(self._q("2025年三季报"), 3)


if __name__ == "__main__":
    unittest.main()
