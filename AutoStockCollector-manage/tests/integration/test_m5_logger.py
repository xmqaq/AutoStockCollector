"""
M5日志模块测试 - 日志记录与查询验证
包含日志记录功能、日志级别控制、日志文件管理、日志查询等功能测试
"""
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logger import LogManager, get_logger, clean_old_logs, init_task_logger
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM5日志模块(unittest.TestCase):
    """M5日志模块 - 日志记录与查询验证"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        logger.info("=" * 80)
        logger.info("M5日志模块测试开始 - 日志记录与查询验证")
        logger.info("=" * 80)

        cls.log_dir = Path(__file__).parent.parent.parent / "logs"
        cls.log_dir.mkdir(parents=True, exist_ok=True)

    def test_5_001_log_manager_initialization(self):
        """测试5.1: 日志管理器初始化"""
        logger.info("\n[测试5.1] 日志管理器初始化测试")

        try:
            log_manager = LogManager("test_init", log_level="INFO", log_type="normal")

            self.assertIsNotNone(log_manager)
            self.assertEqual(log_manager.name, "test_init")
            self.assertEqual(log_manager.log_level, "INFO")
            self.assertEqual(log_manager.log_type, "normal")
            self.assertIsNotNone(log_manager.logger)

            logger.info(f"  日志名称: {log_manager.name}")
            logger.info(f"  日志级别: {log_manager.log_level}")
            logger.info(f"  日志类型: {log_manager.log_type}")
            logger.info("✓ 日志管理器初始化成功")

        except Exception as e:
            logger.error(f"✗ 日志管理器初始化失败: {e}")
            self.fail(f"日志管理器初始化失败: {e}")

    def test_5_002_log_levels(self):
        """测试5.2: 日志级别配置"""
        logger.info("\n[测试5.2] 日志级别配置测试")

        try:
            log_levels = LogManager.LOG_LEVELS

            self.assertIn("DEBUG", log_levels)
            self.assertIn("INFO", log_levels)
            self.assertIn("WARNING", log_levels)
            self.assertIn("ERROR", log_levels)
            self.assertIn("CRITICAL", log_levels)

            logger.info(f"  支持的日志级别: {list(log_levels.keys())}")
            logger.info("✓ 日志级别配置测试通过")

        except Exception as e:
            logger.error(f"✗ 日志级别配置测试失败: {e}")
            self.fail(f"日志级别配置测试失败: {e}")

    def test_5_003_retention_days(self):
        """测试5.3: 日志保留期限配置"""
        logger.info("\n[测试5.3] 日志保留期限配置测试")

        try:
            retention_days = LogManager.RETENTION_DAYS

            self.assertIn("normal", retention_days)
            self.assertIn("error", retention_days)
            self.assertEqual(retention_days["normal"], 30)
            self.assertEqual(retention_days["error"], 60)

            logger.info(f"  保留期限配置: {retention_days}")
            logger.info("✓ 日志保留期限配置测试通过")

        except Exception as e:
            logger.error(f"✗ 日志保留期限配置测试失败: {e}")
            self.fail(f"日志保留期限配置测试失败: {e}")

    def test_5_004_log_message_types(self):
        """测试5.4: 日志消息类型测试"""
        logger.info("\n[测试5.4] 日志消息类型测试")

        try:
            log_manager = LogManager("test_types", log_level="DEBUG", log_type="normal")

            log_manager.debug("Debug message test")
            log_manager.info("Info message test")
            log_manager.warning("Warning message test")
            log_manager.error("Error message test")
            log_manager.critical("Critical message test")

            logger.info("  已记录所有级别日志消息")
            logger.info("✓ 日志消息类型测试通过")

        except Exception as e:
            logger.error(f"✗ 日志消息类型测试失败: {e}")
            self.fail(f"日志消息类型测试失败: {e}")

    def test_5_005_get_logger_singleton(self):
        """测试5.5: 日志获取单例模式"""
        logger.info("\n[测试5.5] 日志获取单例模式测试")

        try:
            logger1 = get_logger("test_singleton", log_level="INFO")
            logger2 = get_logger("test_singleton", log_level="INFO")

            self.assertIs(logger1, logger2)

            logger3 = get_logger("test_singleton_diff", log_level="INFO")
            self.assertIsNot(logger1, logger3)

            logger.info("✓ 日志获取单例模式测试通过")

        except Exception as e:
            logger.error(f"✗ 日志获取单例模式测试失败: {e}")
            self.fail(f"日志获取单例模式测试失败: {e}")

    def test_5_006_log_file_creation(self):
        """测试5.6: 日志文件创建"""
        logger.info("\n[测试5.6] 日志文件创建测试")

        try:
            log_manager = LogManager("test_file", log_level="INFO", log_type="normal")

            log_manager.info("Test log message for file creation")

            self.assertIsNotNone(log_manager.logger)
            self.assertGreater(len(log_manager.logger.handlers), 0)

            logger.info(f"  日志管理器: {log_manager.name}")
            logger.info(f"  处理器数量: {len(log_manager.logger.handlers)}")
            logger.info("✓ 日志文件创建测试通过")

        except Exception as e:
            logger.error(f"✗ 日志文件创建测试失败: {e}")
            self.fail(f"日志文件创建测试失败: {e}")

    def test_5_007_log_directory_structure(self):
        """测试5.7: 日志目录结构"""
        logger.info("\n[测试5.7] 日志目录结构测试")

        try:
            log_dir = LogManager._log_dir

            self.assertTrue(log_dir.exists(), "日志目录应该存在")
            self.assertTrue(log_dir.is_dir(), "日志路径应该是目录")

            log_files = list(log_dir.glob("*.log"))
            logger.info(f"  日志目录: {log_dir}")
            logger.info(f"  日志文件数量: {len(log_files)}")

            logger.info("✓ 日志目录结构测试通过")

        except Exception as e:
            logger.error(f"✗ 日志目录结构测试失败: {e}")
            self.fail(f"日志目录结构测试失败: {e}")

    def test_5_008_init_task_logger(self):
        """测试5.8: 任务日志初始化"""
        logger.info("\n[测试5.8] 任务日志初始化测试")

        try:
            task_id = f"test_task_{int(time.time())}"
            task_logger = init_task_logger(task_id)

            self.assertIsNotNone(task_logger)
            self.assertTrue(task_logger.name.startswith("task_"))

            task_logger.info("Task log message")

            logger.info(f"  任务ID: {task_id}")
            logger.info(f"  任务日志器名称: {task_logger.name}")
            logger.info("✓ 任务日志初始化测试通过")

        except Exception as e:
            logger.error(f"✗ 任务日志初始化测试失败: {e}")
            self.fail(f"任务日志初始化测试失败: {e}")

    def test_5_009_log_format(self):
        """测试5.9: 日志格式验证"""
        logger.info("\n[测试5.9] 日志格式验证测试")

        try:
            log_manager = LogManager("test_format", log_level="INFO", log_type="normal")

            test_message = "Test format message"
            log_manager.info(test_message)

            log_file = self.log_dir / "test_format_normal.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1]
                        logger.info(f"  最新日志行: {last_line.strip()[:100]}")

                        has_timestamp = " - " in last_line
                        has_level = "INFO" in last_line
                        has_message = test_message in last_line

                        self.assertTrue(has_timestamp, "日志应包含时间戳")
                        self.assertTrue(has_level, "日志应包含级别")
                        self.assertTrue(has_message, "日志应包含消息")

            logger.info("✓ 日志格式验证测试通过")

        except Exception as e:
            logger.error(f"✗ 日志格式验证测试失败: {e}")
            self.fail(f"日志格式验证测试失败: {e}")

    def test_5_010_clean_old_logs(self):
        """测试5.10: 旧日志清理功能"""
        logger.info("\n[测试5.10] 旧日志清理功能测试")

        try:
            test_old_log = self.log_dir / "old_test.log"
            test_old_log.write_text("Old log content", encoding="utf-8")

            original_mtime = datetime.now() - timedelta(days=35)
            os.utime(test_old_log, (original_mtime.timestamp(), original_mtime.timestamp()))

            clean_old_logs(days=30)

            log_still_exists = test_old_log.exists()
            logger.info(f"  旧日志清理结果: {'已删除' if not log_still_exists else '仍存在'}")

            logger.info("✓ 旧日志清理功能测试通过")

        except Exception as e:
            logger.error(f"✗ 旧日志清理功能测试失败: {e}")
            self.fail(f"旧日志清理功能测试失败: {e}")

    def test_5_011_log_levels_filtering(self):
        """测试5.11: 日志级别过滤"""
        logger.info("\n[测试5.11] 日志级别过滤测试")

        try:
            logger_debug = get_logger("test_filter_debug", log_level="DEBUG")
            logger_error = get_logger("test_filter_error", log_level="ERROR")

            self.assertEqual(logger_debug.log_level, "DEBUG")
            self.assertEqual(logger_error.log_level, "ERROR")

            debug_value = LogManager.LOG_LEVELS.get(logger_debug.log_level)
            error_value = LogManager.LOG_LEVELS.get(logger_error.log_level)

            self.assertLess(debug_value, error_value, "DEBUG级别应该低于ERROR级别")

            logger.info(f"  DEBUG级别数值: {debug_value}")
            logger.info(f"  ERROR级别数值: {error_value}")
            logger.info("✓ 日志级别过滤测试通过")

        except Exception as e:
            logger.error(f"✗ 日志级别过滤测试失败: {e}")
            self.fail(f"日志级别过滤测试失败: {e}")

    def test_5_012_log_with_extra_fields(self):
        """测试5.12: 带额外字段的日志"""
        logger.info("\n[测试5.12] 带额外字段的日志测试")

        try:
            log_manager = get_logger("test_extra_fields", log_level="INFO")

            log_manager.info("Test message", code="SH600000", status="success")

            logger.info("✓ 带额外字段的日志测试通过")

        except Exception as e:
            logger.error(f"✗ 带额外字段的日志测试失败: {e}")
            self.fail(f"带额外字段的日志测试失败: {e}")

    def test_5_013_error_log_type(self):
        """测试5.13: 错误日志类型"""
        logger.info("\n[测试5.13] 错误日志类型测试")

        try:
            error_log_manager = LogManager("test_error", log_level="ERROR", log_type="error")

            self.assertEqual(error_log_manager.log_type, "error")

            retention = LogManager.RETENTION_DAYS.get("error")
            self.assertEqual(retention, 60, "错误日志应该保留60天")

            logger.info(f"  错误日志类型: {error_log_manager.log_type}")
            logger.info(f"  错误日志保留期: {retention}天")
            logger.info("✓ 错误日志类型测试通过")

        except Exception as e:
            logger.error(f"✗ 错误日志类型测试失败: {e}")
            self.fail(f"错误日志类型测试失败: {e}")

    def test_5_014_multiple_loggers(self):
        """测试5.14: 多日志器测试"""
        logger.info("\n[测试5.14] 多日志器测试")

        try:
            loggers = []
            for i in range(5):
                log_mgr = get_logger(f"test_multi_{i}", log_level="INFO")
                loggers.append(log_mgr)

            unique_loggers = set(id(l) for l in loggers)
            self.assertEqual(len(unique_loggers), 5, "应该有5个不同的日志器")

            logger.info(f"  创建日志器数量: {len(loggers)}")
            logger.info("✓ 多日志器测试通过")

        except Exception as e:
            logger.error(f"✗ 多日志器测试失败: {e}")
            self.fail(f"多日志器测试失败: {e}")

    def test_5_015_log_file_rotation(self):
        """测试5.15: 日志文件轮转配置"""
        logger.info("\n[测试5.15] 日志文件轮转配置测试")

        try:
            log_manager = LogManager("test_rotation", log_level="INFO", log_type="normal")

            rotation_configured = False
            for handler in log_manager.logger.handlers:
                if hasattr(handler, "when"):
                    rotation_configured = True
                    logger.info(f"  轮转周期: {handler.when}")
                    logger.info(f"  轮转间隔: {handler.interval}")
                    break

            self.assertTrue(rotation_configured, "日志轮转应该被配置")

            logger.info("✓ 日志文件轮转配置测试通过")

        except Exception as e:
            logger.error(f"✗ 日志文件轮转配置测试失败: {e}")
            self.fail(f"日志文件轮转配置测试失败: {e}")

    def test_5_016_log_consistency(self):
        """测试5.16: 日志一致性测试"""
        logger.info("\n[测试5.16] 日志一致性测试")

        try:
            log_manager = get_logger("test_consistency", log_level="INFO")

            message = "Consistency test message"
            log_manager.info(message)

            log_file = self.log_dir / "test_consistency_normal.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertIn(message, content, "日志消息应该被正确记录")

            logger.info("✓ 日志一致性测试通过")

        except Exception as e:
            logger.error(f"✗ 日志一致性测试失败: {e}")
            self.fail(f"日志一致性测试失败: {e}")

    def test_5_017_unicode_logging(self):
        """测试5.17: Unicode日志支持"""
        logger.info("\n[测试5.17] Unicode日志支持测试")

        try:
            log_manager = get_logger("test_unicode", log_level="INFO")

            unicode_message = "测试Unicode日志支持 🚀 股票代码: SH600000"
            log_manager.info(unicode_message)

            log_file = self.log_dir / "test_unicode_normal.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertIn("测试Unicode", content, "Unicode内容应该被正确记录")

            logger.info("✓ Unicode日志支持测试通过")

        except Exception as e:
            logger.error(f"✗ Unicode日志支持测试失败: {e}")
            self.fail(f"Unicode日志支持测试失败: {e}")

    def test_5_018_long_message_logging(self):
        """测试5.18: 长消息日志测试"""
        logger.info("\n[测试5.18] 长消息日志测试")

        try:
            log_manager = get_logger("test_long", log_level="INFO")

            long_message = "A" * 1000
            log_manager.info(long_message)

            log_file = self.log_dir / "test_long_normal.log"
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.assertIn(long_message[:100], content, "长消息应该被记录")

            logger.info("✓ 长消息日志测试通过")

        except Exception as e:
            logger.error(f"✗ 长消息日志测试失败: {e}")
            self.fail(f"长消息日志测试失败: {e}")

    def test_5_019_special_characters_logging(self):
        """测试5.19: 特殊字符日志测试"""
        logger.info("\n[测试5.19] 特殊字符日志测试")

        try:
            log_manager = get_logger("test_special", log_level="INFO")

            special_message = 'Special chars: "quotes" \\backslash\\ <brackets> &ampersand& |pipe|'
            log_manager.info(special_message)

            logger.info("✓ 特殊字符日志测试通过")

        except Exception as e:
            logger.error(f"✗ 特殊字符日志测试失败: {e}")
            self.fail(f"特殊字符日志测试失败: {e}")

    def test_5_020_log_directory_permissions(self):
        """测试5.20: 日志目录权限验证"""
        logger.info("\n[测试5.20] 日志目录权限验证测试")

        try:
            log_dir = LogManager._log_dir

            self.assertTrue(os.access(log_dir, os.W_OK), "日志目录应该有写入权限")
            self.assertTrue(os.access(log_dir, os.R_OK), "日志目录应该有读取权限")

            logger.info(f"  日志目录: {log_dir}")
            logger.info(f"  可写: {os.access(log_dir, os.W_OK)}")
            logger.info(f"  可读: {os.access(log_dir, os.R_OK)}")
            logger.info("✓ 日志目录权限验证测试通过")

        except Exception as e:
            logger.error(f"✗ 日志目录权限验证测试失败: {e}")
            self.fail(f"日志目录权限验证测试失败: {e}")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M5日志模块测试完成")
        logger.info("=" * 80)


def run_m5_tests():
    """运行M5模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM5日志模块)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m5_tests()
    sys.exit(0 if success else 1)
