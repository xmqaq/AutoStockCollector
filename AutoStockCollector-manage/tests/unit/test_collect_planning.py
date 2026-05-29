"""采集任务规划纯函数测试（不依赖 DB / scheduler）"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.routes import _build_history_tasks, RANGE_TYPES, _compute_update_latest_tasks


class TestBuildHistoryTasks(unittest.TestCase):
    def test_history_only_contains_range_types(self):
        tasks = _build_history_tasks("2025-01-01", "2025-12-31")
        types = {t["task_type"] for t in tasks}
        # 历史采集只应包含区间类，不含快照/名录类
        self.assertEqual(types, set(RANGE_TYPES))
        self.assertNotIn("news", types)
        self.assertNotIn("fund_flow", types)
        self.assertNotIn("sector", types)
        self.assertNotIn("stock_info", types)

    def test_history_passes_dates_to_range_types(self):
        tasks = _build_history_tasks("2025-01-01", "2025-12-31", ["kline"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["params"]["start_date"], "2025-01-01")
        self.assertEqual(tasks[0]["params"]["end_date"], "2025-12-31")

    def test_history_task_types_filter_ignores_snapshot(self):
        # 即使显式传入快照类，也不应产出
        tasks = _build_history_tasks("2025-01-01", "2025-12-31", ["kline", "news"])
        types = {t["task_type"] for t in tasks}
        self.assertEqual(types, {"kline"})


class TestComputeUpdateLatest(unittest.TestCase):
    TODAY = "2026-05-29"

    def _stats(self, **overrides):
        base = {
            "kline": {"record_count": 10, "date_from": "2025-01-01", "date_to": "2026-05-20"},
            "financial": {"record_count": 5, "date_from": "2024-01-01", "date_to": "2025-12-31"},
            "dragon_tiger": {"record_count": 3, "date_from": "2026-05-01", "date_to": "2026-05-29"},
            "margin": {"record_count": 0, "date_from": None, "date_to": None},
            "news": {"record_count": 100, "date_from": None, "date_to": None},
            "fund_flow": {"record_count": 50, "date_from": None, "date_to": None},
            "sector": {"record_count": 90, "date_from": None, "date_to": None},
            "stock_info": {"record_count": 200, "date_from": None, "date_to": None},
        }
        base.update(overrides)
        return base

    def test_range_type_resumes_from_next_day(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["kline"], self.TODAY)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_type"], "kline")
        self.assertEqual(tasks[0]["params"]["start_date"], "2026-05-21")  # date_to + 1
        self.assertEqual(tasks[0]["params"]["end_date"], self.TODAY)

    def test_range_type_already_latest_is_skipped(self):
        # dragon_tiger date_to == today，应跳过
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["dragon_tiger"], self.TODAY)
        self.assertEqual(tasks, [])
        self.assertIn("dragon_tiger", skipped)

    def test_range_type_no_data_uses_one_year_lookback(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["margin"], self.TODAY)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["params"]["start_date"], "2025-05-29")  # today - 365d
        self.assertEqual(tasks[0]["params"]["end_date"], self.TODAY)

    def test_snapshot_type_has_no_dates(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["news", "fund_flow", "sector"], self.TODAY)
        types = {t["task_type"] for t in tasks}
        self.assertEqual(types, {"news", "fund_flow", "sector"})
        for t in tasks:
            self.assertNotIn("start_date", t["params"])
        news = next(t for t in tasks if t["task_type"] == "news")
        self.assertEqual(news["params"]["limit"], 500)

    def test_catalog_type_uses_incremental_mode(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), ["stock_info"], self.TODAY)
        self.assertEqual(tasks[0]["params"], {"mode": "incremental"})

    def test_default_selects_all_eight_types(self):
        tasks, skipped = _compute_update_latest_tasks(self._stats(), None, self.TODAY)
        handled = {t["task_type"] for t in tasks} | set(skipped)
        self.assertEqual(handled, set(RANGE_TYPES + ["news", "fund_flow", "sector", "stock_info"]))


if __name__ == "__main__":
    unittest.main()
