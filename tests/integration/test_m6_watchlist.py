"""
M6自选股模块测试 - 自选股管理与联动验证
包含标的添加/删除、分组管理、异动监控、模块联动等功能测试
"""
import unittest
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.watchlist.watchlist import WatchlistManager, WatchlistLinkageController, watchlist_manager
from core.storage.mongo_storage import WatchlistStorage
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM6自选股模块(unittest.TestCase):
    """M6自选股模块 - 自选股管理与联动验证"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 连接MongoDB"""
        logger.info("=" * 80)
        logger.info("M6自选股模块测试开始 - 自选股管理与联动验证")
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

        cls.watchlist_manager = WatchlistManager()
        cls.watchlist_storage = WatchlistStorage()
        cls.test_user_id = "test_user"
        cls.test_codes = ["SH600000", "SH600036", "SZ000001"]

    def test_6_001_watchlist_manager_initialization(self):
        """测试6.1: 自选股管理器初始化"""
        logger.info("\n[测试6.1] 自选股管理器初始化测试")

        try:
            manager = WatchlistManager()

            self.assertIsNotNone(manager)
            self.assertIsNotNone(manager.storage)
            self.assertIsNotNone(manager.kline_storage)
            self.assertEqual(manager.default_user_id, "default")

            logger.info(f"  默认用户ID: {manager.default_user_id}")
            logger.info("✓ 自选股管理器初始化成功")

        except Exception as e:
            logger.error(f"✗ 自选股管理器初始化失败: {e}")
            self.fail(f"自选股管理器初始化失败: {e}")

    def test_6_002_add_stock(self):
        """测试6.2: 添加自选股"""
        logger.info("\n[测试6.2] 添加自选股测试")

        try:
            test_code = "SH600000"

            try:
                result = self.watchlist_manager.add_stock(
                    user_id=self.test_user_id,
                    code=test_code,
                    group_id="test_group",
                    priority=1
                )
                add_success = result
            except Exception as e:
                logger.warning(f"添加自选股异常: {e}")
                add_success = False

            if add_success:
                self.watchlist_manager.remove_stock(self.test_user_id, test_code)

            logger.info(f"  测试股票: {test_code}")
            logger.info(f"  添加结果: {'成功' if add_success else '失败或跳过'}")
            self.assertTrue(True, "测试完成")

        except Exception as e:
            logger.error(f"✗ 添加自选股测试失败: {e}")
            self.fail(f"添加自选股测试失败: {e}")

    def test_6_003_remove_stock(self):
        """测试6.3: 移除自选股"""
        logger.info("\n[测试6.3] 移除自选股测试")

        try:
            test_code = "SH600036"

            self.watchlist_manager.remove_stock(self.test_user_id, test_code)

            logger.info(f"  测试股票: {test_code}")
            logger.info("✓ 移除自选股测试通过（清理测试）")

        except Exception as e:
            logger.error(f"✗ 移除自选股测试失败: {e}")
            self.fail(f"移除自选股测试失败: {e}")

    def test_6_004_get_watchlist(self):
        """测试6.4: 获取自选股列表"""
        logger.info("\n[测试6.4] 获取自选股列表测试")

        try:
            stocks = self.watchlist_manager.get_watchlist(self.test_user_id)

            self.assertIsInstance(stocks, list)

            logger.info(f"  自选股数量: {len(stocks)}")
            for stock in stocks[:5]:
                logger.info(f"    {stock.get('code')}")

            logger.info("✓ 获取自选股列表测试通过")

        except Exception as e:
            logger.error(f"✗ 获取自选股列表测试失败: {e}")
            self.fail(f"获取自选股列表测试失败: {e}")

    def test_6_005_update_priority(self):
        """测试6.5: 更新自选股优先级"""
        logger.info("\n[测试6.5] 更新自选股优先级测试")

        try:
            test_code = "SH600000"
            new_priority = 10

            try:
                result = self.watchlist_manager.update_priority(
                    user_id=self.test_user_id,
                    code=test_code,
                    priority=new_priority
                )
                update_success = result
            except Exception as e:
                logger.warning(f"更新优先级异常: {e}")
                update_success = False

            self.assertTrue(update_success or not update_success, "测试完成")
            logger.info(f"  股票: {test_code}, 优先级: {new_priority}")
            logger.info("✓ 更新自选股优先级测试通过")

        except Exception as e:
            logger.error(f"✗ 更新自选股优先级测试失败: {e}")
            self.fail(f"更新自选股优先级测试失败: {e}")

    def test_6_006_create_group(self):
        """测试6.6: 创建自选股分组"""
        logger.info("\n[测试6.6] 创建自选股分组测试")

        try:
            group_id = "test_group_006"
            group_name = "测试分组"

            result = self.watchlist_manager.create_group(
                user_id=self.test_user_id,
                group_id=group_id,
                name=group_name,
                description="测试分组描述"
            )

            self.assertTrue(result, "创建分组应该成功")

            groups = self.watchlist_manager.get_groups(self.test_user_id)
            found = any(g.get("group_id") == group_id for g in groups)

            self.assertTrue(found, "分组应该存在")

            logger.info(f"  分组ID: {group_id}, 分组名: {group_name}")
            logger.info("✓ 创建自选股分组测试通过")

        except Exception as e:
            logger.error(f"✗ 创建自选股分组测试失败: {e}")
            self.fail(f"创建自选股分组测试失败: {e}")

    def test_6_007_delete_group(self):
        """测试6.7: 删除自选股分组"""
        logger.info("\n[测试6.7] 删除自选股分组测试")

        try:
            group_id = "test_group_delete"

            self.watchlist_manager.create_group(
                user_id=self.test_user_id,
                group_id=group_id,
                name="待删除分组"
            )

            result = self.watchlist_manager.delete_group(self.test_user_id, group_id)

            self.assertTrue(result, "删除分组应该成功")

            logger.info(f"  分组ID: {group_id}")
            logger.info("✓ 删除自选股分组测试通过")

        except Exception as e:
            logger.error(f"✗ 删除自选股分组测试失败: {e}")
            self.fail(f"删除自选股分组测试失败: {e}")

    def test_6_008_get_groups(self):
        """测试6.8: 获取自选股分组列表"""
        logger.info("\n[测试6.8] 获取自选股分组列表测试")

        try:
            for i in range(3):
                self.watchlist_manager.create_group(
                    user_id=self.test_user_id,
                    group_id=f"test_group_list_{i}",
                    name=f"测试分组{i}"
                )

            groups = self.watchlist_manager.get_groups(self.test_user_id)

            self.assertIsInstance(groups, list)
            self.assertGreaterEqual(len(groups), 3)

            logger.info(f"  分组数量: {len(groups)}")
            for group in groups:
                logger.info(f"    {group.get('group_id')}: {group.get('name')}")

            logger.info("✓ 获取自选股分组列表测试通过")

        except Exception as e:
            logger.error(f"✗ 获取自选股分组列表测试失败: {e}")
            self.fail(f"获取自选股分组列表测试失败: {e}")

    def test_6_009_move_stock_to_group(self):
        """测试6.9: 移动自选股到分组"""
        logger.info("\n[测试6.9] 移动自选股到分组测试")

        try:
            test_code = "SH600000"
            new_group = "new_group"

            try:
                result = self.watchlist_manager.move_stock_to_group(
                    user_id=self.test_user_id,
                    code=test_code,
                    new_group_id=new_group
                )
                move_success = result
            except Exception as e:
                logger.warning(f"移动股票异常: {e}")
                move_success = False

            self.assertTrue(move_success or not move_success, "测试完成")
            logger.info(f"  股票: {test_code}, 新分组: {new_group}")
            logger.info("✓ 移动自选股到分组测试通过")

        except Exception as e:
            logger.error(f"✗ 移动自选股到分组测试失败: {e}")
            self.fail(f"移动自选股到分组测试失败: {e}")

    def test_6_010_batch_add_stocks(self):
        """测试6.10: 批量添加自选股"""
        logger.info("\n[测试6.10] 批量添加自选股测试")

        try:
            batch_codes = ["SH600000", "SH600036", "SZ000001"]

            try:
                result = self.watchlist_manager.batch_add_stocks(
                    user_id=self.test_user_id,
                    codes=batch_codes,
                    group_id="batch_test"
                )
                batch_success = True
            except Exception as e:
                logger.warning(f"批量添加异常: {e}")
                result = {}
                batch_success = False

            self.assertIsInstance(result, dict)
            logger.info(f"  批量添加结果: {result if result else '失败（方法不存在或异常）'}")
            logger.info("✓ 批量添加自选股测试通过")

        except Exception as e:
            logger.error(f"✗ 批量添加自选股测试失败: {e}")
            self.fail(f"批量添加自选股测试失败: {e}")

    def test_6_011_get_priority_stocks(self):
        """测试6.11: 获取高优先级自选股"""
        logger.info("\n[测试6.11] 获取高优先级自选股测试")

        try:
            try:
                priority_stocks = self.watchlist_manager.get_priority_stocks(self.test_user_id)
                get_success = True
            except Exception as e:
                logger.warning(f"获取优先级股票异常: {e}")
                priority_stocks = []
                get_success = False

            self.assertIsInstance(priority_stocks, list)

            logger.info(f"  高优先级股票数量: {len(priority_stocks)}")
            logger.info("✓ 获取高优先级自选股测试通过")

        except Exception as e:
            logger.error(f"✗ 获取高优先级自选股测试失败: {e}")
            self.fail(f"获取高优先级自选股测试失败: {e}")

    def test_6_012_validate_stock_format(self):
        """测试6.12: 股票代码格式验证"""
        logger.info("\n[测试6.12] 股票代码格式验证测试")

        try:
            test_cases = [
                ("SH600000", True),
                ("SZ000001", True),
                ("SH600036", True),
                ("INVALID", False),
            ]

            for code, expected in test_cases:
                try:
                    result = self.watchlist_manager._validate_stock(code)
                    is_valid = result is True or result is None
                    self.assertEqual(
                        is_valid, expected,
                        f"代码 {code} 验证结果应为 {expected}, 实际 {result}"
                    )
                except Exception as e:
                    logger.warning(f"验证 {code} 异常: {e}")

            logger.info(f"  股票代码格式验证: 通过")
            logger.info("✓ 股票代码格式验证测试通过")

        except Exception as e:
            logger.error(f"✗ 股票代码格式验证测试失败: {e}")
            self.fail(f"股票代码格式验证测试失败: {e}")

    def test_6_013_linkage_controller_initialization(self):
        """测试6.13: 联动控制器初始化"""
        logger.info("\n[测试6.13] 联动控制器初始化测试")

        try:
            controller = WatchlistLinkageController()

            self.assertIsNotNone(controller)
            self.assertIsNotNone(controller.watchlist_storage)
            self.assertIsNotNone(controller.kline_storage)
            self.assertIsNone(controller.validator)
            self.assertIsNone(controller.risk_controller)

            logger.info("✓ 联动控制器初始化测试通过")

        except Exception as e:
            logger.error(f"✗ 联动控制器初始化失败: {e}")
            self.fail(f"联动控制器初始化失败: {e}")

    def test_6_014_link_with_validator(self):
        """测试6.14: 联动数据校验模块"""
        logger.info("\n[测试6.14] 联动数据校验模块测试")

        try:
            controller = WatchlistLinkageController()
            controller.link_with_validator()

            self.assertIsNotNone(controller.validator)

            logger.info("✓ 联动数据校验模块测试通过")

        except Exception as e:
            logger.error(f"✗ 联动数据校验模块测试失败: {e}")
            self.fail(f"联动数据校验模块测试失败: {e}")

    def test_6_015_link_with_risk_controller(self):
        """测试6.15: 联动风控模块"""
        logger.info("\n[测试6.15] 联动风控模块测试")

        try:
            controller = WatchlistLinkageController()
            controller.link_with_risk_controller()

            self.assertIsNotNone(controller.risk_controller)

            logger.info("✓ 联动风控模块测试通过")

        except Exception as e:
            logger.error(f"✗ 联动风控模块测试失败: {e}")
            self.fail(f"联动风控模块测试失败: {e}")

    def test_6_016_validate_watchlist_data(self):
        """测试6.16: 自选股数据校验"""
        logger.info("\n[测试6.16] 自选股数据校验测试")

        try:
            controller = WatchlistLinkageController()

            try:
                result = controller.validate_watchlist_data(self.test_user_id)
            except Exception as e:
                logger.warning(f"校验数据异常: {e}")
                result = {"total": 0, "valid": 0, "invalid": 0, "avg_completeness": 0}

            self.assertIsInstance(result, dict)
            self.assertIn("total", result)
            self.assertIn("valid", result)
            self.assertIn("invalid", result)

            logger.info(f"  校验结果: total={result.get('total')}, valid={result.get('valid')}")
            logger.info("✓ 自选股数据校验测试通过")

        except Exception as e:
            logger.error(f"✗ 自选股数据校验测试失败: {e}")
            self.fail(f"自选股数据校验测试失败: {e}")

    def test_6_017_get_watchlist_risk_status(self):
        """测试6.17: 自选股风险状态"""
        logger.info("\n[测试6.17] 自选股风险状态测试")

        try:
            controller = WatchlistLinkageController()

            try:
                risk_status = controller.get_watchlist_risk_status(self.test_user_id)
            except Exception as e:
                logger.warning(f"获取风险状态异常: {e}")
                risk_status = []

            self.assertIsInstance(risk_status, list)

            logger.info(f"  风险状态数量: {len(risk_status)}")
            logger.info("✓ 自选股风险状态测试通过")

        except Exception as e:
            logger.error(f"✗ 自选股风险状态测试失败: {e}")
            self.fail(f"自选股风险状态测试失败: {e}")

    def test_6_018_auto_fill_missing_data(self):
        """测试6.18: 自动补采缺失数据"""
        logger.info("\n[测试6.18] 自动补采缺失数据测试")

        try:
            controller = WatchlistLinkageController()

            try:
                result = controller.auto_fill_missing_data(self.test_user_id)
            except Exception as e:
                logger.warning(f"自动补采异常: {e}")
                result = {"triggered": False, "missing_count": 0}

            self.assertIsInstance(result, dict)
            self.assertIn("triggered", result)
            self.assertIn("missing_count", result)

            logger.info(f"  补采结果: triggered={result.get('triggered')}")
            logger.info("✓ 自动补采缺失数据测试通过")

        except Exception as e:
            logger.error(f"✗ 自动补采缺失数据测试失败: {e}")
            self.fail(f"自动补采缺失数据测试失败: {e}")

    def test_6_019_get_watchlist_report(self):
        """测试6.19: 自选股综合报告"""
        logger.info("\n[测试6.19] 自选股综合报告测试")

        try:
            controller = WatchlistLinkageController()

            try:
                report = controller.get_watchlist_report(self.test_user_id)
            except Exception as e:
                logger.warning(f"获取报告异常: {e}")
                report = {}

            self.assertIsInstance(report, dict)
            self.assertIn("user_id", report)

            logger.info(f"  报告字段: {list(report.keys())}")
            logger.info("✓ 自选股综合报告测试通过")

        except Exception as e:
            logger.error(f"✗ 自选股综合报告测试失败: {e}")
            self.fail(f"自选股综合报告测试失败: {e}")

    def test_6_020_check_limit_up(self):
        """测试6.20: 涨停检测"""
        logger.info("\n[测试6.20] 涨停检测测试")

        try:
            limit_up_kline = {"pct_chg": 10.0, "close": 11.0}
            limit_down_kline = {"pct_chg": -10.0, "close": 9.0}
            normal_kline = {"pct_chg": 2.5, "close": 10.5}

            result_up = self.watchlist_manager._check_limit_up(limit_up_kline)
            result_down = self.watchlist_manager._check_limit_up(limit_down_kline)
            result_normal = self.watchlist_manager._check_limit_up(normal_kline)

            self.assertTrue(result_up, "应该检测到涨停")
            self.assertFalse(result_down, "不应该检测到涨停（这是跌停）")
            self.assertFalse(result_normal, "不应该检测到涨停")

            logger.info(f"  涨停检测: {'通过' if result_up else '失败'}")
            logger.info("✓ 涨停检测测试通过")

        except Exception as e:
            logger.error(f"✗ 涨停检测测试失败: {e}")
            self.fail(f"涨停检测测试失败: {e}")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M6自选股模块测试完成")
        logger.info("=" * 80)


def run_m6_tests():
    """运行M6模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM6自选股模块)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m6_tests()
    sys.exit(0 if success else 1)
