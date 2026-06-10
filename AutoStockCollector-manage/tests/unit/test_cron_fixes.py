"""测试定时任务修复：僵尸任务检测、状态回写、重复注册防护、next_run 恢复。"""
import unittest
import sys
import datetime
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zoneinfo import ZoneInfo

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _now():
    return datetime.datetime.now(_BEIJING_TZ).replace(tzinfo=None)


def _patch_scheduler(fake_scheduler):
    """_is_task_running 内部用 from ... import scheduler，需 patch 模块属性。"""
    mod = MagicMock()
    mod.scheduler = fake_scheduler
    return patch.dict("sys.modules", {"core.scheduler.scheduler": mod})


class TestIsTaskRunningStaleDetection(unittest.TestCase):
    """问题四：_is_task_running 应跳过超时的僵尸任务。"""

    @patch("core.scheduler.cron._cancel_stale_task")
    def test_stale_running_task_not_blocking(self, mock_cancel):
        from core.scheduler.cron import _is_task_running, _STALE_TASK_SECONDS

        stale_time = (_now() - datetime.timedelta(seconds=_STALE_TASK_SECONDS + 100)).isoformat()
        fake_scheduler = MagicMock()
        fake_scheduler.list_tasks.return_value = [
            {"task_type": "news", "status": "running", "start_time": stale_time, "task_id": "news_old"},
        ]
        with _patch_scheduler(fake_scheduler):
            result = _is_task_running("news")
        self.assertFalse(result)
        mock_cancel.assert_called_once()

    def test_fresh_running_task_blocks(self):
        from core.scheduler.cron import _is_task_running

        fresh_time = _now().isoformat()
        fake_scheduler = MagicMock()
        fake_scheduler.list_tasks.return_value = [
            {"task_type": "news", "status": "running", "start_time": fresh_time, "task_id": "news_new"},
        ]
        with _patch_scheduler(fake_scheduler):
            result = _is_task_running("news")
        self.assertTrue(result)

    def test_no_running_tasks(self):
        from core.scheduler.cron import _is_task_running

        fake_scheduler = MagicMock()
        fake_scheduler.list_tasks.return_value = [
            {"task_type": "news", "status": "completed", "start_time": _now().isoformat()},
        ]
        with _patch_scheduler(fake_scheduler):
            result = _is_task_running("news")
        self.assertFalse(result)


class TestTriggerTaskPersistsCronStatus(unittest.TestCase):
    """问题一：_trigger_task 在触发和失败时都应写 cron_job_status。"""

    @patch("core.scheduler.cron._persist_cron_status")
    @patch("core.scheduler.cron._is_task_running", return_value=False)
    @patch("core.scheduler.cron._record_result")
    def test_trigger_success_persists_status(self, mock_record, mock_running, mock_persist):
        fake_scheduler = MagicMock()
        fake_scheduler.create_task.return_value = "news_12345"
        with patch.dict("sys.modules", {"core.scheduler.scheduler": MagicMock(scheduler=fake_scheduler)}):
            from core.scheduler.cron import _trigger_task
            _trigger_task("news", {"max_pages": 5}, "新闻增量")
        mock_persist.assert_called_once()
        args = mock_persist.call_args[0]
        self.assertEqual(args[0], "news")
        self.assertIsNone(args[2])

    @patch("core.scheduler.cron._persist_cron_status")
    @patch("core.scheduler.cron._is_task_running", return_value=False)
    @patch("core.scheduler.cron._record_result")
    def test_trigger_failure_persists_status(self, mock_record, mock_running, mock_persist):
        fake_scheduler = MagicMock()
        fake_scheduler.create_task.side_effect = RuntimeError("db down")
        with patch.dict("sys.modules", {"core.scheduler.scheduler": MagicMock(scheduler=fake_scheduler)}):
            from core.scheduler.cron import _trigger_task
            _trigger_task("news", {}, "新闻增量")
        mock_persist.assert_called_once()
        args = mock_persist.call_args[0]
        self.assertEqual(args[0], "news")
        self.assertFalse(args[2])


class TestStartDailyJobsReloaderGuard(unittest.TestCase):
    """问题二：Flask reloader 主进程不应启动调度线程。"""

    @patch("core.scheduler.cron.threading.Thread")
    def test_reloader_main_process_skips(self, mock_thread):
        import core.scheduler.cron as cron_mod
        cron_mod._started = False
        with patch.dict("os.environ", {"FLASK_DEBUG": "true"}, clear=False):
            import os
            os.environ.pop("WERKZEUG_RUN_MAIN", None)
            cron_mod.start_daily_jobs()
        mock_thread.assert_not_called()
        cron_mod._started = False

    @patch("core.scheduler.cron._restore_next_run")
    @patch("core.scheduler.cron.threading.Thread")
    def test_reloader_child_process_starts(self, mock_thread, mock_restore):
        import core.scheduler.cron as cron_mod
        cron_mod._started = False
        with patch.dict("os.environ", {"FLASK_DEBUG": "true", "WERKZEUG_RUN_MAIN": "true"}, clear=False):
            cron_mod.start_daily_jobs()
        mock_thread.assert_called_once()
        cron_mod._started = False


