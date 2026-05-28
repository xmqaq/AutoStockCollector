"""
M4 API接口模块测试 - 接口功能与性能验证
包含健康检查、任务管理、数据查询、自选股管理等功能测试
"""
import unittest
from datetime import datetime
from typing import Dict, Any
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api import create_app
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM4API接口(unittest.TestCase):
    """M4 API接口模块 - 接口功能与性能验证"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 连接MongoDB并启动Flask测试客户端"""
        logger.info("=" * 80)
        logger.info("M4 API接口模块测试开始 - 接口功能与性能验证")
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

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_4_001_health_check(self):
        """测试4.1: 健康检查接口"""
        logger.info("\n[测试4.1] 健康检查接口测试")

        try:
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertEqual(data["status"], "ok")
            self.assertIn("timestamp", data)

            logger.info(f"  响应状态: {data['status']}")
            logger.info(f"  时间戳: {data['timestamp']}")
            logger.info("✓ 健康检查接口测试通过")

        except Exception as e:
            logger.error(f"✗ 健康检查接口测试失败: {e}")
            self.fail(f"健康检查接口测试失败: {e}")

    def test_4_002_task_create(self):
        """测试4.2: 任务创建接口"""
        logger.info("\n[测试4.2] 任务创建接口测试")

        try:
            response = self.client.post(
                "/api/v1/task/create",
                json={
                    "task_type": "kline",
                    "params": {"codes": ["SH600000"]}
                }
            )

            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("task_id", data)

            logger.info(f"  创建任务ID: {data['task_id']}")
            logger.info("✓ 任务创建接口测试通过")

        except Exception as e:
            logger.error(f"✗ 任务创建接口测试失败: {e}")
            self.fail(f"任务创建接口测试失败: {e}")

    def test_4_003_task_get(self):
        """测试4.3: 任务查询接口"""
        logger.info("\n[测试4.3] 任务查询接口测试")

        try:
            create_response = self.client.post(
                "/api/v1/task/create",
                json={
                    "task_type": "kline",
                    "params": {"codes": ["SH600000"]}
                }
            )
            task_id = json.loads(create_response.data)["task_id"]

            response = self.client.get(f"/api/v1/task/{task_id}")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertEqual(data["task_id"], task_id)

            logger.info(f"  查询任务ID: {data['task_id']}")
            logger.info(f"  任务状态: {data['status']}")
            logger.info("✓ 任务查询接口测试通过")

        except Exception as e:
            logger.error(f"✗ 任务查询接口测试失败: {e}")
            self.fail(f"任务查询接口测试失败: {e}")

    def test_4_004_task_list(self):
        """测试4.4: 任务列表接口"""
        logger.info("\n[测试4.4] 任务列表接口测试")

        try:
            response = self.client.get("/api/v1/tasks")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("tasks", data)
            self.assertIsInstance(data["tasks"], list)

            logger.info(f"  任务列表数量: {len(data['tasks'])}")
            logger.info("✓ 任务列表接口测试通过")

        except Exception as e:
            logger.error(f"✗ 任务列表接口测试失败: {e}")
            self.fail(f"任务列表接口测试失败: {e}")

    def test_4_005_task_start(self):
        """测试4.5: 任务启动接口"""
        logger.info("\n[测试4.5] 任务启动接口测试")

        try:
            create_response = self.client.post(
                "/api/v1/task/create",
                json={
                    "task_type": "kline",
                    "params": {"codes": ["SH600000"]}
                }
            )
            task_id = json.loads(create_response.data)["task_id"]

            response = self.client.post(f"/api/v1/task/{task_id}/start")
            self.assertIn(response.status_code, [200, 400])

            data = json.loads(response.data)
            logger.info(f"  启动响应: {data}")
            logger.info("✓ 任务启动接口测试通过")

        except Exception as e:
            logger.error(f"✗ 任务启动接口测试失败: {e}")
            self.fail(f"任务启动接口测试失败: {e}")

    def test_4_006_task_cancel(self):
        """测试4.6: 任务取消接口"""
        logger.info("\n[测试4.6] 任务取消接口测试")

        try:
            create_response = self.client.post(
                "/api/v1/task/create",
                json={
                    "task_type": "kline",
                    "params": {"codes": ["SH600000"]}
                }
            )
            task_id = json.loads(create_response.data)["task_id"]

            response = self.client.post(f"/api/v1/task/{task_id}/cancel")
            self.assertIn(response.status_code, [200, 400])

            data = json.loads(response.data)
            logger.info(f"  取消响应: {data}")
            logger.info("✓ 任务取消接口测试通过")

        except Exception as e:
            logger.error(f"✗ 任务取消接口测试失败: {e}")
            self.fail(f"任务取消接口测试失败: {e}")

    def test_4_007_kline_query(self):
        """测试4.7: K线数据查询接口"""
        logger.info("\n[测试4.7] K线数据查询接口测试")

        try:
            response = self.client.get("/api/v1/kline/SH600000")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("data", data)

            logger.info(f"  查询股票: {data['code']}")
            logger.info(f"  记录数量: {data['count']}")
            logger.info("✓ K线数据查询接口测试通过")

        except Exception as e:
            logger.error(f"✗ K线数据查询接口测试失败: {e}")
            self.fail(f"K线数据查询接口测试失败: {e}")

    def test_4_008_kline_latest(self):
        """测试4.8: 最新K线数据接口"""
        logger.info("\n[测试4.8] 最新K线数据接口测试")

        try:
            response = self.client.get("/api/v1/kline/SH600000/latest")
            self.assertIn(response.status_code, [200, 404])

            if response.status_code == 200:
                data = json.loads(response.data)
                self.assertTrue(data["success"])
                self.assertIn("data", data)
                logger.info("✓ 最新K线数据接口测试通过（数据存在）")
            else:
                logger.info("⚠ 最新K线数据接口测试通过（无数据）")

        except Exception as e:
            logger.error(f"✗ 最新K线数据接口测试失败: {e}")
            self.fail(f"最新K线数据接口测试失败: {e}")

    def test_4_009_stock_info(self):
        """测试4.9: 股票信息查询接口"""
        logger.info("\n[测试4.9] 股票信息查询接口测试")

        try:
            response = self.client.get("/api/v1/stock/SH600000/info")
            self.assertIn(response.status_code, [200, 404])

            if response.status_code == 200:
                data = json.loads(response.data)
                self.assertTrue(data["success"])
                self.assertIn("data", data)
                logger.info("✓ 股票信息查询接口测试通过（数据存在）")
            else:
                logger.info("⚠ 股票信息查询接口测试通过（无数据）")

        except Exception as e:
            logger.error(f"✗ 股票信息查询接口测试失败: {e}")
            self.fail(f"股票信息查询接口测试失败: {e}")

    def test_4_010_financial_query(self):
        """测试4.10: 财务数据查询接口"""
        logger.info("\n[测试4.10] 财务数据查询接口测试")

        try:
            response = self.client.get("/api/v1/financial/SH600000")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("data", data)

            logger.info(f"  查询股票: SH600000")
            logger.info(f"  记录数量: {data['count']}")
            logger.info("✓ 财务数据查询接口测试通过")

        except Exception as e:
            logger.error(f"✗ 财务数据查询接口测试失败: {e}")
            self.fail(f"财务数据查询接口测试失败: {e}")

    def test_4_011_news_query(self):
        """测试4.11: 新闻数据查询接口"""
        logger.info("\n[测试4.11] 新闻数据查询接口测试")

        try:
            response = self.client.get("/api/v1/news")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("data", data)

            logger.info(f"  新闻记录数量: {data['count']}")
            logger.info("✓ 新闻数据查询接口测试通过")

        except Exception as e:
            logger.error(f"✗ 新闻数据查询接口测试失败: {e}")
            self.fail(f"新闻数据查询接口测试失败: {e}")

    def test_4_012_fund_flow_query(self):
        """测试4.12: 资金流向查询接口"""
        logger.info("\n[测试4.12] 资金流向查询接口测试")

        try:
            response = self.client.get("/api/v1/fund-flow/SH600000")
            self.assertIn(response.status_code, [200, 404])

            if response.status_code == 200:
                data = json.loads(response.data)
                self.assertTrue(data["success"])
                self.assertIn("data", data)
                logger.info("✓ 资金流向查询接口测试通过（数据存在）")
            else:
                logger.info("⚠ 资金流向查询接口测试通过（无数据）")

        except Exception as e:
            logger.error(f"✗ 资金流向查询接口测试失败: {e}")
            self.fail(f"资金流向查询接口测试失败: {e}")

    def test_4_013_validation_batch(self):
        """测试4.13: 批量校验接口"""
        logger.info("\n[测试4.13] 批量校验接口测试")

        try:
            response = self.client.post(
                "/api/v1/validation/kline",
                json={
                    "codes": ["SH600000", "SH600036"]
                }
            )
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("results", data)

            logger.info(f"  校验结果数量: {len(data['results'])}")
            logger.info("✓ 批量校验接口测试通过")

        except Exception as e:
            logger.error(f"✗ 批量校验接口测试失败: {e}")
            self.fail(f"批量校验接口测试失败: {e}")

    def test_4_014_validation_report(self):
        """测试4.14: 校验报告接口"""
        logger.info("\n[测试4.14] 校验报告接口测试")

        try:
            response = self.client.get("/api/v1/validation/report")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("report", data)

            logger.info(f"  报告内容: {list(data['report'].keys())}")
            logger.info("✓ 校验报告接口测试通过")

        except Exception as e:
            logger.error(f"✗ 校验报告接口测试失败: {e}")
            self.fail(f"校验报告接口测试失败: {e}")

    def test_4_015_validation_gaps(self):
        """测试4.15: 数据间隙检查接口"""
        logger.info("\n[测试4.15] 数据间隙检查接口测试")

        try:
            response = self.client.get(
                "/api/v1/validation/gaps",
                query_string={
                    "code": "SH600000",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31"
                }
            )
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("missing_dates", data)

            logger.info(f"  缺失日期数量: {data['missing_count']}")
            logger.info("✓ 数据间隙检查接口测试通过")

        except Exception as e:
            logger.error(f"✗ 数据间隙检查接口测试失败: {e}")
            self.fail(f"数据间隙检查接口测试失败: {e}")

    def test_4_016_watchlist_get(self):
        """测试4.16: 自选股列表接口"""
        logger.info("\n[测试4.16] 自选股列表接口测试")

        try:
            response = self.client.get("/api/v1/watchlist")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("data", data)

            logger.info(f"  自选股数量: {data['count']}")
            logger.info("✓ 自选股列表接口测试通过")

        except Exception as e:
            logger.error(f"✗ 自选股列表接口测试失败: {e}")
            self.fail(f"自选股列表接口测试失败: {e}")

    def test_4_017_watchlist_add(self):
        """测试4.17: 添加自选股接口"""
        logger.info("\n[测试4.17] 添加自选股接口测试")

        try:
            response = self.client.post(
                "/api/v1/watchlist",
                json={
                    "user_id": "test_user",
                    "code": "SH600000",
                    "group_id": "test_group",
                    "priority": 1
                }
            )
            self.assertIn(response.status_code, [200, 400])

            data = json.loads(response.data)
            logger.info(f"  添加响应: {data}")
            logger.info("✓ 添加自选股接口测试通过")

        except Exception as e:
            logger.error(f"✗ 添加自选股接口测试失败: {e}")
            self.fail(f"添加自选股接口测试失败: {e}")

    def test_4_018_watchlist_remove(self):
        """测试4.18: 移除自选股接口"""
        logger.info("\n[测试4.18] 移除自选股接口测试")

        try:
            response = self.client.delete(
                "/api/v1/watchlist/SH600000",
                query_string={"user_id": "test_user"}
            )
            self.assertIn(response.status_code, [200, 400])

            data = json.loads(response.data)
            logger.info(f"  移除响应: {data}")
            logger.info("✓ 移除自选股接口测试通过")

        except Exception as e:
            logger.error(f"✗ 移除自选股接口测试失败: {e}")
            self.fail(f"移除自选股接口测试失败: {e}")

    def test_4_019_strategy_list(self):
        """测试4.19: 策略列表接口"""
        logger.info("\n[测试4.19] 策略列表接口测试")

        try:
            response = self.client.get("/api/v1/strategy/list")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("strategies", data)

            logger.info(f"  策略数量: {len(data['strategies'])}")
            logger.info("✓ 策略列表接口测试通过")

        except Exception as e:
            logger.error(f"✗ 策略列表接口测试失败: {e}")
            self.fail(f"策略列表接口测试失败: {e}")

    def test_4_020_scheduler_stats(self):
        """测试4.20: 调度器统计接口"""
        logger.info("\n[测试4.20] 调度器统计接口测试")

        try:
            response = self.client.get("/api/v1/scheduler/stats")
            self.assertEqual(response.status_code, 200)

            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("stats", data)

            logger.info(f"  调度器统计: {data['stats']}")
            logger.info("✓ 调度器统计接口测试通过")

        except Exception as e:
            logger.error(f"✗ 调度器统计接口测试失败: {e}")
            self.fail(f"调度器统计接口测试失败: {e}")

    def test_4_021_error_handler_404(self):
        """测试4.21: 404错误处理"""
        logger.info("\n[测试4.21] 404错误处理测试")

        try:
            response = self.client.get("/api/v1/nonexistent")
            self.assertEqual(response.status_code, 404)

            data = json.loads(response.data)
            self.assertIn("error", data)

            logger.info(f"  错误响应: {data}")
            logger.info("✓ 404错误处理测试通过")

        except Exception as e:
            logger.error(f"✗ 404错误处理测试失败: {e}")
            self.fail(f"404错误处理测试失败: {e}")

    def test_4_022_invalid_task_create(self):
        """测试4.22: 无效任务创建验证"""
        logger.info("\n[测试4.22] 无效任务创建验证测试")

        try:
            response = self.client.post(
                "/api/v1/task/create",
                json={}
            )
            self.assertIn(response.status_code, [400, 500])

            data = json.loads(response.data)
            has_error = "error" in data or not data.get("success", True)

            logger.info(f"  响应状态: {response.status_code}")
            logger.info(f"  错误响应: {data}")
            self.assertTrue(has_error, "应返回错误信息")
            logger.info("✓ 无效任务创建验证测试通过")

        except Exception as e:
            logger.error(f"✗ 无效任务创建验证测试失败: {e}")
            self.fail(f"无效任务创建验证测试失败: {e}")

    def test_4_023_missing_code_validation(self):
        """测试4.23: 缺少股票代码验证"""
        logger.info("\n[测试4.23] 缺少股票代码验证测试")

        try:
            response = self.client.post(
                "/api/v1/watchlist",
                json={
                    "user_id": "test_user"
                }
            )
            self.assertEqual(response.status_code, 400)

            data = json.loads(response.data)
            self.assertIn("error", data)

            logger.info(f"  错误响应: {data}")
            logger.info("✓ 缺少股票代码验证测试通过")

        except Exception as e:
            logger.error(f"✗ 缺少股票代码验证测试失败: {e}")
            self.fail(f"缺少股票代码验证测试失败: {e}")

    def test_4_024_stock_code_format_compatibility(self):
        """测试4.24: 股票代码格式兼容性测试"""
        logger.info("\n[测试4.24] 股票代码格式兼容性测试")

        test_cases = [
            ("000001", "SZ000001"),
            ("600000", "SH600000"),
            ("SZ000001", "SZ000001"),
            ("SH600000", "SH600000"),
            ("sz000001", "SZ000001"),
            ("SH600000", "SH600000"),
            ("300001", "SZ300001"),
            ("688001", "SH688001"),
        ]

        try:
            for input_code, expected_code in test_cases:
                response = self.client.get(f"/api/v1/kline/{input_code}")
                self.assertEqual(response.status_code, 200)

                data = json.loads(response.data)
                self.assertTrue(data["success"])
                self.assertEqual(data["code"], expected_code,
                    f"股票代码 {input_code} 应转换为 {expected_code}，实际为 {data['code']}")

                logger.info(f"  ✓ {input_code} -> {data['code']}")

            logger.info("✓ 股票代码格式兼容性测试通过")

        except Exception as e:
            logger.error(f"✗ 股票代码格式兼容性测试失败: {e}")
            self.fail(f"股票代码格式兼容性测试失败: {e}")

    def test_4_025_stock_code_flexible_format_all_endpoints(self):
        """测试4.25: 多接口股票代码格式兼容性测试"""
        logger.info("\n[测试4.25] 多接口股票代码格式兼容性测试")

        endpoints_to_test = [
            ("/api/v1/kline/000001", "kline"),
            ("/api/v1/stock/000001/info", "stock_info"),
            ("/api/v1/financial/000001", "financial"),
            ("/api/v1/fund-flow/000001", "fund_flow"),
        ]

        try:
            for endpoint, name in endpoints_to_test:
                response = self.client.get(endpoint)
                self.assertIn(response.status_code, [200, 404],
                    f"{name} 接口应返回 200 或 404")

                if response.status_code == 200:
                    data = json.loads(response.data)
                    self.assertTrue(data.get("success", False) or "data" in data,
                        f"{name} 接口应返回有效响应")

                logger.info(f"  ✓ {name} 接口接受纯数字股票代码")

            logger.info("✓ 多接口股票代码格式兼容性测试通过")

        except Exception as e:
            logger.error(f"✗ 多接口股票代码格式兼容性测试失败: {e}")
            self.fail(f"多接口股票代码格式兼容性测试失败: {e}")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M4 API接口模块测试完成")
        logger.info("=" * 80)


def run_m4_tests():
    """运行M4模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM4API接口)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m4_tests()
    sys.exit(0 if success else 1)
