"""底座层因子引擎纯函数测试（无 DB / 无网络）"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.factors import (
    trend_score, volume_score, valuation_score, fund_flow_score, composite_score,
)


class TestTrendScore(unittest.TestCase):
    def test_strong_uptrend_scores_high(self):
        closes = [20.0] + [15.0] * 4 + [10.0] * 15
        self.assertEqual(trend_score(closes), 80.0)

    def test_below_ma_scores_low(self):
        closes = [8.0] + [12.0] * 4 + [15.0] * 15
        self.assertEqual(trend_score(closes), 30.0)

    def test_insufficient_data_returns_neutral(self):
        self.assertEqual(trend_score([10.0, 11.0]), 50.0)


class TestVolumeScore(unittest.TestCase):
    def test_volume_spike_scores_above_neutral(self):
        volumes = [3000.0] + [1000.0] * 9
        self.assertGreater(volume_score(volumes), 50.0)

    def test_normal_volume_neutral(self):
        self.assertEqual(volume_score([1000.0] * 10), 50.0)

    def test_insufficient_data_returns_neutral(self):
        self.assertEqual(volume_score([1000.0]), 50.0)


class TestValuationScore(unittest.TestCase):
    def test_reasonable_pe_pb_scores_high(self):
        self.assertEqual(valuation_score(pe=15.0, pb=2.0, ps=0), 75.0)

    def test_overvalued_scores_low(self):
        self.assertEqual(valuation_score(pe=50.0, pb=5.0, ps=0), 30.0)

    def test_missing_data_neutral(self):
        self.assertEqual(valuation_score(pe=None, pb=None, ps=None), 50.0)


class TestFundFlowScore(unittest.TestCase):
    def test_net_inflow_scores_above_neutral(self):
        self.assertGreater(fund_flow_score(main_net_inflow=1e7), 50.0)

    def test_net_outflow_scores_below_neutral(self):
        self.assertLess(fund_flow_score(main_net_inflow=-1e7), 50.0)

    def test_zero_flow_neutral(self):
        self.assertEqual(fund_flow_score(main_net_inflow=0), 50.0)


class TestCompositeScore(unittest.TestCase):
    def test_weighted_average(self):
        scores = {"technical": 80.0, "fundamental": 60.0, "fund_flow": 70.0, "sentiment": 50.0}
        weights = {"technical": 0.4, "fundamental": 0.3, "fund_flow": 0.2, "sentiment": 0.1}
        self.assertAlmostEqual(composite_score(scores, weights), 69.0)

    def test_missing_dimension_skipped_and_renormalized(self):
        scores = {"technical": 80.0, "fundamental": 60.0}
        weights = {"technical": 0.4, "fundamental": 0.3, "fund_flow": 0.2, "sentiment": 0.1}
        self.assertAlmostEqual(composite_score(scores, weights), 71.42857, places=4)

    def test_empty_returns_neutral(self):
        self.assertEqual(composite_score({}, {}), 50.0)


if __name__ == "__main__":
    unittest.main()
