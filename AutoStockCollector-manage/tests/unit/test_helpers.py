"""
工具模块测试
"""
import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.helpers import (
    format_date,
    parse_date,
    get_trading_days,
    is_trading_day,
    validate_stock_code,
    normalize_stock_code,
    calculate_change_percent,
    chunk_list,
    safe_float,
    safe_int,
    safe_str,
    DateRange,
)


class TestDateHelpers(unittest.TestCase):
    def test_format_date(self):
        date = datetime(2024, 1, 15)
        result = format_date(date)
        self.assertEqual(result, "2024-01-15")

    def test_parse_date(self):
        date_str = "2024-01-15"
        result = parse_date(date_str)
        self.assertEqual(result, datetime(2024, 1, 15))

    def test_get_trading_days(self):
        days = get_trading_days("2024-01-02", "2024-01-05")
        self.assertIn("2024-01-02", days)
        self.assertIn("2024-01-03", days)
        self.assertIn("2024-01-04", days)
        self.assertIn("2024-01-05", days)
        self.assertEqual(len(days), 4)

    def test_is_trading_day(self):
        monday = datetime(2024, 1, 15)
        saturday = datetime(2024, 1, 20)

        self.assertTrue(is_trading_day(monday))
        self.assertFalse(is_trading_day(saturday))


class TestStockCodeHelpers(unittest.TestCase):
    def test_validate_stock_code_valid(self):
        self.assertTrue(validate_stock_code("SH600000"))
        self.assertTrue(validate_stock_code("SZ000001"))
        self.assertTrue(validate_stock_code("sh600000"))
        self.assertTrue(validate_stock_code("sz000001"))

    def test_validate_stock_code_invalid(self):
        self.assertFalse(validate_stock_code("invalid"))
        self.assertFalse(validate_stock_code("123456"))
        self.assertFalse(validate_stock_code("SZ12345"))
        self.assertFalse(validate_stock_code(""))

    def test_normalize_stock_code(self):
        self.assertEqual(normalize_stock_code("600000"), "SH600000")
        self.assertEqual(normalize_stock_code("000001"), "SZ000001")
        self.assertEqual(normalize_stock_code("SH600000"), "SH600000")
        self.assertEqual(normalize_stock_code("sz000001"), "SZ000001")


class TestNumericHelpers(unittest.TestCase):
    def test_calculate_change_percent(self):
        self.assertEqual(calculate_change_percent(110, 100), 10.0)
        self.assertEqual(calculate_change_percent(90, 100), -10.0)
        self.assertEqual(calculate_change_percent(100, 0), 0.0)

    def test_safe_float(self):
        self.assertEqual(safe_float("10.5"), 10.5)
        self.assertEqual(safe_float(None), 0.0)
        self.assertEqual(safe_float("invalid"), 0.0)
        self.assertEqual(safe_float(42), 42.0)

    def test_safe_int(self):
        self.assertEqual(safe_int("10"), 10)
        self.assertEqual(safe_int(None), 0)
        self.assertEqual(safe_int("invalid"), 0)
        self.assertEqual(safe_int(42.9), 42)

    def test_safe_str(self):
        self.assertEqual(safe_str(123), "123")
        self.assertEqual(safe_str(None), "")
        self.assertEqual(safe_str("hello"), "hello")


class TestChunkList(unittest.TestCase):
    def test_chunk_list_basic(self):
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        chunks = chunk_list(items, 3)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], [1, 2, 3])
        self.assertEqual(chunks[1], [4, 5, 6])
        self.assertEqual(chunks[2], [7, 8, 9])

    def test_chunk_list_unequal(self):
        items = [1, 2, 3, 4, 5]
        chunks = chunk_list(items, 2)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], [1, 2])
        self.assertEqual(chunks[1], [3, 4])
        self.assertEqual(chunks[2], [5])

    def test_chunk_list_empty(self):
        items = []
        chunks = chunk_list(items, 3)
        self.assertEqual(len(chunks), 0)


class TestDateRange(unittest.TestCase):
    def test_date_range_iteration(self):
        dr = DateRange("2024-01-01", "2024-01-05")
        dates = list(dr)

        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[0].day, 1)
        self.assertEqual(dates[-1].day, 5)

    def test_date_range_trading_days(self):
        dr = DateRange("2024-01-01", "2024-01-07")
        trading_days = dr.trading_days_only()

        self.assertEqual(len(trading_days), 5)


if __name__ == "__main__":
    unittest.main()