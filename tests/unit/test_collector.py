"""
数据采集模块测试
"""
import unittest
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.collector.base import BaseCollector, ProgressTracker
from core.collector.kline_collector import KlineCollector


class TestBaseCollector(unittest.TestCase):
    def setUp(self):
        self.collector = KlineCollector()

    def test_normalize_code(self):
        self.assertEqual(self.collector._normalize_code("600000"), "SH600000")
        self.assertEqual(self.collector._normalize_code("000001"), "SZ000001")
        self.assertEqual(self.collector._normalize_code("SH600000"), "SH600000")
        self.assertEqual(self.collector._normalize_code("sz000001"), "SZ000001")
        self.assertEqual(self.collector._normalize_code("300001"), "SZ300001")

    def test_validate_required_fields(self):
        data = {"code": "SH600000", "date": "2024-01-01", "close": 10.0}
        self.assertTrue(self.collector.validate_required_fields(data, ["code", "date"]))

        data_missing = {"code": "SH600000"}
        self.assertFalse(self.collector.validate_required_fields(data_missing, ["code", "date"]))

    def test_clean_numeric_fields(self):
        data = {
            "close": "10.5",
            "volume": "1000000",
            "name": "Test"
        }
        result = self.collector.clean_numeric_fields(data, ["close", "volume"])

        self.assertEqual(result["close"], 10.5)
        self.assertEqual(result["volume"], 1000000.0)
        self.assertEqual(result["name"], "Test")


class TestProgressTracker(unittest.TestCase):
    def test_initial_state(self):
        tracker = ProgressTracker(total=100)

        self.assertEqual(tracker.total, 100)
        self.assertEqual(tracker.current, 0)
        self.assertEqual(tracker.success, 0)
        self.assertEqual(tracker.failed, 0)

    def test_increment_success(self):
        tracker = ProgressTracker(total=100)
        tracker.increment(success=True)

        self.assertEqual(tracker.current, 1)
        self.assertEqual(tracker.success, 1)
        self.assertEqual(tracker.failed, 0)

    def test_increment_failure(self):
        tracker = ProgressTracker(total=100)
        tracker.increment(success=False)

        self.assertEqual(tracker.current, 1)
        self.assertEqual(tracker.success, 0)
        self.assertEqual(tracker.failed, 1)

    def test_get_progress(self):
        tracker = ProgressTracker(total=100)
        tracker.current = 50

        self.assertEqual(tracker.get_progress(), 50.0)

    def test_get_progress_zero_total(self):
        tracker = ProgressTracker(total=0)
        tracker.current = 50

        self.assertEqual(tracker.get_progress(), 0.0)

    def test_get_stats(self):
        tracker = ProgressTracker(total=100)
        tracker.current = 50
        tracker.success = 45
        tracker.failed = 5

        stats = tracker.get_stats()

        self.assertEqual(stats["total"], 100)
        self.assertEqual(stats["current"], 50)
        self.assertEqual(stats["success"], 45)
        self.assertEqual(stats["failed"], 5)
        self.assertEqual(stats["progress"], 50.0)


if __name__ == "__main__":
    unittest.main()