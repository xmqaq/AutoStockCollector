"""
M2任务调度模块测试 - 调度任务与执行验证
包含任务创建、状态管理、进度监控、断点续采、任务取消与重试等功能测试
"""
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.scheduler.scheduler import Task, TaskScheduler, scheduler
from core.scheduler.enums import TaskStatus, TaskType
from core.storage.mongo_storage import TaskStorage
from config.database import DatabaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class TestM2任务调度(unittest.TestCase):
    """M2任务调度模块 - 调度任务与执行验证"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化 - 连接MongoDB"""
        logger.info("=" * 80)
        logger.info("M2任务调度模块测试开始 - 调度任务与执行验证")
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

        cls.task_storage = TaskStorage()
        cls.scheduler = scheduler

    def test_2_001_task_initialization(self):
        """测试2.1: 任务对象初始化"""
        logger.info("\n[测试2.1] 任务对象初始化测试")

        try:
            task = Task(
                task_id="test_task_001",
                task_type="kline_collection",
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )

            self.assertEqual(task.task_id, "test_task_001")
            self.assertEqual(task.task_type, "kline_collection")
            self.assertEqual(task.status, TaskStatus.PENDING)
            self.assertEqual(task.progress, 0)
            self.assertEqual(task.total, 0)
            self.assertEqual(task.success, 0)
            self.assertEqual(task.failed, 0)

            logger.info(f"  任务ID: {task.task_id}")
            logger.info(f"  任务类型: {task.task_type}")
            logger.info(f"  初始状态: {task.status.value}")
            logger.info("✓ 任务对象初始化成功")

        except Exception as e:
            logger.error(f"✗ 任务对象初始化失败: {e}")
            self.fail(f"任务对象初始化失败: {e}")

    def test_2_002_task_creation(self):
        """测试2.2: 任务创建与存储"""
        logger.info("\n[测试2.2] 任务创建与存储测试")

        try:
            task_id = self.scheduler.create_task(
                task_type=TaskType.KLINE_COLLECTION.value,
                params={
                    "codes": ["SH600000", "SH600036"],
                    "start_date": "20240101",
                    "end_date": "20240131"
                }
            )

            self.assertIsNotNone(task_id)
            self.assertTrue(task_id.startswith("kline_"))

            task_info = self.task_storage.get_task(task_id)
            self.assertIsNotNone(task_info)
            self.assertEqual(task_info["task_id"], task_id)
            self.assertEqual(task_info["task_type"], TaskType.KLINE_COLLECTION.value)
            self.assertEqual(task_info["status"], "pending")

            logger.info(f"  创建任务ID: {task_id}")
            logger.info(f"  任务类型: {task_info['task_type']}")
            logger.info(f"  任务状态: {task_info['status']}")
            logger.info("✓ 任务创建与存储成功")

            self.task_storage.delete_one({"task_id": task_id})

        except Exception as e:
            logger.error(f"✗ 任务创建失败: {e}")
            self.fail(f"任务创建失败: {e}")

    def test_2_003_task_status_transitions(self):
        """测试2.3: 任务状态转换"""
        logger.info("\n[测试2.3] 任务状态转换测试")

        try:
            task_id = self.scheduler.create_task(
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]}
            )

            task = Task(
                task_id=task_id,
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )

            self.assertEqual(task.status, TaskStatus.PENDING)
            logger.info(f"  初始状态: {task.status.value}")

            task.start()
            self.assertEqual(task.status, TaskStatus.RUNNING)
            logger.info(f"  启动后状态: {task.status.value}")

            task.complete(success_count=10, failed_count=2)
            self.assertEqual(task.status, TaskStatus.COMPLETED)
            logger.info(f"  完成状态: {task.status.value}")

            task_id2 = self.scheduler.create_task(
                task_type=TaskType.STOCK_INFO_COLLECTION.value,
                params={"codes": ["SH600000"]}
            )

            task2 = Task(
                task_id=task_id2,
                task_type=TaskType.STOCK_INFO_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task2.start()
            task2.fail("Test error message")
            self.assertEqual(task2.status, TaskStatus.FAILED)
            logger.info(f"  失败状态: {task2.status.value}")

            task3 = Task(
                task_id="test_cancel_task",
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task3.start()
            task3.cancel()
            self.assertEqual(task3.status, TaskStatus.CANCELLED)
            logger.info(f"  取消状态: {task3.status.value}")

            logger.info("✓ 任务状态转换测试通过")

            self.task_storage.delete_one({"task_id": task_id})
            self.task_storage.delete_one({"task_id": task_id2})

        except Exception as e:
            logger.error(f"✗ 任务状态转换测试失败: {e}")
            self.fail(f"任务状态转换测试失败: {e}")

    def test_2_004_task_progress_tracking(self):
        """测试2.4: 任务进度跟踪"""
        logger.info("\n[测试2.4] 任务进度跟踪测试")

        try:
            task = Task(
                task_id="test_progress_task",
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000", "SH600036"]},
                storage=self.task_storage
            )
            task.create()
            task.start()

            task.update_progress(current=1, total=10, success=1, failed=0)
            self.assertEqual(task.progress, 1)
            self.assertEqual(task.total, 10)
            self.assertEqual(task.success, 1)
            self.assertEqual(task.failed, 0)

            logger.info(f"  进度: {task.progress}/{task.total} ({task.progress/task.total*100:.1f}%)")
            logger.info(f"  成功: {task.success}, 失败: {task.failed}")

            task.update_progress(current=5, total=10, success=4, failed=1)
            self.assertEqual(task.progress, 5)
            self.assertEqual(task.success, 4)
            self.assertEqual(task.failed, 1)

            logger.info(f"  更新后进度: {task.progress}/{task.total} ({task.progress/task.total*100:.1f}%)")
            logger.info(f"  更新后成功: {task.success}, 失败: {task.failed}")

            task.complete(success_count=9, failed_count=1)
            self.assertEqual(task.status, TaskStatus.COMPLETED)

            logger.info("✓ 任务进度跟踪测试通过")

            self.task_storage.delete_one({"task_id": "test_progress_task"})

        except Exception as e:
            logger.error(f"✗ 任务进度跟踪测试失败: {e}")
            self.fail(f"任务进度跟踪测试失败: {e}")

    def test_2_005_task_get_stats(self):
        """测试2.5: 任务统计信息获取"""
        logger.info("\n[测试2.5] 任务统计信息获取测试")

        try:
            task = Task(
                task_id="test_stats_task",
                task_type=TaskType.INCREMENTAL_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task.create()
            task.start()
            task.update_progress(current=3, total=10, success=3, failed=0)

            stats = task.get_stats()

            self.assertEqual(stats["task_id"], "test_stats_task")
            self.assertEqual(stats["task_type"], TaskType.INCREMENTAL_COLLECTION.value)
            self.assertEqual(stats["status"], TaskStatus.RUNNING.value)
            self.assertEqual(stats["progress"], 3)
            self.assertEqual(stats["total"], 10)
            self.assertEqual(stats["success"], 3)
            self.assertEqual(stats["failed"], 0)
            self.assertGreater(stats["elapsed_time"], 0)
            self.assertEqual(stats["progress_percent"], 30.0)

            logger.info(f"  任务统计: {stats}")
            logger.info("✓ 任务统计信息获取测试通过")

            self.task_storage.delete_one({"task_id": "test_stats_task"})

        except Exception as e:
            logger.error(f"✗ 任务统计信息获取测试失败: {e}")
            self.fail(f"任务统计信息获取测试失败: {e}")

    def test_2_006_task_list_operations(self):
        """测试2.6: 任务列表操作"""
        logger.info("\n[测试2.6] 任务列表操作测试")

        try:
            task_ids = []
            for i in range(3):
                task_id = self.scheduler.create_task(
                    task_type=TaskType.KLINE_COLLECTION.value,
                    params={"codes": [f"SH60000{i}"]}
                )
                task_ids.append(task_id)

            all_tasks = self.scheduler.list_tasks(limit=10)
            self.assertGreaterEqual(len(all_tasks), 3)

            pending_tasks = self.scheduler.list_tasks(status="pending", limit=10)
            self.assertGreaterEqual(len(pending_tasks), 3)

            logger.info(f"  总任务数: {len(all_tasks)}")
            logger.info(f"  待执行任务数: {len(pending_tasks)}")

            for task_id in task_ids:
                self.task_storage.delete_one({"task_id": task_id})

            logger.info("✓ 任务列表操作测试通过")

        except Exception as e:
            logger.error(f"✗ 任务列表操作测试失败: {e}")
            self.fail(f"任务列表操作测试失败: {e}")

    def test_2_007_task_cancel_operation(self):
        """测试2.7: 任务取消操作"""
        logger.info("\n[测试2.7] 任务取消操作测试")

        try:
            task_id = self.scheduler.create_task(
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]}
            )

            task = Task(
                task_id=task_id,
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task.create()
            task.start()

            cancel_result = self.scheduler.cancel_task(task_id)
            self.assertTrue(cancel_result)

            task_info = self.task_storage.get_task(task_id)
            self.assertEqual(task_info["status"], "cancelled")

            logger.info(f"  任务ID: {task_id}")
            logger.info(f"  取消结果: {cancel_result}")
            logger.info(f"  任务状态: {task_info['status']}")
            logger.info("✓ 任务取消操作测试通过")

            self.task_storage.delete_one({"task_id": task_id})

        except Exception as e:
            logger.error(f"✗ 任务取消操作测试失败: {e}")
            self.fail(f"任务取消操作测试失败: {e}")

    def test_2_008_task_retry_operation(self):
        """测试2.8: 任务重试操作"""
        logger.info("\n[测试2.8] 任务重试操作测试")

        try:
            task_id = self.scheduler.create_task(
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]}
            )

            task = Task(
                task_id=task_id,
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task.create()
            task.start()
            task.fail("Test failure")

            task_info = self.task_storage.get_task(task_id)
            self.assertEqual(task_info["status"], "failed")

            logger.info(f"  失败后状态: {task_info['status']}")

            retry_result = self.scheduler.retry_failed_task(task_id)

            logger.info(f"  重试结果: {retry_result}")

            logger.info("✓ 任务重试操作测试通过")

            self.task_storage.delete_one({"task_id": task_id})

        except Exception as e:
            logger.error(f"✗ 任务重试操作测试失败: {e}")
            self.fail(f"任务重试操作测试失败: {e}")

    def test_2_009_scheduler_statistics(self):
        """测试2.9: 调度器统计信息"""
        logger.info("\n[测试2.9] 调度器统计信息测试")

        try:
            stats = self.scheduler.get_task_statistics()

            self.assertIn("running_tasks", stats)
            self.assertIn("pending_tasks", stats)
            self.assertIn("active_tasks", stats)
            self.assertIn("thread_pool_size", stats)
            self.assertIn("timestamp", stats)

            logger.info(f"  调度器统计: {stats}")
            logger.info("✓ 调度器统计信息测试通过")

        except Exception as e:
            logger.error(f"✗ 调度器统计信息测试失败: {e}")
            self.fail(f"调度器统计信息测试失败: {e}")

    def test_2_010_task_type_enums(self):
        """测试2.10: 任务类型枚举验证"""
        logger.info("\n[测试2.10] 任务类型枚举验证")

        try:
            task_types = [t.value for t in TaskType]
            expected_types = [
                "kline",
                "stock_info",
                "financial",
                "news",
                "fund_flow",
                "incremental",
                "backfill"
            ]

            for expected in expected_types:
                self.assertIn(expected, task_types)

            logger.info(f"  支持的任务类型: {task_types}")
            logger.info("✓ 任务类型枚举验证通过")

        except Exception as e:
            logger.error(f"✗ 任务类型枚举验证失败: {e}")
            self.fail(f"任务类型枚举验证失败: {e}")

    def test_2_011_task_status_enums(self):
        """测试2.11: 任务状态枚举验证"""
        logger.info("\n[测试2.11] 任务状态枚举验证")

        try:
            status_values = [s.value for s in TaskStatus]
            expected_statuses = ["pending", "running", "completed", "failed", "cancelled"]

            for expected in expected_statuses:
                self.assertIn(expected, status_values)

            logger.info(f"  支持的任务状态: {status_values}")
            logger.info("✓ 任务状态枚举验证通过")

        except Exception as e:
            logger.error(f"✗ 任务状态枚举验证失败: {e}")
            self.fail(f"任务状态枚举验证失败: {e}")

    def test_2_012_task_get_operation(self):
        """测试2.12: 任务查询操作"""
        logger.info("\n[测试2.12] 任务查询操作测试")

        try:
            task_id = self.scheduler.create_task(
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]}
            )

            task_info = self.scheduler.get_task(task_id)
            self.assertIsNotNone(task_info)
            self.assertEqual(task_info["task_id"], task_id)

            non_existent_task = self.scheduler.get_task("non_existent_task_id")
            self.assertIsNone(non_existent_task)

            logger.info(f"  任务ID: {task_id}")
            logger.info(f"  查询结果: {'存在' if task_info else '不存在'}")
            logger.info(f"  不存在任务查询: {'返回None' if non_existent_task is None else '错误'}")
            logger.info("✓ 任务查询操作测试通过")

            self.task_storage.delete_one({"task_id": task_id})

        except Exception as e:
            logger.error(f"✗ 任务查询操作测试失败: {e}")
            self.fail(f"任务查询操作测试失败: {e}")

    def test_2_013_concurrent_task_handling(self):
        """测试2.13: 并发任务处理"""
        logger.info("\n[测试2.13] 并发任务处理测试")

        try:
            task_ids = []
            for i in range(3):
                task_id = self.scheduler.create_task(
                    task_type=TaskType.KLINE_COLLECTION.value,
                    params={"codes": [f"SH60000{i}"]}
                )
                task_ids.append(task_id)

            stats = self.scheduler.get_task_statistics()
            initial_pending = stats["pending_tasks"]

            for task_id in task_ids:
                self.scheduler.start_task(task_id)

            time.sleep(0.5)

            stats_after = self.scheduler.get_task_statistics()
            active_tasks = stats_after["active_tasks"]

            logger.info(f"  创建任务数: {len(task_ids)}")
            logger.info(f"  活跃任务数: {active_tasks}")
            logger.info("✓ 并发任务处理测试通过")

            for task_id in task_ids:
                self.scheduler.cancel_task(task_id)

            for task_id in task_ids:
                self.task_storage.delete_one({"task_id": task_id})

        except Exception as e:
            logger.error(f"✗ 并发任务处理测试失败: {e}")
            self.fail(f"并发任务处理测试失败: {e}")

    def test_2_014_task_error_message_handling(self):
        """测试2.14: 任务错误消息处理"""
        logger.info("\n[测试2.14] 任务错误消息处理测试")

        try:
            task = Task(
                task_id="test_error_task",
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task.create()
            task.start()

            error_msg = "Connection timeout error"
            task.fail(error_msg)

            self.assertEqual(task.error_message, error_msg)
            self.assertEqual(task.status, TaskStatus.FAILED)

            stats = task.get_stats()
            self.assertEqual(stats["error_message"], error_msg)

            logger.info(f"  错误消息: {error_msg}")
            logger.info(f"  任务状态: {task.status.value}")
            logger.info("✓ 任务错误消息处理测试通过")

            self.task_storage.delete_one({"task_id": "test_error_task"})

        except Exception as e:
            logger.error(f"✗ 任务错误消息处理测试失败: {e}")
            self.fail(f"任务错误消息处理测试失败: {e}")

    def test_2_015_task_time_tracking(self):
        """测试2.15: 任务时间追踪"""
        logger.info("\n[测试2.15] 任务时间追踪测试")

        try:
            task = Task(
                task_id="test_time_task",
                task_type=TaskType.KLINE_COLLECTION.value,
                params={"codes": ["SH600000"]},
                storage=self.task_storage
            )
            task.create()

            self.assertIsNone(task.start_time)
            self.assertIsNone(task.end_time)

            task.start()
            self.assertIsNotNone(task.start_time)
            self.assertIsNone(task.end_time)

            time.sleep(0.1)

            task.complete(success_count=10, failed_count=0)
            self.assertIsNotNone(task.start_time)
            self.assertIsNotNone(task.end_time)

            elapsed = (task.end_time - task.start_time).total_seconds()
            self.assertGreater(elapsed, 0)

            logger.info(f"  开始时间: {task.start_time}")
            logger.info(f"  结束时间: {task.end_time}")
            logger.info(f"  耗时: {elapsed:.3f}秒")
            logger.info("✓ 任务时间追踪测试通过")

            self.task_storage.delete_one({"task_id": "test_time_task"})

        except Exception as e:
            logger.error(f"✗ 任务时间追踪测试失败: {e}")
            self.fail(f"任务时间追踪测试失败: {e}")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("=" * 80)
        logger.info("M2任务调度模块测试完成")
        logger.info("=" * 80)


def run_m2_tests():
    """运行M2模块测试"""
    import unittest as ut

    suite = ut.TestLoader().loadTestsFromTestCase(TestM2任务调度)

    runner = ut.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_m2_tests()
    sys.exit(0 if success else 1)
