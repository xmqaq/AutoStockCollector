"""
数据校验模块测试
"""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.validator.validator import ValidationResult, DataIntegrityChecker


class TestValidationResult(unittest.TestCase):
    def test_initial_state(self):
        result = ValidationResult("SH600000", "kline")

        self.assertTrue(result.is_valid)
        self.assertEqual(result.code, "SH600000")
        self.assertEqual(result.data_type, "kline")
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_add_error(self):
        result = ValidationResult("SH600000", "kline")
        result.add_error("Missing date field")

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Missing date field", result.errors)

    def test_add_warning(self):
        result = ValidationResult("SH600000", "kline")
        result.add_warning("Optional field missing")

        self.assertEqual(len(result.warnings), 1)

    def test_set_completeness(self):
        result = ValidationResult("SH600000", "kline")
        result.set_completeness(85.5)

        self.assertEqual(result.completeness_score, 85.5)

    def test_completeness_bounds(self):
        result = ValidationResult("SH600000", "kline")
        result.set_completeness(150)
        self.assertEqual(result.completeness_score, 100.0)

        result.set_completeness(-10)
        self.assertEqual(result.completeness_score, 0.0)

    def test_to_dict(self):
        result = ValidationResult("SH600000", "kline")
        result.add_error("Test error")
        result.set_completeness(75.0)

        d = result.to_dict()

        self.assertEqual(d["code"], "SH600000")
        self.assertEqual(d["data_type"], "kline")
        self.assertFalse(d["is_valid"])
        self.assertIn("Test error", d["errors"])
        self.assertEqual(d["completeness_score"], 75.0)


class TestDataIntegrityChecker(unittest.TestCase):
    def test_check_price_sequence_valid(self):
        klines = [
            {"date": "2024-01-01", "open": 10, "high": 11, "low": 9.5, "close": 10.5},
            {"date": "2024-01-02", "open": 10.5, "high": 11.5, "low": 10, "close": 11},
        ]

        errors = DataIntegrityChecker.check_price_sequence(klines)
        self.assertEqual(len(errors), 0)

    def test_check_price_sequence_invalid(self):
        klines = [
            {"date": "2024-01-01", "open": 10, "high": 9, "low": 9.5, "close": 10.5},
        ]

        errors = DataIntegrityChecker.check_price_sequence(klines)
        self.assertEqual(len(errors), 1)
        self.assertIn("High < Low", errors[0])

    def test_check_volume_anomaly_normal(self):
        klines = [
            {"date": "2024-01-01", "volume": 1000000},
            {"date": "2024-01-02", "volume": 1200000},
            {"date": "2024-01-03", "volume": 1100000},
            {"date": "2024-01-04", "volume": 1050000},
        ]

        errors = DataIntegrityChecker.check_volume_anomaly(klines, threshold=5.0)
        self.assertEqual(len(errors), 0)

    def test_check_volume_anomaly_detected(self):
        klines = [
            {"date": "2024-01-01", "volume": 1000000},
            {"date": "2024-01-02", "volume": 1200000},
            {"date": "2024-01-03", "volume": 10000000},
            {"date": "2024-01-04", "volume": 1100000},
        ]

        errors = DataIntegrityChecker.check_volume_anomaly(klines, threshold=2.0)
        self.assertEqual(len(errors), 1)
        self.assertIn("2024-01-03", errors[0])

    def test_check_price_jump_normal(self):
        klines = [
            {"date": "2024-01-01", "close": 100},
            {"date": "2024-01-02", "close": 101},
            {"date": "2024-01-03", "close": 100.5},
        ]

        errors = DataIntegrityChecker.check_price_jump(klines, threshold=20.0)
        self.assertEqual(len(errors), 0)

    def test_check_price_jump_detected(self):
        klines = [
            {"date": "2024-01-01", "close": 100},
            {"date": "2024-01-02", "close": 130},
            {"date": "2024-01-03", "close": 125},
        ]

        errors = DataIntegrityChecker.check_price_jump(klines, threshold=20.0)
        self.assertEqual(len(errors), 1)
        self.assertIn("30", errors[0])


if __name__ == "__main__":
    unittest.main()