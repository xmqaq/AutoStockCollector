"""
M3数据校验模块测试 - 校验逻辑与异常处理
包含时序校验、完整性校验、合法性校验、异常数据容错处理能力测试
"""
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.validator.validator import DataValidator, DataIntegrityChecker, ValidationResult
from core.storage.mongo_storage import KlineStorage, StockInfoStorage
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM3数据校验(unittest.TestCase):
    """M3数据校验模块 - 校验逻辑与异常处理"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 连接MongoDB"""
        logger.info("=" * 80)
        logger.info("M3数据校验模块测试开始 - 校验逻辑与异常处理")
        logger.info("=" * 80)

        import os
        from pathlib import Path
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())

        try:
            DatabaseConfig.connect()
            logger.info("✓ MongoDB连接成功")
        except Exception as e:
            logger.error(f"✗ MongoDB连接失败: {e}")
            raise

        cls.validator = DataValidator()
        cls.kline_storage = KlineStorage()
        cls.stock_info_storage = StockInfoStorage()

    def test_3_001_validator_initialization(self):
        """测试3.1: 数据校验器初始化"""
        logger.info("\n[测试3.1] 数据校验器初始化测试")

        try:
            validator = DataValidator()

            self.assertIsNotNone(validator.kline_storage)
            self.assertIsNotNone(validator.stock_info_storage)
            self.assertIsNotNone(validator.financial_storage)
            self.assertIsNotNone(validator.news_storage)
            self.assertIsNotNone(validator.fund_flow_storage)

            logger.info("✓ 数据校验器初始化成功")

        except Exception as e:
            logger.error(f"✗ 数据校验器初始化失败: {e}")
            self.fail(f"数据校验器初始化失败: {e}")

    def test_3_002_validation_result_class(self):
        """测试3.2: 校验结果类功能验证"""
        logger.info("\n[测试3.2] 校验结果类功能测试")

        try:
            result = ValidationResult(code="SH600000", data_type="kline")

            self.assertEqual(result.code, "SH600000")
            self.assertEqual(result.data_type, "kline")
            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(len(result.warnings), 0)
            self.assertEqual(result.completeness_score, 100.0)

            result.add_error("Test error")
            self.assertFalse(result.is_valid)
            self.assertEqual(len(result.errors), 1)
            self.assertEqual(result.errors[0], "Test error")

            result.add_warning("Test warning")
            self.assertEqual(len(result.warnings), 1)
            self.assertEqual(result.warnings[0], "Test warning")

            result.set_completeness(85.5)
            self.assertEqual(result.completeness_score, 85.5)

            result_dict = result.to_dict()
            self.assertEqual(result_dict["code"], "SH600000")
            self.assertEqual(result_dict["data_type"], "kline")
            self.assertFalse(result_dict["is_valid"])
            self.assertEqual(len(result_dict["errors"]), 1)
            self.assertEqual(len(result_dict["warnings"]), 1)

            logger.info(f"  校验结果: {result_dict}")
            logger.info("✓ 校验结果类功能验证通过")

        except Exception as e:
            logger.error(f"✗ 校验结果类功能验证失败: {e}")
            self.fail(f"校验结果类功能验证失败: {e}")

    def test_3_003_kline_data_validation(self):
        """测试3.3: K线数据校验"""
        logger.info("\n[测试3.3] K线数据校验测试")

        try:
            result = self.validator.validate_kline_data("SH600000")

            self.assertIsNotNone(result)
            self.assertEqual(result.code, "SH600000")
            self.assertEqual(result.data_type, "kline")

            logger.info(f"  校验结果: is_valid={result.is_valid}")
            logger.info(f"  错误数: {len(result.errors)}")
            logger.info(f"  警告数: {len(result.warnings)}")
            logger.info(f"  完整度: {result.completeness_score}%")
            logger.info("✓ K线数据校验测试通过")

        except Exception as e:
            logger.error(f"✗ K线数据校验测试失败: {e}")
            self.fail(f"K线数据校验测试失败: {e}")

    def test_3_004_stock_info_validation(self):
        """测试3.4: 股票信息校验"""
        logger.info("\n[测试3.4] 股票信息校验测试")

        try:
            result = self.validator.validate_stock_info("SH600000")

            self.assertIsNotNone(result)
            self.assertEqual(result.code, "SH600000")
            self.assertEqual(result.data_type, "stock_info")

            logger.info(f"  校验结果: is_valid={result.is_valid}")
            logger.info(f"  完整度: {result.completeness_score}%")
            logger.info("✓ 股票信息校验测试通过")

        except Exception as e:
            logger.error(f"✗ 股票信息校验测试失败: {e}")
            self.fail(f"股票信息校验测试失败: {e}")

    def test_3_005_batch_validation(self):
        """测试3.5: 批量校验功能"""
        logger.info("\n[测试3.5] 批量校验功能测试")

        try:
            codes = ["SH600000", "SH600036", "SZ000001"]

            results = self.validator.validate_batch(codes, data_type="kline")

            self.assertEqual(len(results), 3)

            for i, result in enumerate(results):
                self.assertEqual(result.code, codes[i])
                self.assertEqual(result.data_type, "kline")

            logger.info(f"  批量校验: {len(results)} 个标的")
            for result in results:
                logger.info(f"    {result.code}: is_valid={result.is_valid}")
            logger.info("✓ 批量校验功能测试通过")

        except Exception as e:
            logger.error(f"✗ 批量校验功能测试失败: {e}")
            self.fail(f"批量校验功能测试失败: {e}")

    def test_3_006_data_gaps_check(self):
        """测试3.6: 数据间隙检测"""
        logger.info("\n[测试3.6] 数据间隙检测测试")

        try:
            gaps = self.validator.check_data_gaps(
                code="SH600000",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            self.assertIsInstance(gaps, list)
            logger.info(f"  缺失日期数量: {len(gaps)}")
            if gaps:
                logger.info(f"  缺失日期示例: {gaps[:5]}")

            logger.info("✓ 数据间隙检测测试通过")

        except Exception as e:
            logger.error(f"✗ 数据间隙检测测试失败: {e}")
            self.fail(f"数据间隙检测测试失败: {e}")

    def test_3_007_completeness_score(self):
        """测试3.7: 数据完整度评分"""
        logger.info("\n[测试3.7] 数据完整度评分测试")

        try:
            score = self.validator.get_data_completeness_score(
                code="SH600000",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            self.assertIsInstance(score, float)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)

            logger.info(f"  完整度评分: {score:.2f}%")
            logger.info("✓ 数据完整度评分测试通过")

        except Exception as e:
            logger.error(f"✗ 数据完整度评分测试失败: {e}")
            self.fail(f"数据完整度评分测试失败: {e}")

    def test_3_008_validation_report_generation(self):
        """测试3.8: 校验报告生成"""
        logger.info("\n[测试3.8] 校验报告生成测试")

        try:
            report = self.validator.generate_validation_report(
                codes=["SH600000", "SH600036"],
                data_type="kline"
            )

            self.assertIn("total_codes", report)
            self.assertIn("valid_count", report)
            self.assertIn("invalid_count", report)
            self.assertIn("avg_completeness", report)
            self.assertIn("error_summary", report)
            self.assertIn("results", report)

            logger.info(f"  报告统计:")
            logger.info(f"    总标的数: {report['total_codes']}")
            logger.info(f"    有效数: {report['valid_count']}")
            logger.info(f"    无效数: {report['invalid_count']}")
            logger.info(f"    平均完整度: {report['avg_completeness']}%")
            logger.info(f"    错误汇总: {report['error_summary']}")
            logger.info("✓ 校验报告生成测试通过")

        except Exception as e:
            logger.error(f"✗ 校验报告生成测试失败: {e}")
            self.fail(f"校验报告生成测试失败: {e}")

    def test_3_009_price_sequence_check(self):
        """测试3.9: 价格序列校验"""
        logger.info("\n[测试3.9] 价格序列校验测试")

        try:
            klines = [
                {"date": "2024-01-01", "high": 10.5, "low": 10.0, "close": 10.2},
                {"date": "2024-01-02", "high": 10.8, "low": 10.3, "close": 10.6},
                {"date": "2024-01-03", "high": 11.0, "low": 10.5, "close": 10.8},
            ]

            errors = DataIntegrityChecker.check_price_sequence(klines)

            self.assertIsInstance(errors, list)
            self.assertEqual(len(errors), 0)

            invalid_klines = [
                {"date": "2024-01-01", "high": 10.0, "low": 10.5, "close": 10.2},
            ]

            errors = DataIntegrityChecker.check_price_sequence(invalid_klines)
            self.assertGreater(len(errors), 0)

            logger.info(f"  有效K线错误数: {len(errors)}")
            logger.info(f"  无效K线错误数: {len(errors)}")
            logger.info("✓ 价格序列校验测试通过")

        except Exception as e:
            logger.error(f"✗ 价格序列校验测试失败: {e}")
            self.fail(f"价格序列校验测试失败: {e}")

    def test_3_010_volume_anomaly_check(self):
        """测试3.10: 成交量异常检测"""
        logger.info("\n[测试3.10] 成交量异常检测测试")

        try:
            klines = [
                {"date": "2024-01-01", "volume": 1000000},
                {"date": "2024-01-02", "volume": 1100000},
                {"date": "2024-01-03", "volume": 1050000},
                {"date": "2024-01-04", "volume": 1200000},
            ]

            errors = DataIntegrityChecker.check_volume_anomaly(klines, threshold=5.0)

            self.assertIsInstance(errors, list)

            abnormal_klines = [
                {"date": "2024-01-01", "volume": 1000000},
                {"date": "2024-01-02", "volume": 1000000},
                {"date": "2024-01-03", "volume": 1000000},
                {"date": "2024-01-04", "volume": 1000000},
                {"date": "2024-01-05", "volume": 100000000},
            ]

            errors = DataIntegrityChecker.check_volume_anomaly(abnormal_klines, threshold=2.0)
            self.assertGreater(len(errors), 0)

            logger.info(f"  正常数据异常数: {len(errors)}")
            logger.info(f"  异常数据检测数: {len(errors)}")
            logger.info("✓ 成交量异常检测测试通过")

        except Exception as e:
            logger.error(f"✗ 成交量异常检测测试失败: {e}")
            self.fail(f"成交量异常检测测试失败: {e}")

    def test_3_011_price_jump_check(self):
        """测试3.11: 价格跳空检测"""
        logger.info("\n[测试3.11] 价格跳空检测测试")

        try:
            klines = [
                {"date": "2024-01-01", "close": 10.0},
                {"date": "2024-01-02", "close": 10.2},
                {"date": "2024-01-03", "close": 10.5},
            ]

            errors = DataIntegrityChecker.check_price_jump(klines, threshold=20.0)

            self.assertIsInstance(errors, list)
            self.assertEqual(len(errors), 0)

            jump_klines = [
                {"date": "2024-01-01", "close": 10.0},
                {"date": "2024-01-02", "close": 25.0},
            ]

            errors = DataIntegrityChecker.check_price_jump(jump_klines, threshold=20.0)
            self.assertGreater(len(errors), 0)

            logger.info(f"  正常数据跳空数: {len(errors)}")
            logger.info(f"  跳空数据检测数: {len(errors)}")
            logger.info("✓ 价格跳空检测测试通过")

        except Exception as e:
            logger.error(f"✗ 价格跳空检测测试失败: {e}")
            self.fail(f"价格跳空检测测试失败: {e}")

    def test_3_012_fix_common_issues(self):
        """测试3.12: 常见问题修复"""
        logger.info("\n[测试3.12] 常见问题修复测试")

        try:
            self.validator.fix_common_issues("SH600000", data_type="kline")

            logger.info("✓ 常见问题修复测试通过")

        except Exception as e:
            logger.error(f"✗ 常见问题修复测试失败: {e}")
            self.fail(f"常见问题修复测试失败: {e}")

    def test_3_013_fund_flow_validation(self):
        """测试3.13: 资金流向数据校验"""
        logger.info("\n[测试3.13] 资金流向数据校验测试")

        try:
            result = self.validator.validate_fund_flow("SH600000")

            self.assertIsNotNone(result)
            self.assertEqual(result.code, "SH600000")
            self.assertEqual(result.data_type, "fund_flow")

            logger.info(f"  校验结果: is_valid={result.is_valid}")
            logger.info(f"  完整度: {result.completeness_score}%")
            logger.info("✓ 资金流向数据校验测试通过")

        except Exception as e:
            logger.error(f"✗ 资金流向数据校验测试失败: {e}")
            self.fail(f"资金流向数据校验测试失败: {e}")

    def test_3_014_news_validation(self):
        """测试3.14: 新闻数据校验"""
        logger.info("\n[测试3.14] 新闻数据校验测试")

        try:
            result = self.validator.validate_news_data()

            self.assertIsNotNone(result)
            self.assertEqual(result.data_type, "news")

            logger.info(f"  校验结果: is_valid={result.is_valid}")
            logger.info(f"  完整度: {result.completeness_score}%")
            logger.info("✓ 新闻数据校验测试通过")

        except Exception as e:
            logger.error(f"✗ 新闻数据校验测试失败: {e}")
            self.fail(f"新闻数据校验测试失败: {e}")

    def test_3_015_financial_validation(self):
        """测试3.15: 财务数据校验"""
        logger.info("\n[测试3.15] 财务数据校验测试")

        try:
            result = self.validator.validate_financial_data("SH600000")

            self.assertIsNotNone(result)
            self.assertEqual(result.code, "SH600000")
            self.assertEqual(result.data_type, "financial")

            logger.info(f"  校验结果: is_valid={result.is_valid}")
            logger.info(f"  完整度: {result.completeness_score}%")
            logger.info("✓ 财务数据校验测试通过")

        except Exception as e:
            logger.error(f"✗ 财务数据校验测试失败: {e}")
            self.fail(f"财务数据校验测试失败: {e}")

    def test_3_016_trading_calendar_loading(self):
        """测试3.16: 交易日历加载"""
        logger.info("\n[测试3.16] 交易日历加载测试")

        try:
            self.validator.load_trading_calendar("2024-01-01", "2024-01-31")

            calendar = self.validator.trading_calendar

            self.assertIsNotNone(calendar)
            self.assertIsInstance(calendar, list)
            self.assertGreater(len(calendar), 0)

            logger.info(f"  交易日数量: {len(calendar)}")
            if calendar:
                logger.info(f"  首个交易日: {calendar[0]}")
                logger.info(f"  最后交易日: {calendar[-1]}")

            logger.info("✓ 交易日历加载测试通过")

        except Exception as e:
            logger.error(f"✗ 交易日历加载测试失败: {e}")
            self.fail(f"交易日历加载测试失败: {e}")

    def test_3_017_completeness_score_bounds(self):
        """测试3.17: 完整度评分边界验证"""
        logger.info("\n[测试3.17] 完整度评分边界验证测试")

        try:
            result = ValidationResult("TEST", "test")

            result.set_completeness(150.0)
            self.assertEqual(result.completeness_score, 100.0)

            result.set_completeness(-10.0)
            self.assertEqual(result.completeness_score, 0.0)

            result.set_completeness(50.0)
            self.assertEqual(result.completeness_score, 50.0)

            logger.info("✓ 完整度评分边界验证通过")

        except Exception as e:
            logger.error(f"✗ 完整度评分边界验证失败: {e}")
            self.fail(f"完整度评分边界验证失败: {e}")

    def test_3_018_validation_result_multiple_errors(self):
        """测试3.18: 多错误累积验证"""
        logger.info("\n[测试3.18] 多错误累积验证测试")

        try:
            result = ValidationResult("TEST", "test")

            for i in range(5):
                result.add_error(f"Error {i}")

            self.assertEqual(len(result.errors), 5)
            self.assertFalse(result.is_valid)

            for i in range(3):
                result.add_warning(f"Warning {i}")

            self.assertEqual(len(result.warnings), 3)

            logger.info(f"  错误数量: {len(result.errors)}")
            logger.info(f"  警告数量: {len(result.warnings)}")
            logger.info("✓ 多错误累积验证通过")

        except Exception as e:
            logger.error(f"✗ 多错误累积验证失败: {e}")
            self.fail(f"多错误累积验证失败: {e}")

    def test_3_019_kline_record_field_validation(self):
        """测试3.19: K线记录字段校验"""
        logger.info("\n[测试3.19] K线记录字段校验测试")

        try:
            validator = DataValidator()

            valid_record = {
                "code": "SH600000",
                "date": "2024-01-01",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000
            }

            result = ValidationResult("SH600000", "kline")
            validator._validate_kline_record(valid_record, result)

            self.assertTrue(result.is_valid)

            invalid_record = {
                "code": "SH600000",
                "date": "2024-01-01",
                "high": 10.0,
                "low": 10.5,
                "close": -10.0,
                "volume": -100
            }

            result2 = ValidationResult("SH600000", "kline")
            validator._validate_kline_record(invalid_record, result2)

            self.assertFalse(result2.is_valid)
            self.assertGreater(len(result2.errors), 0)

            logger.info(f"  有效记录错误数: {len(result.errors)}")
            logger.info(f"  无效记录错误数: {len(result2.errors)}")
            logger.info("✓ K线记录字段校验测试通过")

        except Exception as e:
            logger.error(f"✗ K线记录字段校验测试失败: {e}")
            self.fail(f"K线记录字段校验测试失败: {e}")

    def test_3_020_empty_data_validation(self):
        """测试3.20: 空数据校验容错处理"""
        logger.info("\n[测试3.20] 空数据校验容错处理测试")

        try:
            result = self.validator.validate_kline_data("NONEXISTENT")

            self.assertFalse(result.is_valid)
            self.assertGreater(len(result.errors), 0)
            self.assertEqual(result.completeness_score, 0.0)

            logger.info(f"  空数据校验结果: is_valid={result.is_valid}")
            logger.info(f"  错误信息: {result.errors}")
            logger.info("✓ 空数据校验容错处理测试通过")

        except Exception as e:
            logger.error(f"✗ 空数据校验容错处理测试失败: {e}")
            self.fail(f"空数据校验容错处理测试失败: {e}")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M3数据校验模块测试完成")
        logger.info("=" * 80)


def run_m3_tests():
    """运行M3模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM3数据校验)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m3_tests()
    sys.exit(0 if success else 1)
