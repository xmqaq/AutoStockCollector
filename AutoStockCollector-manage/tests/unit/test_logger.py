"""
日志模块测试
"""
import unittest
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logger import LogManager, get_logger, clean_old_logs


class TestLogManager(unittest.TestCase):
    def setUp(self):
        self.test_log_dir = tempfile.mkdtemp()

    def test_logger_creation(self):
        logger = get_logger("test_logger")
        self.assertIsNotNone(logger)

        logger.info("Test message")

    def test_multiple_loggers(self):
        logger1 = get_logger("test1")
        logger2 = get_logger("test2")

        self.assertIsNotNone(logger1)
        self.assertIsNotNone(logger2)

        logger1.info("Logger 1 message")
        logger2.info("Logger 2 message")

    def test_log_levels(self):
        logger = get_logger("test_levels")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_log_with_extra_data(self):
        logger = get_logger("test_extra")

        logger.info("Test with extra data", extra_field="extra_value")

    def test_clean_old_logs(self):
        pass


class TestGetLogger(unittest.TestCase):
    def test_get_logger_same_instance(self):
        logger1 = get_logger("singleton_test")
        logger2 = get_logger("singleton_test")

        self.assertIs(logger1, logger2)

    def test_get_logger_different_names(self):
        logger1 = get_logger("name1")
        logger2 = get_logger("name2")

        self.assertIsNot(logger1, logger2)


if __name__ == "__main__":
    unittest.main()