"""选股效果跟踪测试：mock 结果/K线加载器，不连 DB。"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.engines.tracker import PickTracker


def _kline_loader_factory(data):
    """data: {code: [(date, close), ...] 按日期正序，首条为入场日}"""
    def loader(code, since_date, bars):
        return data.get(code, [])[:bars]
    return loader


class TestPickTracker(unittest.TestCase):
    def test_returns_and_win_rate(self):
        results = [{
            "timestamp": "2026-06-01T15:00:00",
            "picks": [
                {"code": "A", "name": "甲", "composite": 80},
                {"code": "B", "name": "乙", "composite": 70},
            ],
        }]
        klines = {
            # 入场 10.0，1日后 11.0(+10%)，3日后 12.0(+20%)
            "A": [("2026-06-01", 10.0), ("2026-06-02", 11.0),
                  ("2026-06-03", 11.5), ("2026-06-04", 12.0)],
            # 入场 20.0，1日后 19.0(-5%)，3日后 21.0(+5%)
            "B": [("2026-06-01", 20.0), ("2026-06-02", 19.0),
                  ("2026-06-03", 20.5), ("2026-06-04", 21.0)],
        }
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines))
        out = tracker.evaluate(horizons=(1, 3), limit=10)

        self.assertEqual(out["runs_count"], 1)
        run = out["runs"][0]
        self.assertEqual(run["evaluated"], 2)
        self.assertAlmostEqual(run["returns"]["1"]["avg"], 2.5)   # (10 + -5) / 2
        self.assertEqual(run["returns"]["1"]["win_rate"], 50.0)
        self.assertAlmostEqual(run["returns"]["3"]["avg"], 12.5)  # (20 + 5) / 2
        self.assertEqual(run["returns"]["3"]["win_rate"], 100.0)
        self.assertAlmostEqual(out["overall"]["1"]["avg"], 2.5)
        self.assertEqual(out["overall"]["3"]["n"], 2)

        pick_a = next(p for p in run["picks"] if p["code"] == "A")
        self.assertEqual(pick_a["entry_date"], "2026-06-01")
        self.assertAlmostEqual(pick_a["returns"]["1"], 10.0)

    def test_insufficient_klines_skips_horizon(self):
        """K线不足覆盖某 horizon 时该档不计入，不报错。"""
        results = [{"timestamp": "2026-06-09T15:00:00",
                    "picks": [{"code": "A", "name": "甲", "composite": 80}]}]
        klines = {"A": [("2026-06-09", 10.0), ("2026-06-10", 10.5)]}  # 只够1日
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines))
        out = tracker.evaluate(horizons=(1, 5), limit=10)
        run = out["runs"][0]
        self.assertEqual(run["returns"]["1"]["n"], 1)
        self.assertEqual(run["returns"]["5"]["n"], 0)
        self.assertIsNone(run["returns"]["5"]["avg"])

    def test_no_klines_pick_not_evaluated(self):
        results = [{"timestamp": "2026-06-09T15:00:00",
                    "picks": [{"code": "GONE", "name": "无数据", "composite": 50}]}]
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory({}))
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs"][0]["evaluated"], 0)
        self.assertEqual(out["overall"]["1"]["n"], 0)

    def test_empty_results(self):
        tracker = PickTracker(results_loader=lambda limit: [],
                              kline_loader=_kline_loader_factory({}))
        out = tracker.evaluate(horizons=(1, 3), limit=10)
        self.assertEqual(out["runs_count"], 0)
        self.assertEqual(out["overall"]["1"]["n"], 0)

    def test_zero_entry_close_skipped(self):
        """入场价为0（脏数据）不应除零，整只跳过。"""
        results = [{"timestamp": "2026-06-09T15:00:00",
                    "picks": [{"code": "A", "name": "甲", "composite": 80}]}]
        klines = {"A": [("2026-06-09", 0.0), ("2026-06-10", 10.0)]}
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines))
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs"][0]["evaluated"], 0)


if __name__ == "__main__":
    unittest.main()
