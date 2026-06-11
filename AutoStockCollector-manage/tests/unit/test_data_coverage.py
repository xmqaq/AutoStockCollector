"""数据完整性体检测试：mock db，不连库。"""
import unittest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.collector.coverage import compute_data_coverage


def _fake_db(kline_all, kline_today, ff_codes, val_total=0, si_codes=None, fin=None):
    colls = {}

    kline = MagicMock()
    def kline_distinct(field, query=None):
        if query:
            return list(kline_today)
        return list(kline_all)
    kline.distinct.side_effect = kline_distinct
    colls["kline"] = kline

    ff = MagicMock()
    def ff_distinct(field, query=None):
        if field == "date":
            return ["2026-06-11", "2026-06-10"]
        return list(ff_codes)
    ff.distinct.side_effect = ff_distinct
    colls["fund_flow"] = ff

    val = MagicMock()
    val.count_documents.return_value = val_total
    colls["stock_valuation"] = val

    si = MagicMock()
    si.distinct.return_value = list(si_codes or [])
    colls["stock_info"] = si

    f = MagicMock()
    f.find_one.return_value = {"report_date": "2026-03-31"} if fin else None
    f.distinct.return_value = list(fin or [])
    colls["financial"] = f

    db = MagicMock()
    db.__getitem__.side_effect = lambda n: colls[n]
    return db


class TestDataCoverage(unittest.TestCase):
    def test_kline_gap_detected_as_bad(self):
        """K线只覆盖一半在交易股票 → bad + 缺口示例。"""
        all_codes = [f"C{i}" for i in range(10)]
        db = _fake_db(kline_all=all_codes, kline_today=all_codes[:5],
                      ff_codes=all_codes, val_total=10,
                      si_codes=all_codes, fin=all_codes)
        out = compute_data_coverage(db)
        kline = next(s for s in out["sources"] if s["name"] == "kline")
        self.assertEqual(kline["status"], "bad")
        self.assertEqual(kline["missing_count"], 5)
        self.assertTrue(kline["missing_sample"])
        self.assertEqual(out["overall"], "bad")

    def test_full_coverage_ok(self):
        all_codes = [f"C{i}" for i in range(10)]
        db = _fake_db(kline_all=all_codes, kline_today=all_codes,
                      ff_codes=all_codes, val_total=10,
                      si_codes=all_codes, fin=all_codes)
        out = compute_data_coverage(db)
        self.assertEqual(out["overall"], "ok")
        for s in out["sources"]:
            self.assertEqual(s["status"], "ok", s["name"])

    def test_ref_date_falls_back_to_latest_fund_flow_date(self):
        all_codes = [f"C{i}" for i in range(10)]
        db = _fake_db(kline_all=all_codes, kline_today=all_codes,
                      ff_codes=all_codes, val_total=10,
                      si_codes=all_codes, fin=all_codes)
        out = compute_data_coverage(db)
        self.assertEqual(out["ref_date"], "2026-06-11")


if __name__ == "__main__":
    unittest.main()
