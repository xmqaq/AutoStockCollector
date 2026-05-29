"""个股深度分析引擎测试：注入 mock DAL 和 mock LLMRouter，不连 DB / 不发 LLM。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.dal import StockDataBundle
from modules.ai.foundation.llm_router import LLMResult
from modules.ai.engines.analysis import AnalysisEngine


class TestAnalysisEngine(unittest.TestCase):
    def _bundle(self):
        return StockDataBundle(
            code="SH600519", name="贵州茅台",
            closes=[20.0] + [15.0] * 4 + [10.0] * 15,
            volumes=[3000.0] + [1000.0] * 9,
            pe=15.0, pb=2.0, ps=0,
            main_net_inflow=1e7,
            financial={"roe": 0.18}, news=[], dragon_tiger=[], margin=[],
        )

    def _engine(self, llm_success=True, llm_text="综合判断偏强，注意控制仓位"):
        dal = MagicMock()
        dal.get_stock_bundle.return_value = self._bundle()
        router = MagicMock()
        if llm_success:
            router.chat.return_value = LLMResult(
                success=True, provider="deepseek",
                data={"summary": llm_text, "recommendation": "关注", "risk_factors": ["估值偏高"]},
            )
        else:
            router.chat.return_value = LLMResult(success=False, error="all failed")
        return AnalysisEngine(dal=dal, router=router), dal, router

    def test_returns_four_dimension_scores(self):
        engine, _, _ = self._engine()
        result = engine.analyze("SH600519")
        self.assertEqual(result["code"], "SH600519")
        self.assertEqual(result["name"], "贵州茅台")
        scores = result["scores"]
        self.assertIn("technical", scores)
        self.assertIn("fundamental", scores)
        self.assertIn("fund_flow", scores)
        self.assertIn("sentiment", scores)
        self.assertIn("composite", scores)
        self.assertEqual(scores["technical"], 80.0)

    def test_llm_summary_included_and_sanitized(self):
        engine, _, _ = self._engine(llm_text="该股必涨，建议全仓")
        result = engine.analyze("SH600519")
        self.assertNotIn("必涨", result["llm"]["summary"])
        self.assertNotIn("全仓", result["llm"]["summary"])
        self.assertEqual(result["source"], "llm")

    def test_llm_failure_falls_back_to_factor_only(self):
        engine, _, _ = self._engine(llm_success=False)
        result = engine.analyze("SH600519")
        self.assertEqual(result["source"], "factor")
        self.assertIsNone(result["llm"])
        self.assertIn("composite", result["scores"])

    def test_disclaimer_always_present(self):
        engine, _, _ = self._engine()
        result = engine.analyze("SH600519")
        self.assertIn("参考", result["disclaimer"])


if __name__ == "__main__":
    unittest.main()
