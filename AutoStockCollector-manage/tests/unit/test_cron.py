"""定时调度测试：直接调 job 函数验证 create+start，不起线程/不等时间。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.scheduler.cron import run_ai_pick_job, get_cron_time


class TestRunAiPickJob(unittest.TestCase):
    def test_job_creates_and_starts_ai_pick_task(self):
        fake_scheduler = MagicMock()
        fake_scheduler.create_task.return_value = "ai_pick_123"
        run_ai_pick_job(scheduler=fake_scheduler)
        args, _ = fake_scheduler.create_task.call_args
        self.assertEqual(args[0], "ai_pick")
        fake_scheduler.start_task.assert_called_once_with("ai_pick_123")

    def test_job_swallows_errors(self):
        fake_scheduler = MagicMock()
        fake_scheduler.create_task.side_effect = RuntimeError("db down")
        # 不应抛出（定时任务失败不能崩线程）
        run_ai_pick_job(scheduler=fake_scheduler)


class TestGetCronTime(unittest.TestCase):
    def test_default_time(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("AI_PICK_CRON_TIME", None)
            self.assertEqual(get_cron_time(), "15:30")

    def test_env_override(self):
        import os
        with patch.dict("os.environ", {"AI_PICK_CRON_TIME": "16:05"}):
            self.assertEqual(get_cron_time(), "16:05")


if __name__ == "__main__":
    unittest.main()
