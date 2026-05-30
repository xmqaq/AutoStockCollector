"""盯盘融合引擎测试：mock watchlist_manager/advice_engine/config/saver，不连 DB/不发 LLM。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.monitor.monitor_engine import MonitorEngine


class TestMonitorEngine(unittest.TestCase):
    def _engine(self, threshold_alerts, advice_ok=True):
        wm = MagicMock()
        wm.monitor_alerts.return_value = threshold_alerts
        advice = MagicMock()
        if advice_ok:
            advice.advise.return_value = {
                "advice": {"action": "减仓", "reason": "回调风险"}, "composite": 45.0,
            }
        else:
            advice.advise.side_effect = RuntimeError("llm down")
        saved = []
        engine = MonitorEngine(
            watchlist_manager=wm, advice_engine=advice,
            config_loader=lambda uid: {"price_rise_threshold": 5.0, "price_fall_threshold": 3.0, "volume_ratio_threshold": 2.0},
            alert_saver=lambda doc: saved.append(doc),
        )
        return engine, advice, saved

    def test_triggered_alert_enriched_with_ai_advice(self):
        engine, advice, saved = self._engine([
            {"code": "SH600519", "type": "price_alert", "message": "价格异动: -6.0%"},
        ])
        result = engine.scan("default")
        self.assertEqual(len(result), 1)
        self.assertEqual(len(saved), 1)
        self.assertIn("ai_advice", saved[0])
        self.assertEqual(saved[0]["ai_advice"]["action"], "减仓")
        self.assertEqual(saved[0]["code"], "SH600519")
        self.assertEqual(saved[0]["type"], "price")
        advice.advise.assert_called_once_with("SH600519")

    def test_no_threshold_alert_means_no_llm_call(self):
        engine, advice, saved = self._engine([])
        result = engine.scan("default")
        self.assertEqual(result, [])
        self.assertEqual(saved, [])
        advice.advise.assert_not_called()  # 成本闸门

    def test_advice_failure_still_saves_threshold_alert(self):
        engine, advice, saved = self._engine([
            {"code": "SH600519", "type": "volume_alert", "message": "成交量异常放大: 3.0倍"},
        ], advice_ok=False)
        result = engine.scan("default")
        self.assertEqual(len(saved), 1)
        self.assertIsNone(saved[0]["ai_advice"])  # 降级：告警不丢
        self.assertEqual(saved[0]["type"], "volume")

    def test_volume_multiplier_mapped_from_config(self):
        engine, advice, saved = self._engine([])
        engine.scan("default")
        _, kwargs = engine.watchlist_manager.monitor_alerts.call_args
        self.assertEqual(kwargs.get("volume_multiplier"), 2.0)
        # price_change_threshold 取 rise/fall 较小值，确保涨跌都能触发
        self.assertEqual(kwargs.get("price_change_threshold"), 3.0)


if __name__ == "__main__":
    unittest.main()
