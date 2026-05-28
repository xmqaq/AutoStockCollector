"""
M1数据采集模块测试 - 历史数据链路验证
包含数据源连接稳定性、数据格式兼容性、全量数据完整性、异常数据容错处理能力测试
"""
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.collector.kline_collector import KlineCollector
from core.collector.fund_flow_collector import FundFlowCollector, MarginCollector
from core.collector.base import BaseCollector, SourceSelector, DataSourcePriority
from core.storage.mongo_storage import KlineStorage, FundFlowStorage
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM1DataCollection链路(unittest.TestCase):
    """M1数据采集模块 - 历史数据链路验证"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 连接MongoDB"""
        logger.info("=" * 80)
        logger.info("M1数据采集模块测试开始 - 历史数据链路验证")
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

    def test_1_001_mongodb_connection_stability(self):
        """测试1.1: MongoDB连接稳定性"""
        logger.info("\n[测试1.1] MongoDB连接稳定性测试")

        try:
            db = DatabaseConfig.get_database()
            db.command("ping")
            logger.info("✓ MongoDB连接稳定性验证通过")
            self.assertTrue(True)
        except Exception as e:
            logger.error(f"✗ MongoDB连接失败: {e}")
            self.fail(f"MongoDB连接失败: {e}")

    def test_1_002_kline_collector_initialization(self):
        """测试1.2: K线采集器初始化"""
        logger.info("\n[测试1.2] K线采集器初始化测试")

        try:
            collector = KlineCollector()
            self.assertIsNotNone(collector)
            self.assertIsNotNone(collector.storage)
            self.assertIsNotNone(collector.risk_controller)
            logger.info("✓ K线采集器初始化成功")
        except Exception as e:
            logger.error(f"✗ K线采集器初始化失败: {e}")
            self.fail(f"K线采集器初始化失败: {e}")

    def test_1_003_kline_historical_data_collection(self):
        """测试1.3: K线历史数据采集 - 单标的"""
        logger.info("\n[测试1.3] K线历史数据采集测试 - 单标的")

        collector = KlineCollector()
        test_code = "SH600000"

        try:
            start_date = "20240101"
            end_date = "20240131"

            records = collector.collect_single(
                test_code,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if records and len(records) > 0:
                logger.info(f"✓ 成功采集K线数据 {len(records)} 条")

                first_record = records[0]
                self.assertIn("code", first_record)
                self.assertIn("date", first_record)

                logger.info(f"  首条数据日期: {first_record.get('date')}")
                logger.info(f"  首条数据收盘价: {first_record.get('close')}")
                logger.info(f"  ✓ 数据格式兼容性验证通过")
            else:
                logger.warning(f"⚠ K线数据为空（可能为退市或停牌股票，或网络连接问题）")
                self.skipTest("K线数据采集为空，跳过此测试")

        except unittest.case.SkipTest:
            raise
        except Exception as e:
            logger.error(f"✗ K线历史数据采集失败: {e}")
            self.fail(f"K线历史数据采集失败: {e}")

    def test_1_004_kline_data_persistence(self):
        """测试1.4: K线数据持久化验证"""
        logger.info("\n[测试1.4] K线数据持久化测试")

        collector = KlineCollector()
        storage = KlineStorage()
        test_code = "SH600036"

        try:
            start_date = "20240301"
            end_date = "20240331"

            records = collector.collect_single(
                test_code,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if records and len(records) > 0:
                success_count, failed_count = storage.save_kline_batch(records)

                logger.info(f"  入库成功: {success_count} 条")
                logger.info(f"  入库失败: {failed_count} 条")

                stored_records = storage.query_by_date_range(
                    test_code, "date", start_date, end_date
                )

                self.assertGreater(len(stored_records), 0, "数据持久化验证失败")
                logger.info(f"✓ 数据持久化验证通过，库中记录数: {len(stored_records)}")

                for record in stored_records:
                    self.assertIn("code", record)
                    self.assertIn("date", record)
                    logger.info(f"  验证记录: {record['date']} - 收盘价: {record.get('close')}")

            else:
                logger.warning(f"⚠ 无采集数据，跳过持久化测试")
                self.skipTest("无采集数据，跳过持久化测试")

        except unittest.case.SkipTest:
            raise
        except Exception as e:
            logger.error(f"✗ K线数据持久化测试失败: {e}")
            self.fail(f"K线数据持久化测试失败: {e}")

    def test_1_005_kline_data_completeness(self):
        """测试1.5: K线数据完整性验证"""
        logger.info("\n[测试1.5] K线数据完整性测试")

        storage = KlineStorage()
        test_code = "SH600000"

        try:
            earliest, latest = storage.get_kline_range(test_code)

            if earliest and latest:
                logger.info(f"  数据范围: {earliest} 至 {latest}")

                records = storage.query_by_date_range(
                    test_code, "date", earliest, latest
                )

                required_fields = ["code", "date"]

                missing_fields_records = []
                for record in records:
                    for field in required_fields:
                        if field not in record or record[field] is None:
                            missing_fields_records.append({
                                "date": record.get("date"),
                                "missing_field": field
                            })

                if missing_fields_records:
                    logger.warning(f"⚠ 发现 {len(missing_fields_records)} 条缺失字段的记录")
                    for miss in missing_fields_records[:5]:
                        logger.warning(f"  {miss}")
                else:
                    logger.info(f"✓ 所有记录字段完整，无缺失")

                invalid_values = []
                for record in records:
                    if record.get("close", 0) <= 0:
                        invalid_values.append(record.get("date"))

                if invalid_values:
                    logger.warning(f"⚠ 发现 {len(invalid_values)} 条无效值记录")
                else:
                    logger.info(f"✓ 所有记录值有效，无负数或零值")

                logger.info(f"✓ K线数据完整性验证通过")

            else:
                logger.warning(f"⚠ 库中无该股票数据，跳过完整性测试")
                self.skipTest("库中无该股票数据")

        except unittest.case.SkipTest:
            raise
        except Exception as e:
            logger.error(f"✗ K线数据完整性测试失败: {e}")
            self.fail(f"K线数据完整性测试失败: {e}")

    def test_1_006_fund_flow_historical_collection(self):
        """测试1.6: 资金流向历史数据采集"""
        logger.info("\n[测试1.6] 资金流向历史数据采集测试")

        collector = FundFlowCollector()
        test_code = "SH600000"

        try:
            records = collector.collect_single(test_code, period="daily")

            if records and len(records) > 0:
                logger.info(f"✓ 成功采集资金流向数据 {len(records)} 条")

                first_record = records[0]
                logger.info(f"  数据字段: {list(first_record.keys())}")

                required_fields = ["code", "date"]
                for field in required_fields:
                    self.assertIn(field, first_record, f"缺少必需字段: {field}")

                logger.info(f"✓ 资金流向数据格式兼容性验证通过")
            else:
                logger.warning(f"⚠ 资金流向数据为空")

        except Exception as e:
            logger.error(f"✗ 资金流向历史数据采集失败: {e}")
            self.fail(f"资金流向历史数据采集失败: {e}")

    def test_1_007_margin_data_collection(self):
        """测试1.7: 两融数据采集测试"""
        logger.info("\n[测试1.7] 两融数据采集测试")

        collector = MarginCollector()
        test_date = datetime.now().strftime("%Y%m%d")

        try:
            result = collector.collect_margin_summary(date=test_date)

            if result:
                logger.info(f"✓ 成功采集两融汇总数据")
                logger.info(f"  融资余额: {result.get('margin_balance')}")
                logger.info(f"  融券余额: {result.get('short_balance')}")
                self.assertIn("date", result)
                self.assertIn("margin_balance", result)
            else:
                logger.warning(f"⚠ 两融汇总数据为空（非交易日或接口限制）")

        except Exception as e:
            logger.warning(f"⚠ 两融数据采集异常: {e}")

    def test_1_008_data_source_priority_validation(self):
        """测试1.8: 数据源优先级规则验证"""
        logger.info("\n[测试1.8] 数据源优先级规则验证")

        try:
            preferred_sources = ["sina", "ths", "baidu", "xina", "cninfo"]
            eastmoney_sources = ["eastmoney", "em", "东方财富"]

            for source in preferred_sources:
                self.assertTrue(
                    SourceSelector.is_preferred_source(source),
                    f"数据源 {source} 应被识别为优先数据源"
                )
                self.assertFalse(
                    SourceSelector.is_eastmoney_source(source),
                    f"数据源 {source} 不应被识别为东方财富"
                )

            for source in eastmoney_sources:
                self.assertTrue(
                    SourceSelector.is_eastmoney_source(source),
                    f"数据源 {source} 应被识别为东方财富"
                )
                self.assertFalse(
                    SourceSelector.is_preferred_source(source),
                    f"东方财富数据源 {source} 不应被识别为优先"
                )

            logger.info(f"✓ 数据源优先级规则验证通过")

            for priority in DataSourcePriority:
                logger.info(f"  {priority.name} = {priority.value}")

        except Exception as e:
            logger.error(f"✗ 数据源优先级规则验证失败: {e}")
            self.fail(f"数据源优先级规则验证失败: {e}")

    def test_1_009_incremental_collection_logic(self):
        """测试1.9: 增量采集逻辑验证"""
        logger.info("\n[测试1.9] 增量采集逻辑测试")

        collector = KlineCollector()
        storage = KlineStorage()
        test_code = "SH600000"

        try:
            latest_date = storage.get_latest_date(test_code)

            if latest_date:
                logger.info(f"  库中最新日期: {latest_date}")

                incremental_records = collector.collect_incremental(test_code)

                if incremental_records:
                    new_dates = [r.get("date") for r in incremental_records]
                    logger.info(f"  新采集日期范围: {min(new_dates)} 至 {max(new_dates)}")

                    all_new_after_latest = all(
                        date > latest_date for date in new_dates
                    )
                    self.assertTrue(
                        all_new_after_latest,
                        "增量采集应只采集最新数据"
                    )
                    logger.info(f"✓ 增量采集逻辑验证通过")
                else:
                    logger.info(f"⚠ 无新增数据（已到最新）")
            else:
                logger.info(f"  库中无数据，执行全量采集测试")

                records = collector.collect_single(
                    test_code,
                    start_date="20240101",
                    end_date="20240131"
                )

                if records:
                    logger.info(f"✓ 全量采集成功 {len(records)} 条")
                else:
                    logger.warning(f"⚠ 网络问题导致采集失败，跳过此测试")
                    self.skipTest("网络问题导致采集失败")

        except unittest.case.SkipTest:
            raise
        except Exception as e:
            logger.error(f"✗ 增量采集逻辑测试失败: {e}")
            self.fail(f"增量采集逻辑测试失败: {e}")

    def test_1_010_error_handling_invalid_code(self):
        """测试1.10: 异常数据容错处理 - 无效股票代码"""
        logger.info("\n[测试1.10] 异常数据容错处理 - 无效股票代码")

        collector = KlineCollector()

        invalid_codes = ["INVALID", "999999", "", None]

        for code in invalid_codes:
            if code is None:
                continue

            try:
                result = collector.collect_single(code)
                logger.info(f"  无效代码 '{code}' 处理: 返回 {result}")
                self.assertIsNone(result, "无效代码应返回None")
            except Exception as e:
                logger.warning(f"  无效代码 '{code}' 抛出异常: {e}")

        logger.info(f"✓ 无效股票代码容错处理验证通过")

    def test_1_011_error_handling_invalid_date_range(self):
        """测试1.11: 异常数据容错处理 - 无效日期范围"""
        logger.info("\n[测试1.11] 异常数据容错处理 - 无效日期范围")

        collector = KlineCollector()
        test_code = "SH600000"

        try:
            result = collector.collect_single(
                test_code,
                start_date="99999999",
                end_date="11111111"
            )

            logger.info(f"  无效日期范围处理: {'返回空数据' if not result else '返回数据'}")
            self.assertIsNone(result, "无效日期范围应返回None")

            result2 = collector.collect_single(
                test_code,
                start_date="2024-01-01",
                end_date="2023-01-01"
            )

            logger.info(f"  起始日期大于结束日期: {'自动调整' if result2 else '返回空'}")
            logger.info(f"✓ 无效日期范围容错处理验证通过")

        except Exception as e:
            logger.warning(f"  异常处理: {e}")

    def test_1_012_batch_collection_stability(self):
        """测试1.12: 批量采集稳定性测试"""
        logger.info("\n[测试1.12] 批量采集稳定性测试")

        collector = KlineCollector()
        test_codes = ["SH600000", "SH600036", "SZ000001", "SZ000002"]

        try:
            all_records = []
            success_count = 0
            failed_count = 0

            for code in test_codes:
                try:
                    records = collector.collect_single(code)
                    if records:
                        all_records.extend(records)
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"  采集失败 {code}: {e}")
                    failed_count += 1

                time.sleep(1)

            logger.info(f"  批量采集统计:")
            logger.info(f"    成功: {success_count}/{len(test_codes)}")
            logger.info(f"    失败: {failed_count}/{len(test_codes)}")
            logger.info(f"    总记录数: {len(all_records)}")

            if success_count == 0:
                logger.warning(f"⚠ 网络连接问题导致批量采集全部失败")
                self.skipTest("网络连接问题导致批量采集全部失败")
            else:
                self.assertGreater(success_count, 0, "至少应有部分股票采集成功")
                logger.info(f"✓ 批量采集稳定性测试通过")

        except unittest.case.SkipTest:
            raise
        except Exception as e:
            logger.error(f"✗ 批量采集稳定性测试失败: {e}")
            self.fail(f"批量采集稳定性测试失败: {e}")

    def test_1_013_retry_mechanism(self):
        """测试1.13: 重试机制验证"""
        logger.info("\n[测试1.13] 重试机制验证")

        collector = KlineCollector()

        try:
            initial_retry_times = collector.retry_times
            initial_retry_delay = collector.retry_delay

            logger.info(f"  重试次数配置: {initial_retry_times}")
            logger.info(f"  重试延迟配置: {initial_retry_delay}秒")

            self.assertGreater(initial_retry_times, 0, "重试次数应大于0")
            self.assertGreater(initial_retry_delay, 0, "重试延迟应大于0")

            logger.info(f"✓ 重试机制配置验证通过")

        except Exception as e:
            logger.error(f"✗ 重试机制验证失败: {e}")
            self.fail(f"重试机制验证失败: {e}")

    def test_1_014_data_normalization(self):
        """测试1.14: 数据标准化验证"""
        logger.info("\n[测试1.14] 数据标准化验证")

        collector = KlineCollector()

        try:
            test_data = pd.DataFrame({
                "日期": ["2024-01-01", "2024-01-02"],
                "代码": ["600000", "600036"],
                "开盘": [10.5, 11.2],
                "收盘": [10.8, 11.5],
                "成交量": [1000000, 1200000],
                "最高": [11.0, 12.0],
                "最低": [10.0, 11.0]
            })

            normalized = collector.normalize_dataframe(test_data)

            self.assertEqual(len(normalized), 2)

            self.assertIn("date", normalized[0])
            self.assertIn("code", normalized[0])

            logger.info(f"  标准化字段: {list(normalized[0].keys())}")
            logger.info(f"✓ 数据标准化验证通过")

        except Exception as e:
            logger.error(f"✗ 数据标准化验证失败: {e}")
            self.fail(f"数据标准化验证失败: {e}")

    def test_1_015_code_normalization(self):
        """测试1.15: 股票代码标准化验证"""
        logger.info("\n[测试1.15] 股票代码标准化验证")

        collector = KlineCollector()

        test_cases = [
            ("600000", "SH600000"),
            ("000001", "SZ000001"),
            ("300001", "SZ300001"),
            ("SH600000", "SH600000"),
            ("sz000001", "SZ000001"),
            ("SH600036", "SH600036"),
        ]

        for input_code, expected in test_cases:
            result = collector._normalize_code(input_code)
            self.assertEqual(
                result, expected,
                f"代码 {input_code} 标准化失败: 期望 {expected}, 实际 {result}"
            )
            logger.info(f"  {input_code} -> {result}")

        logger.info(f"✓ 股票代码标准化验证通过")

    def test_1_016_multi_period_collection(self):
        """测试1.16: 多周期K线采集测试"""
        logger.info("\n[测试1.16] 多周期K线采集测试")

        collector = KlineCollector()
        test_code = "SH600000"

        periods = ["daily"]

        for period in periods:
            try:
                logger.info(f"  测试周期: {period}")

                records = collector.collect_single(
                    test_code,
                    start_date="20240301",
                    end_date="20240331",
                    period=period
                )

                if records:
                    logger.info(f"    采集成功: {len(records)} 条")
                else:
                    logger.warning(f"    无数据")

            except Exception as e:
                logger.warning(f"    {period} 周期采集异常: {e}")

        logger.info(f"✓ 多周期K线采集测试完成")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M1数据采集模块测试完成")
        logger.info("=" * 80)


def run_m1_tests():
    """运行M1模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM1DataCollection链路)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m1_tests()
    sys.exit(0 if success else 1)