class TestRestoreNextRunSkipsStale(unittest.TestCase):
    """问题五：_restore_next_run 应跳过已过期的 next_run 值。"""

    def test_past_next_run_recalculated(self):
        import core.scheduler.cron as cron_mod

        past_time = (_now() - datetime.timedelta(hours=3)).isoformat()
        future_time = (_now() + datetime.timedelta(hours=1)).isoformat()

        mock_col = MagicMock()
        mock_col.find.return_value = [
            {"label": "新闻增量 整点", "next_run": past_time},
            {"label": "K线增量 16:05", "next_run": future_time},
        ]

        test_jobs = [
            {"label": "新闻增量 整点", "kind": "hourly", "hour": 0, "minute": 0,
             "next_run": _now()},
            {"label": "K线增量 16:05", "kind": "daily", "hour": 16, "minute": 5,
             "next_run": _now()},
        ]

        with patch.object(cron_mod, "_registered_jobs", test_jobs):
            with patch.object(cron_mod, "_get_cron_collection", return_value=mock_col):
                cron_mod._restore_next_run()

        self.assertGreater(test_jobs[0]["next_run"], _now())
        expected_future = datetime.datetime.fromisoformat(future_time)
        self.assertEqual(test_jobs[1]["next_run"], expected_future)


class TestOnTaskDoneHandlesAllTerminalStates(unittest.TestCase):
    """问题一/三：_on_task_done 应处理 COMPLETED/FAILED/CANCELLED 三种终态。"""

    def test_completed_with_zero_news(self):
        from core.scheduler.scheduler import TaskScheduler, TaskStatus
        from core.storage.mongo_storage import TaskStorage

        sched = TaskScheduler()
        mock_storage = MagicMock(spec=TaskStorage)

        from core.scheduler.scheduler import Task
        task = Task("news_test", "news", {}, mock_storage)
        task.status = TaskStatus.COMPLETED
        task.success = 0
        task.failed = 0
        task.end_time = _now()

        with sched._lock:
            sched._tasks["news_test"] = task

        mock_future = MagicMock()
        mock_future.exception.return_value = None

        with patch("core.scheduler.cron._persist_cron_status") as mock_persist:
            sched._on_task_done("news_test", mock_future)
            mock_persist.assert_called_once()
            args = mock_persist.call_args[0]
            self.assertTrue(args[2])
            self.assertIn("暂无新闻", args[3])

    def test_cancelled_task_persists(self):
        from core.scheduler.scheduler import TaskScheduler, TaskStatus
        from core.storage.mongo_storage import TaskStorage

        sched = TaskScheduler()
        mock_storage = MagicMock(spec=TaskStorage)

        from core.scheduler.scheduler import Task
        task = Task("news_cancel", "news", {}, mock_storage)
        task.status = TaskStatus.CANCELLED
        task.end_time = _now()

        with sched._lock:
            sched._tasks["news_cancel"] = task

        mock_future = MagicMock()
        mock_future.exception.return_value = None

        with patch("core.scheduler.cron._persist_cron_status") as mock_persist:
            sched._on_task_done("news_cancel", mock_future)
            mock_persist.assert_called_once()
            args = mock_persist.call_args[0]
            self.assertIsNone(args[2])
            self.assertIn("取消", args[3])


class TestPersistScheduleUpsert(unittest.TestCase):
    """问题二：_persist_schedule 应使用 upsert 而非 delete+insert。"""

    def test_uses_replace_one_upsert(self):
        import core.scheduler.cron as cron_mod

        mock_col = MagicMock()
        test_jobs = [
            {"label": "新闻增量 整点", "kind": "hourly", "hour": 0, "minute": 0,
             "next_run": _now(), "task_type": "news"},
        ]

        with patch.object(cron_mod, "_registered_jobs", test_jobs):
            with patch.object(cron_mod, "_get_cron_collection", return_value=mock_col):
                cron_mod._persist_schedule()

        mock_col.replace_one.assert_called_once()
        call_args = mock_col.replace_one.call_args
        self.assertEqual(call_args[0][0], {"label": "新闻增量 整点"})
        self.assertTrue(call_args[1].get("upsert"))
        mock_col.delete_many.assert_not_called()
        mock_col.insert_many.assert_not_called()


if __name__ == "__main__":
    unittest.main()
