"""AI选股引擎测试：mock DAL / AnalysisEngine / saver，不连 DB / 不发 LLM。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import FactorInputs
from modules.ai.engines.picker import PickerEngine


class TestPickerEngine(unittest.TestCase):
    def _dal(self):
        dal = MagicMock()
        dal.list_universe.return_value = ["A", "B", "C", "D", "E"]

        def factor_inputs(code, **kw):
            mapping = {
                "A": [30.0] + [20.0] * 4 + [10.0] * 25,
                "B": [25.0] + [20.0] * 4 + [12.0] * 25,
                "C": [18.0] + [18.0] * 29,
                "D": [12.0] + [15.0] * 4 + [18.0] * 25,
                "E": [8.0] + [14.0] * 4 + [18.0] * 25,
            }
            return FactorInputs(code=code, closes=mapping[code], volumes=[1000.0] * 30, pe=15.0, pb=2.0, main_net_inflow=1e6)
        dal.get_factor_inputs.side_effect = factor_inputs
        return dal

    def _analysis_engine(self):
        eng = MagicMock()
        def analyze(code, **kw):
            return {"code": code, "name": code, "scores": {"composite": {"A": 85, "B": 80, "C": 60}.get(code, 50)}, "source": "llm", "llm": {"summary": "x"}}
        eng.analyze.side_effect = analyze
        return eng

    def test_two_stage_funnel_returns_top_n(self):
        saver = MagicMock()
        engine = PickerEngine(dal=self._dal(), analysis_engine=self._analysis_engine(), result_saver=saver)
        result = engine.run(top_n=2, candidate_pool=3)
        self.assertEqual(len(result["picks"]), 2)
        self.assertEqual(result["picks"][0]["code"], "A")

    def test_stage1_limits_candidate_pool(self):
        analysis = self._analysis_engine()
        engine = PickerEngine(dal=self._dal(), analysis_engine=analysis, result_saver=MagicMock())
        engine.run(top_n=2, candidate_pool=3)
        self.assertEqual(analysis.analyze.call_count, 3)

    def test_results_saved(self):
        saver = MagicMock()
        engine = PickerEngine(dal=self._dal(), analysis_engine=self._analysis_engine(), result_saver=saver)
        engine.run(top_n=2, candidate_pool=3)
        self.assertTrue(saver.called)

    def test_empty_universe_returns_empty(self):
        dal = self._dal()
        dal.list_universe.return_value = []
        engine = PickerEngine(dal=dal, analysis_engine=self._analysis_engine(), result_saver=MagicMock())
        result = engine.run(top_n=2, candidate_pool=3)
        self.assertEqual(result["picks"], [])

    def test_hard_filters_exclude_st_short_kline_low_liquidity(self):
        """ST/退市/次新(K线不足)/低流动性 股票应在初筛前被硬性剔除。"""
        dal = MagicMock()
        dal.list_universe.return_value = ["GOOD", "ST1", "TUI", "NEW", "ILLIQ"]

        def factor_inputs(code, **kw):
            base = dict(closes=[10.0] * 30, volumes=[1000.0] * 30, pe=15.0,
                        pb=2.0, main_net_inflow=1e6, total_amount=5e8)
            if code == "ST1":
                return FactorInputs(code=code, name="*ST九鼎", **base)
            if code == "TUI":
                return FactorInputs(code=code, name="某某退", **base)
            if code == "NEW":
                return FactorInputs(code=code, name="次新股",
                                    **{**base, "closes": [10.0] * 5, "volumes": [1000.0] * 5})
            if code == "ILLIQ":
                return FactorInputs(code=code, name="僵尸股", **{**base, "total_amount": 1e6})
            return FactorInputs(code=code, name="正常股", **base)
        dal.get_factor_inputs.side_effect = factor_inputs

        analysis = self._analysis_engine()
        result = PickerEngine(dal=dal, analysis_engine=analysis,
                              result_saver=MagicMock()).run(top_n=5, candidate_pool=5)
        analyzed = {c.args[0] for c in analysis.analyze.call_args_list}
        self.assertEqual(analyzed, {"GOOD"})
        self.assertEqual(result["filtered_count"], 4)
        self.assertEqual(result["filtered_detail"]["st"], 2)
        self.assertEqual(result["filtered_detail"]["insufficient_kline"], 1)
        self.assertEqual(result["filtered_detail"]["low_liquidity"], 1)

    def test_missing_total_amount_not_filtered(self):
        """total_amount 缺失（数据断档）不应被误杀为低流动性。"""
        engine = PickerEngine(dal=MagicMock(), analysis_engine=MagicMock(),
                              result_saver=MagicMock())
        fi = FactorInputs(code="X", name="正常股", closes=[10.0] * 30,
                          volumes=[1000.0] * 30, total_amount=None)
        self.assertIsNone(engine._hard_filter(fi))

    def test_stage1_requests_60_klines(self):
        """初筛取60条K线，保证 MA60/强多头排列可计算。"""
        dal = self._dal()
        engine = PickerEngine(dal=dal, analysis_engine=self._analysis_engine(),
                              result_saver=MagicMock())
        engine.run(top_n=2, candidate_pool=3)
        _, kwargs = dal.get_factor_inputs.call_args
        self.assertEqual(kwargs.get("kline_limit"), 60)

    def test_screen_score_redistributes_unavailable_technical(self):
        """K线不足时技术面应标记不可用并重分配权重，而非按50分中性值计入。"""
        engine = PickerEngine(dal=MagicMock(), analysis_engine=MagicMock(),
                              result_saver=MagicMock())
        fi = FactorInputs(
            code="X", closes=[10.0], volumes=[100.0], pe=10.0, pb=0.9,
            roe=26.0, revenue_growth=35.0, profit_growth=35.0,
            gross_margin=65.0, debt_ratio=25.0,
            main_net_inflow=2e8, total_amount=2e9, turnover_rate=3.0,
        )
        # 基本面/资金面/估值面均为满分，技术面K线不足：剔除权重后综合应为100
        self.assertEqual(engine._screen_score(fi), 100.0)


if __name__ == "__main__":
    unittest.main()
