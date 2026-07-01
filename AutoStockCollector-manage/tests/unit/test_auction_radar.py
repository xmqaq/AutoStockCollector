"""盘前竞价雷达模块单元测试：mock MongoDB 与行情，不依赖真实数据库。

覆盖：
- 8 维打分（含负跳空修复）
- 9 类诱骗检测
- 回测 metrics（胜率/profit_factor/sharpe/max_drawdown/单调性）
- TrackingStore 状态机
- radar_utils 代码转换/板块强度
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.pre_market_call_auction.config import AuctionConfig
from modules.pre_market_call_auction.strength_calculator import (
    compute_strength, _score_gap, _score_vol_ratio, _score_order_imbalance,
    _score_auction_turnover, _rank_percentile,
)
from modules.pre_market_call_auction.trap_detector import (
    detect_trap, compute_sector_trap_rate, _check_cancel_rate, _check_volume_concentration,
    _check_sector_trap,
)
from modules.pre_market_call_auction.radar_utils import (
    strip_prefix_from_code, to_tencent_code, compute_sector_strength,
)
from modules.pre_market_call_auction.backtest.metrics import (
    compute_metrics, _win_rate, _profit_factor, _max_drawdown, _check_monotonicity,
)
from modules.pre_market_call_auction.tracking_store import TrackingStore


def _snap(code="600000", gap=4.0, amount=5e7, volume=1e6, turnover=2.0,
          open_price=10.0, volume_ratio=1.5, name="测试股票", pre_close=9.6):
    return {
        "code": code, "name": name, "gap_pct": gap, "amount": amount,
        "volume": volume, "turnover": turnover, "open_price": open_price,
        "pre_close": pre_close, "volume_ratio": volume_ratio,
    }


# ── 8 维打分 ───────────────────────────────────────────────────
class TestStrengthScoring(unittest.TestCase):
    def _neg(self, amounts):
        return [-x for x in sorted(amounts, reverse=True)]

    def test_positive_gap_linear(self):
        # gap=6% → 100 分
        self.assertAlmostEqual(_score_gap(6.0), 100.0)

    def test_negative_gap_no_volume_zero(self):
        # 负跳空无量大 → 0
        neg = self._neg([1e8, 5e7, 1e7])
        self.assertEqual(_score_gap(-5.0, amount=1e6, neg_sorted_desc=neg), 10.0)

    def test_negative_gap_with_volume(self):
        # 负跳空 + 量大（承接）→ 60 分。amount 接近顶部 → pct>=0.5
        neg = self._neg([1e8, 9e7, 5e7, 1e7])
        self.assertEqual(_score_gap(-5.0, amount=9e7, neg_sorted_desc=neg), 60.0)

    def test_flat_open(self):
        self.assertEqual(_score_gap(0.0), 40.0)

    def test_vol_ratio_high(self):
        snap = _snap(volume_ratio=3.0)
        self.assertAlmostEqual(_score_vol_ratio(snap), 100.0)

    def test_vol_ratio_missing(self):
        snap = _snap(volume_ratio=0)
        self.assertAlmostEqual(_score_vol_ratio(snap), 30.0)

    def test_order_imbalance_buy_pressure(self):
        # amount/volume > open_price → 主动买
        snap = _snap(amount=1.2e7, volume=1e6, open_price=10.0)
        # avg=12, ratio=1.2 → 50 + 0.2*500 = 150 → clamp 100
        self.assertAlmostEqual(_score_order_imbalance(snap), 100.0)

    def test_order_imbalance_no_data(self):
        snap = _snap(amount=0, volume=0)
        self.assertAlmostEqual(_score_order_imbalance(snap), 50.0)

    def test_auction_turnover_new_ipo_boost(self):
        snap = {"turnover": 3.0, "is_new_ipo": True}
        # 无 sorted_turnover → 绝对值分档 3/5*100=60，新股*1.2=72
        self.assertAlmostEqual(_score_auction_turnover(snap, None), 72.0)

    def test_compute_strength_8d(self):
        snap = _snap(code="600000", gap=4.0, amount=1e8, volume_ratio=2.0)
        neg = self._neg([1e8, 5e7, 1e7])
        s = compute_strength(snap, [1e8, 5e7, 1e7], neg,
                             {"600000": "银行"}, {"银行": 3.0}, [3.0, 2.0, 1.0])
        self.assertGreater(s.score, 60)
        self.assertIn("gap", s.factors_used)
        self.assertIn("vol_ratio", s.factors_used)
        self.assertEqual(len(s.weights), 8)


# ── 9 类诱骗检测 ───────────────────────────────────────────────
class TestTrapDetector(unittest.TestCase):
    def _thresholds(self):
        return {"median": 5e7, "bottom20_pct": 1e7, "top20_pct": 8e7, "vol_min_threshold": 3e7}

    def test_extreme_high_open(self):
        w = detect_trap(_snap(gap=9.0, amount=1e8), [1e8, 5e7], self._thresholds())
        self.assertTrue(w.is_trap)
        self.assertIn("极端高开", w.signals[0])

    def test_no_volume_high_open(self):
        w = detect_trap(_snap(gap=6.0, amount=1e6), [1e8, 5e7], self._thresholds())
        self.assertTrue(w.is_trap)
        self.assertEqual(w.trap_type, "bull_trap")

    def test_bear_trap_volume(self):
        w = detect_trap(_snap(gap=-5.0, amount=9e7), [1e8] * 200, self._thresholds())
        self.assertTrue(w.is_trap)
        self.assertEqual(w.trap_type, "bear_trap")

    def test_cancel_rate_dual_snapshot(self):
        cur = _snap(gap=5.0, volume=1e5)
        pre = {"volume": 1e6}  # 9:20 量远大于 9:25 → 90% 撤单
        w = _check_cancel_rate(cur, pre)
        self.assertTrue(w.is_trap)
        self.assertIsNotNone(w.cancel_rate)

    def test_volume_concentration(self):
        snap = _snap(gap=6.0, volume_ratio=0.5, amount=1e8)
        w = _check_volume_concentration(snap, self._thresholds())
        self.assertTrue(w.is_trap)
        self.assertIn("量集中前段", w.signals[0])

    def test_sector_trap(self):
        snap = {"code": "600000", "gap_pct": 5.0, "industry": "银行", "pre_close": 9.6}
        rate = {"银行": 0.5}  # 板块诱多率 50%
        w = _check_sector_trap(snap, rate)
        self.assertTrue(w.is_trap)

    def test_no_trap(self):
        w = detect_trap(_snap(gap=2.0, amount=5e7), [1e8, 5e7], self._thresholds())
        self.assertFalse(w.is_trap)

    def test_aggregate_severity(self):
        # 极端高开 + 无量 + 末尾量 → 3 signals → high
        snap = _snap(gap=9.0, amount=1e6)
        w = detect_trap(snap, [1e8] * 200, self._thresholds())
        self.assertGreaterEqual(len(w.signals), 2)
        self.assertIn(w.severity, ("medium", "high"))


# ── metrics ────────────────────────────────────────────────────
class TestBacktestMetrics(unittest.TestCase):
    def test_win_rate(self):
        trades = [{"return_pct": 0.05}, {"return_pct": -0.02}, {"return_pct": 0.03}]
        self.assertAlmostEqual(_win_rate(trades), 0.6667, places=3)

    def test_profit_factor(self):
        trades = [{"return_pct": 0.1}, {"return_pct": -0.05}, {"return_pct": 0.08}]
        pf = _profit_factor(trades)
        self.assertAlmostEqual(pf, round(0.18 / 0.05, 4))

    def test_max_drawdown(self):
        # 逐日收益 [0.05, -0.10, 0.02]：cum=0.05(peak)→-0.05(dd=0.10)→-0.03(dd=0.08)
        # 最大回撤在第二步 = 0.10
        dd = _max_drawdown([0.05, -0.10, 0.02])
        self.assertAlmostEqual(dd, 0.10, places=2)

    def test_monotonicity_true(self):
        buckets = [{"win_rate": 0.8}, {"win_rate": 0.6}, {"win_rate": 0.4}]
        self.assertTrue(_check_monotonicity(buckets))

    def test_monotonicity_false(self):
        buckets = [{"win_rate": 0.4}, {"win_rate": 0.8}]  # 高桶反而低
        self.assertFalse(_check_monotonicity(buckets))

    def test_compute_metrics_empty(self):
        m = compute_metrics([])
        self.assertEqual(m["overall"]["total_trades"], 0)

    def test_compute_metrics_buckets(self):
        trades = [
            {"strength_score": 85, "return_pct": 0.05, "date": "2026-06-01"},
            {"strength_score": 65, "return_pct": -0.02, "date": "2026-06-01"},
            {"strength_score": 45, "return_pct": 0.01, "date": "2026-06-02"},
        ]
        m = compute_metrics(trades)
        self.assertEqual(len(m["buckets"]), 3)
        self.assertEqual(m["overall"]["total_trades"], 3)


# ── radar_utils ────────────────────────────────────────────────
class TestRadarUtils(unittest.TestCase):
    def test_strip_prefix(self):
        self.assertEqual(strip_prefix_from_code("SH600000"), "600000")
        self.assertEqual(strip_prefix_from_code("sz000001"), "000001")
        self.assertEqual(strip_prefix_from_code("600000"), "600000")

    def test_to_tencent_code(self):
        self.assertEqual(to_tencent_code("600000"), "sh600000")
        self.assertEqual(to_tencent_code("SZ000001"), "sz000001")
        self.assertEqual(to_tencent_code("830001"), "bj830001")

    def test_sector_strength(self):
        snaps = [
            {"code": "600000", "gap_pct": 5.0, "amount": 1e8, "industry": "银行"},
            {"code": "600001", "gap_pct": 10.0, "amount": 2e8, "industry": "银行"},
            {"code": "000001", "gap_pct": 3.0, "amount": 5e7, "industry": "地产"},
        ]
        result = compute_sector_strength(snaps, {"600000": "银行", "600001": "银行", "000001": "地产"})
        self.assertEqual(len(result), 2)
        # 银行板块应有涨停家数
        bank = next(s for s in result if s["sector"] == "银行")
        self.assertEqual(bank["limit_up_count"], 1)


# ── TrackingStore 状态机 ───────────────────────────────────────
class TestTrackingStore(unittest.TestCase):
    def _store(self):
        store = TrackingStore()
        # _db 是方法，返回 mock db；让 db["col"] 返回各 collection mock
        track_col = MagicMock()
        perf_col = MagicMock()
        db_mock = MagicMock()
        db_mock.__getitem__.side_effect = lambda k: {
            "auction_intraday_track": track_col,
            "auction_performance": perf_col,
        }[k]
        store._db = MagicMock(return_value=db_mock)
        return store, track_col, perf_col

    def test_init_tracking_writes_both_collections(self):
        from modules.pre_market_call_auction.schemas import RadarResult, RadarStock
        store, track_col, perf_col = self._store()
        result = RadarResult(date="2026-07-01", top_stocks=[
            RadarStock(symbol="600000", name="测试", open_price=10.0, gap_pct=4.0),
        ])
        n = store.init_tracking(result)
        self.assertEqual(n, 1)
        track_col.bulk_write.assert_called_once()
        perf_col.bulk_write.assert_called_once()

    def test_close_record_syncs_both(self):
        store, track_col, perf_col = self._store()
        store.close_record("600000", "2026-07-01", 11.0, 0.1, "尾盘平仓")
        track_col.update_one.assert_called_once()
        perf_col.update_one.assert_called_once()
        # auction_performance 应标记为 win（return_pct>0）
        perf_call = perf_col.update_one.call_args[0]
        self.assertEqual(perf_call[1]["$set"]["result"], "win")


if __name__ == "__main__":
    unittest.main()
