"""买卖建议引擎测试：注入 mock AnalysisEngine 和 mock LLMRouter。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.llm_router import LLMResult
from modules.ai.engines.advice import AdviceEngine


class TestAdviceEngine(unittest.TestCase):
    def _analysis_result(self, composite=72.0):
        return {
            "code": "SH600519", "name": "贵州茅台",
            "scores": {"composite": composite, "technical": 80.0},
            "current_price": 20.0, "source": "llm",
            "llm": {"summary": "偏强"},
        }

    def _engine(self, llm_success=True, llm_text="可逢低关注，注意控制仓位"):
        analysis = MagicMock()
        analysis.analyze.return_value = self._analysis_result()
        router = MagicMock()
        if llm_success:
            router.chat.return_value = LLMResult(
                success=True, provider="deepseek",
                data={"action": "关注", "reason": llm_text, "buy_zone": "18-19", "stop_loss": "16.5", "position_advice": "轻仓试探"},
            )
        else:
            router.chat.return_value = LLMResult(success=False, error="fail")
        return AdviceEngine(analysis_engine=analysis, router=router), analysis, router

    def test_advice_includes_action_and_sanitized_reason(self):
        engine, _, _ = self._engine(llm_text="该股必涨，建议全仓")
        result = engine.advise("SH600519")
        self.assertNotIn("必涨", result["advice"]["reason"])
        self.assertNotIn("全仓", result["advice"]["reason"])
        self.assertEqual(result["source"], "llm")

    def test_passes_position_context_to_prompt(self):
        engine, _, router = self._engine()
        engine.advise("SH600519", cost=18.0, position=0.3)
        prompt = router.chat.call_args[0][0]
        self.assertIn("18.0", prompt)
        self.assertIn("0.3", prompt)

    def test_llm_failure_falls_back_to_rule_based(self):
        engine, _, _ = self._engine(llm_success=False)
        result = engine.advise("SH600519")
        self.assertEqual(result["source"], "rule")
        self.assertIn(result["advice"]["action"], ["关注", "买入参考", "持有"])

    def test_low_score_rule_advice_is_cautious(self):
        engine, analysis, _ = self._engine(llm_success=False)
        analysis.analyze.return_value = self._analysis_result(composite=30.0)
        result = engine.advise("SH600519")
        self.assertEqual(result["source"], "rule")
        self.assertIn(result["advice"]["action"], ["回避", "观望", "减仓"])

    def test_buy_zone_and_stop_loss_sanitized(self):
        from unittest.mock import MagicMock
        from modules.ai.foundation.llm_router import LLMResult
        analysis = MagicMock()
        analysis.analyze.return_value = self._analysis_result()
        router = MagicMock()
        router.chat.return_value = LLMResult(
            success=True, provider="deepseek",
            data={"action": "关注", "reason": "稳健", "buy_zone": "必涨区间18-19",
                  "stop_loss": "保证收益16.5", "position_advice": "轻仓"},
        )
        engine = AdviceEngine(analysis_engine=analysis, router=router)
        result = engine.advise("SH600519")
        self.assertNotIn("必涨", result["advice"]["buy_zone"])
        self.assertNotIn("保证收益", result["advice"]["stop_loss"])


if __name__ == "__main__":
    unittest.main()
