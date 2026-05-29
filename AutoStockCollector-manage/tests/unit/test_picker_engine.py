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


if __name__ == "__main__":
    unittest.main()
