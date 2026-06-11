"""AI选股引擎测试：mock DAL / AnalysisEngine / saver，不连 DB / 不发 LLM。"""
import unittest
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import FactorInputs
from modules.ai.engines.picker import PickerEngine, get_progress
from utils.helpers import beijing_now


class TestGetProgressStaleGuard(unittest.TestCase):
    def _db_with_doc(self, doc):
        coll = MagicMock()
        coll.find_one.return_value = doc
        db = MagicMock()
        db.__getitem__.side_effect = lambda n: coll
        return db

    def test_stale_running_doc_reported_dead(self):
        """is_running=True 但 updated_at 超过10分钟未推进 → 视为已中断。"""
        doc = {"key": "current", "is_running": True, "progress": 29,
               "status": "初筛 2600/5209 只...",
               "updated_at": beijing_now() - timedelta(minutes=30)}
        with patch("config.database.DatabaseConfig.get_database",
                   return_value=self._db_with_doc(doc)):
            prog = get_progress()
        self.assertFalse(prog["is_running"])
        self.assertIn("中断", prog["status"])

    def test_fresh_running_doc_untouched(self):
        doc = {"key": "current", "is_running": True, "progress": 50,
               "status": "深度评分 1/50 只...", "updated_at": beijing_now()}
        with patch("config.database.DatabaseConfig.get_database",
                   return_value=self._db_with_doc(doc)):
            prog = get_progress()
        self.assertTrue(prog["is_running"])


class TestRunLock(unittest.TestCase):
    """跨进程选股互斥：另一实例运行中时本次应跳过且不写结果。"""

    def _engine(self):
        dal = MagicMock()
        dal.list_universe.return_value = ["A"]
        dal.get_factor_inputs.side_effect = lambda code, **kw: FactorInputs(
            code=code, name="正常股", closes=[10.0] * 30, volumes=[1000.0] * 30,
            pe=15.0, pb=2.0, main_net_inflow=1e6, total_amount=5e8)
        eng = MagicMock()
        eng.analyze.side_effect = lambda code, **kw: {
            "code": code, "name": code, "scores": {"composite": 60}, "source": "llm"}
        saver = MagicMock()
        return PickerEngine(dal=dal, analysis_engine=eng, result_saver=saver), saver

    def test_lock_held_by_other_run_skips(self):
        coll = MagicMock()
        coll.find_one_and_update.return_value = None   # 抢锁失败
        coll.find_one.return_value = {"key": "current", "is_running": True,
                                      "updated_at": beijing_now()}
        db = MagicMock()
        db.__getitem__.side_effect = lambda n: coll
        engine, saver = self._engine()
        with patch("config.database.DatabaseConfig.get_database", return_value=db):
            result = engine.run(top_n=1, candidate_pool=1)
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result["picks"], [])
        saver.assert_not_called()

    def test_stale_lock_can_be_claimed(self):
        coll = MagicMock()
        coll.find_one_and_update.return_value = {"key": "current"}  # 抢到锁（含僵死场景）
        db = MagicMock()
        db.__getitem__.side_effect = lambda n: coll
        engine, saver = self._engine()
        with patch("config.database.DatabaseConfig.get_database", return_value=db):
            result = engine.run(top_n=1, candidate_pool=1)
        self.assertFalse(result.get("skipped", False))
        self.assertTrue(saver.called)


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

    def _passing_factor_inputs(self, code):
        return FactorInputs(code=code, name="正常股", closes=[10.0] * 30,
                            volumes=[1000.0] * 30, pe=15.0, pb=2.0,
                            main_net_inflow=1e6, total_amount=5e8)

    def test_stage2_runs_in_parallel(self):
        """Stage-2 应真并行：8只×0.4s 在4 worker 下应远快于串行的 3.2s。"""
        import time
        dal = MagicMock()
        dal.list_universe.return_value = [f"C{i}" for i in range(8)]
        dal.get_factor_inputs.side_effect = lambda code, **kw: self._passing_factor_inputs(code)

        eng = MagicMock()
        def slow_analyze(code, **kw):
            time.sleep(0.4)
            return {"code": code, "name": code, "scores": {"composite": 60}, "source": "llm"}
        eng.analyze.side_effect = slow_analyze

        engine = PickerEngine(dal=dal, analysis_engine=eng, result_saver=MagicMock())
        t0 = time.monotonic()
        result = engine.run(top_n=8, candidate_pool=8)
        elapsed = time.monotonic() - t0
        self.assertEqual(len(result["picks"]), 8)
        self.assertLess(elapsed, 2.4)  # 串行需 3.2s，4路并行约 0.8s

    def test_stage2_failure_falls_back_to_factor_score(self):
        """单只深研异常应降级为纯因子评分，不丢股票。"""
        dal = MagicMock()
        dal.list_universe.return_value = ["A", "B"]
        dal.get_factor_inputs.side_effect = lambda code, **kw: self._passing_factor_inputs(code)

        eng = MagicMock()
        def analyze(code, **kw):
            if code == "B":
                raise RuntimeError("LLM boom")
            return {"code": code, "name": code, "scores": {"composite": 80}, "source": "llm"}
        eng.analyze.side_effect = analyze
        eng.analyze_factor_only.side_effect = lambda code: {
            "code": code, "name": code, "scores": {"composite": 40}, "source": "factor"}

        result = PickerEngine(dal=dal, analysis_engine=eng,
                              result_saver=MagicMock()).run(top_n=2, candidate_pool=2)
        by_code = {p["code"]: p for p in result["picks"]}
        self.assertEqual(set(by_code), {"A", "B"})
        self.assertEqual(by_code["B"]["source"], "factor")

    def test_industry_cap_max3_per_industry(self):
        """精选阶段单行业最多3只，超额顺位让给下一行业。"""
        dal = MagicMock()
        codes = [f"G{i}" for i in range(5)] + ["B1", "B2"]
        dal.list_universe.return_value = codes
        dal.get_factor_inputs.side_effect = lambda code, **kw: self._passing_factor_inputs(code)

        eng = MagicMock()
        def analyze(code, **kw):
            if code.startswith("G"):
                return {"code": code, "name": code, "industry": "光模块",
                        "scores": {"composite": 90 - int(code[1])}, "source": "llm"}
            return {"code": code, "name": code, "industry": "银行",
                    "scores": {"composite": 70 - int(code[1])}, "source": "llm"}
        eng.analyze.side_effect = analyze

        result = PickerEngine(dal=dal, analysis_engine=eng,
                              result_saver=MagicMock()).run(top_n=5, candidate_pool=7)
        industries = [p["industry"] for p in result["picks"]]
        self.assertEqual(len(result["picks"]), 5)
        self.assertEqual(industries.count("光模块"), 3)
        self.assertEqual(industries.count("银行"), 2)

    def test_unknown_industry_not_capped(self):
        """行业缺失的股票不应被当作同一行业封顶。"""
        dal = MagicMock()
        dal.list_universe.return_value = [f"U{i}" for i in range(5)]
        dal.get_factor_inputs.side_effect = lambda code, **kw: self._passing_factor_inputs(code)

        eng = MagicMock()
        eng.analyze.side_effect = lambda code, **kw: {
            "code": code, "name": code, "industry": "",
            "scores": {"composite": 80}, "source": "llm"}

        result = PickerEngine(dal=dal, analysis_engine=eng,
                              result_saver=MagicMock()).run(top_n=5, candidate_pool=5)
        self.assertEqual(len(result["picks"]), 5)

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
