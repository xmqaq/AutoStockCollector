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


def _no_baseline(**kw):
    """构造不带基准数据的 tracker kwargs（基准各字段应为 None）。"""
    return dict(trading_dates_loader=lambda: [],
                market_loader=lambda dates: {}, **kw)


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
                              kline_loader=_kline_loader_factory(klines),
                              **_no_baseline())
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
                              kline_loader=_kline_loader_factory(klines),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1, 5), limit=10)
        run = out["runs"][0]
        self.assertEqual(run["returns"]["1"]["n"], 1)
        self.assertEqual(run["returns"]["5"]["n"], 0)
        self.assertIsNone(run["returns"]["5"]["avg"])

    def test_no_klines_pick_not_evaluated(self):
        results = [{"timestamp": "2026-06-09T15:00:00",
                    "picks": [{"code": "GONE", "name": "无数据", "composite": 50}]}]
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory({}),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs"][0]["evaluated"], 0)
        self.assertEqual(out["overall"]["1"]["n"], 0)

    def test_empty_results(self):
        tracker = PickTracker(results_loader=lambda limit: [],
                              kline_loader=_kline_loader_factory({}),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1, 3), limit=10)
        self.assertEqual(out["runs_count"], 0)
        self.assertEqual(out["overall"]["1"]["n"], 0)

    def test_same_day_batches_deduped_keep_last(self):
        """同一天同策略多次运行只统计当天最后一批，重复批次不重复计票。"""
        results = [
            {"timestamp": "2026-06-01T15:30:00", "strategy": "default",
             "picks": [{"code": "A", "name": "甲", "composite": 80}]},
            {"timestamp": "2026-06-01T09:00:00", "strategy": "default",
             "picks": [{"code": "A", "name": "甲", "composite": 80},
                       {"code": "B", "name": "乙", "composite": 70}]},
        ]
        klines = {"A": [("2026-06-01", 10.0), ("2026-06-02", 11.0)],
                  "B": [("2026-06-01", 20.0), ("2026-06-02", 21.0)]}
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs_count"], 1)
        self.assertEqual(out["runs"][0]["timestamp"], "2026-06-01T15:30:00")
        self.assertEqual(out["overall"]["1"]["n"], 1)  # 只计最后一批的1只

    def test_same_day_different_strategies_kept(self):
        """同一天不同策略的批次互不去重。"""
        results = [
            {"timestamp": "2026-06-01T15:30:00", "strategy": "default",
             "picks": [{"code": "A", "name": "甲", "composite": 80}]},
            {"timestamp": "2026-06-01T17:00:00", "strategy": "五因子增强",
             "picks": [{"code": "B", "name": "乙", "composite": 70}]},
        ]
        klines = {"A": [("2026-06-01", 10.0), ("2026-06-02", 11.0)],
                  "B": [("2026-06-01", 20.0), ("2026-06-02", 21.0)]}
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs_count"], 2)
        self.assertEqual(out["overall"]["1"]["n"], 2)

    def test_baseline_and_excess(self):
        """有市场数据时应给出等权基准、超额收益和跑赢率。"""
        results = [{
            "timestamp": "2026-06-01T15:00:00",
            "picks": [{"code": "A", "name": "甲", "composite": 80}],
        }]
        klines = {"A": [("2026-06-01", 10.0), ("2026-06-02", 11.0)]}  # pick 1日 +10%
        # 全市场两只：X +5%，Y 0% → 等权基准 +2.5%
        market = {
            "2026-06-01": {"X": 10.0, "Y": 20.0, "A": 10.0},
            "2026-06-02": {"X": 10.5, "Y": 20.0, "A": 11.0},
        }
        tracker = PickTracker(
            results_loader=lambda limit: results,
            kline_loader=_kline_loader_factory(klines),
            trading_dates_loader=lambda: ["2026-06-01", "2026-06-02"],
            market_loader=lambda dates: {d: market[d] for d in dates if d in market},
        )
        out = tracker.evaluate(horizons=(1,), limit=10)
        h1 = out["runs"][0]["returns"]["1"]
        self.assertAlmostEqual(h1["baseline"], 5.0)   # (5 + 0 + 10) / 3
        self.assertAlmostEqual(h1["excess"], 5.0)     # 10 - 5
        self.assertEqual(h1["beat_rate"], 100.0)
        self.assertAlmostEqual(out["overall"]["1"]["excess"], 5.0)
        self.assertEqual(out["overall"]["1"]["beat_rate"], 100.0)

    def test_baseline_missing_target_date(self):
        """目标交易日超出已有数据时基准为 None，收益仍正常输出。"""
        results = [{"timestamp": "2026-06-01T15:00:00",
                    "picks": [{"code": "A", "name": "甲", "composite": 80}]}]
        klines = {"A": [("2026-06-01", 10.0), ("2026-06-02", 11.0)]}
        tracker = PickTracker(
            results_loader=lambda limit: results,
            kline_loader=_kline_loader_factory(klines),
            trading_dates_loader=lambda: ["2026-06-01"],  # 没有 06-02
            market_loader=lambda dates: {},
        )
        out = tracker.evaluate(horizons=(1,), limit=10)
        h1 = out["runs"][0]["returns"]["1"]
        self.assertAlmostEqual(h1["avg"], 10.0)
        self.assertIsNone(h1["baseline"])
        self.assertIsNone(h1["excess"])

    def test_zero_entry_close_skipped(self):
        """入场价为0（脏数据）不应除零，整只跳过。"""
        results = [{"timestamp": "2026-06-09T15:00:00",
                    "picks": [{"code": "A", "name": "甲", "composite": 80}]}]
        klines = {"A": [("2026-06-09", 0.0), ("2026-06-10", 10.0)]}
        tracker = PickTracker(results_loader=lambda limit: results,
                              kline_loader=_kline_loader_factory(klines),
                              **_no_baseline())
        out = tracker.evaluate(horizons=(1,), limit=10)
        self.assertEqual(out["runs"][0]["evaluated"], 0)


if __name__ == "__main__":
    unittest.main()
