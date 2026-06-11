"""DAL 轻量取数测试：mock storage，不连 DB。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_full_valuation_cache_no_unbound_error(self):
        """估值缓存 PE/PB/ROE 齐全时不应抛 UnboundLocalError（回归：候选池只剩1只）。"""
        dal = _make_dal()
        valuation = MagicMock()
        valuation.get_by_code.return_value = {
            "code": "SH600519", "pe_dynamic": 22.0, "pb": 8.5,
            "roe": 30.1, "total_mv": 2.1e12,
        }
        dal.valuation_storage = valuation
        fi = dal.get_factor_inputs("SH600519")
        self.assertEqual(fi.pe, 22.0)
        self.assertEqual(fi.pb, 8.5)
        self.assertEqual(fi.roe, 30.1)

    def test_factor_inputs_name_from_valuation_cache(self):
        """name 优先取估值缓存（5分钟刷新，带最新 ST 标记），用于硬过滤。"""
        dal = _make_dal()
        valuation = MagicMock()
        valuation.get_by_code.return_value = {
            "code": "SH600053", "name": "*ST九鼎", "pe_dynamic": 22.0, "pb": 8.5, "roe": 5.0,
        }
        dal.valuation_storage = valuation
        fi = dal.get_factor_inputs("SH600053")
        self.assertEqual(fi.name, "*ST九鼎")

    def test_preload_caches_valuation_no_per_code_query(self):
        """预加载后估值走内存缓存，不应再逐只查 valuation_storage。"""
        dal = _make_dal()
        valuation = MagicMock()
        dal.valuation_storage = valuation

        colls = {}
        for name in ("financial", "fund_flow", "stock_info", "stock_valuation"):
            colls[name] = MagicMock()
        colls["financial"].aggregate.return_value = []
        colls["fund_flow"].distinct.return_value = []
        colls["stock_info"].find.return_value = []
        colls["stock_valuation"].find.return_value = [
            {"code": "SH600519", "name": "贵州茅台", "pe_dynamic": 22.0, "pb": 8.5, "roe": 30.1},
        ]
        fake_db = MagicMock()
        fake_db.__getitem__.side_effect = lambda n: colls[n]

        with patch("config.database.DatabaseConfig.get_database", return_value=fake_db):
            dal.preload_screen_cache(["SH600519"])

        fi = dal.get_factor_inputs("SH600519")
        self.assertEqual(fi.pe, 22.0)
        self.assertEqual(fi.roe, 30.1)
        self.assertEqual(fi.name, "贵州茅台")
        valuation.get_by_code.assert_not_called()

    def test_cached_roe_only_no_unbound_error(self):
        """缓存只有 ROE（PE/PB 缺）时同样不应崩。"""
        dal = _make_dal()
        valuation = MagicMock()
        valuation.get_by_code.return_value = {
            "code": "SH600519", "pe_dynamic": None, "pb": None, "roe": 30.1,
        }
        dal.valuation_storage = valuation
        fi = dal.get_factor_inputs("SH600519")
        self.assertEqual(fi.roe, 30.1)


if __name__ == "__main__":
    unittest.main()
