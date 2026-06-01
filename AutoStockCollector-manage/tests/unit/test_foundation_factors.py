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
        # current > ma5 > ma20 + large momentum → should score well above 70
        closes = [20.0] + [15.0] * 4 + [10.0] * 15
        self.assertGreater(trend_score(closes), 70.0)

    def test_below_ma_scores_low(self):
        # current < ma5 < ma20 → should score below 50
        closes = [8.0] + [12.0] * 4 + [15.0] * 15
        self.assertLess(trend_score(closes), 50.0)

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
    def test_reasonable_pe_pb_scores_above_neutral(self):
        # PE=15, PB=2: both reasonable → score > 50
        score = valuation_score(pe=15.0, pb=2.0, ps=0)
        self.assertGreater(score, 50.0)

    def test_high_roe_compensates_high_pe(self):
        # PE=50, but ROE=28 → high quality, should score above plain average
        score_with_roe = valuation_score(pe=50.0, pb=10.0, roe=28.0, gross_margin=70.0)
        score_without = valuation_score(pe=50.0, pb=10.0)
        self.assertGreater(score_with_roe, score_without)

    def test_moutai_like_profile(self):
        # TTM PE~21, PB~8, ROE~28%, gross_margin~91%, debt_ratio low
        score = valuation_score(pe=21.0, pb=8.0, roe=28.0, gross_margin=91.0, debt_ratio=20.0)
        self.assertGreater(score, 60.0)  # 不应因 PB>3 被大幅扣分

    def test_pure_pe_pb_overvalued_not_strongly_penalized(self):
        # PE=50, PB=5, no quality info → near neutral (可能略低于 50)
        score = valuation_score(pe=50.0, pb=5.0, ps=0)
        # 没有 ROE/毛利率信息，不能确定是否高估，评分应在 30-55 之间
        self.assertGreater(score, 30.0)
        self.assertLess(score, 60.0)

    def test_missing_data_neutral(self):
        self.assertEqual(valuation_score(pe=None, pb=None, ps=None), 50.0)

    def test_high_roe_adds_score(self):
        base = valuation_score(pe=None, pb=None)
        high_roe = valuation_score(pe=None, pb=None, roe=28.0)
        self.assertGreater(high_roe, base)

    def test_high_debt_penalizes(self):
        low_debt = valuation_score(pe=None, pb=None, debt_ratio=20.0)
        high_debt = valuation_score(pe=None, pb=None, debt_ratio=80.0)
        self.assertGreater(low_debt, high_debt)

    def test_negative_roe_penalizes(self):
        score = valuation_score(pe=None, pb=None, roe=-10.0)
        self.assertLess(score, 50.0)

    def test_loss_making_pe_penalized(self):
        # PE <= 0 means losses
        score_loss = valuation_score(pe=-1.0, pb=2.0)
        score_ok = valuation_score(pe=15.0, pb=2.0)
        self.assertLess(score_loss, score_ok)


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
