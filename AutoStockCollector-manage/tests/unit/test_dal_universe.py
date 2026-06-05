"""DAL 轻量取数测试：mock storage，不连 DB。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import StockDAL, FactorInputs


def _make_dal():
    kline = MagicMock()
    kline.distinct.return_value = ["SH600519", "SZ000001", None, "SH601318"]
    kline.find_many.return_value = [
        {"code": "SH600519", "date": "2026-05-28", "close": 20.0, "volume": 3000.0},
        {"code": "SH600519", "date": "2026-05-27", "close": 15.0, "volume": 1000.0},
    ]
    info = MagicMock()
    info.get_by_code.return_value = {"code": "SH600519", "name": "贵州茅台", "pe": 15.0, "pb": 2.0, "ps": 1.0}
    fund = MagicMock()
    fund.get_latest_flow.return_value = {"main_net_inflow": 5e6, "price": 20.0}
    fin = MagicMock()
    fin.find_one.return_value = {"code": "SH600519", "基本每股收益": 15.0, "每股净资产": 70.0, "roe": 28.5}
    return StockDAL(
        kline_storage=kline, info_storage=info, fund_flow_storage=fund,
        news_storage=MagicMock(), financial_storage=fin,
        dragon_tiger_storage=MagicMock(), margin_storage=MagicMock(),
    )


class TestListUniverse(unittest.TestCase):
    def test_returns_distinct_codes_dropping_none(self):
        dal = _make_dal()
        codes = dal.list_universe()
        self.assertIn("SH600519", codes)
        self.assertNotIn(None, codes)
        self.assertEqual(len(codes), 3)

    def test_passes_field_code_to_distinct(self):
        dal = _make_dal()
        dal.list_universe()
        args, _ = dal.kline_storage.distinct.call_args
        self.assertEqual(args[0], "code")


class TestGetFactorInputs(unittest.TestCase):
    def test_returns_factor_inputs_dataclass(self):
        dal = _make_dal()
        fi = dal.get_factor_inputs("SH600519")
        self.assertIsInstance(fi, FactorInputs)
        self.assertEqual(fi.code, "SH600519")
        self.assertEqual(fi.closes, [20.0, 15.0])
        self.assertEqual(fi.volumes, [3000.0, 1000.0])
        self.assertAlmostEqual(fi.pe, 20.0 / 15.0, places=2)  # close=20 / eps=15
        self.assertEqual(fi.main_net_inflow, 5e6)

    def test_missing_info_safe(self):
        dal = _make_dal()
        dal.info_storage.get_by_code.return_value = None
        dal.financial_storage.find_one.return_value = {}
        fi = dal.get_factor_inputs("SH600519")
        self.assertIsNone(fi.pe)


if __name__ == "__main__":
    unittest.main()
