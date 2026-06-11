"""定时调度测试：直接调 job 函数验证 create+start，不起线程/不等时间。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.scheduler.cron import run_ai_pick_job, get_cron_time, job_kline_gap_backfill


class TestKlineGapBackfill(unittest.TestCase):
    """K线缺口自检：主采集被打断/数据源中途失败时，盘后自动只补缺口股票。"""

    def _fake_db(self, trading_codes, have_kline_codes):
        ff = MagicMock()
        ff.distinct.return_value = list(trading_codes)
        kl = MagicMock()
        kl.distinct.return_value = list(have_kline_codes)
        db = MagicMock()
        db.__getitem__.side_effect = lambda n: {"fund_flow": ff, "kline": kl}[n]
        return db

    def test_gap_triggers_backfill_for_missing_only(self):
        db = self._fake_db(["SH600000", "SZ300502", "SZ301377"], ["SH600000"])
        with patch("config.database.DatabaseConfig.get_database", return_value=db), \
             patch("core.scheduler.cron._is_weekday", return_value=True), \
             patch("core.scheduler.cron._trigger_task") as trig:
            job_kline_gap_backfill()
        trig.assert_called_once()
        args, _ = trig.call_args
        self.assertEqual(args[0], "kline")
        self.assertEqual(sorted(args[1]["codes"]), ["SZ300502", "SZ301377"])
        self.assertIn("start_date", args[1])

    def test_no_gap_no_trigger(self):
        db = self._fake_db(["SH600000"], ["SH600000"])
        with patch("config.database.DatabaseConfig.get_database", return_value=db), \
             patch("core.scheduler.cron._is_weekday", return_value=True), \
             patch("core.scheduler.cron._trigger_task") as trig:
            job_kline_gap_backfill()
        trig.assert_not_called()

    def test_non_trading_day_skips(self):
        """今日无资金流向记录（节假日/数据未到）不应误触发全市场回补。"""
        db = self._fake_db([], [])
        with patch("config.database.DatabaseConfig.get_database", return_value=db), \
             patch("core.scheduler.cron._is_weekday", return_value=True), \
             patch("core.scheduler.cron._trigger_task") as trig:
            job_kline_gap_backfill()
        trig.assert_not_called()

    def test_swallows_errors(self):
        with patch("config.database.DatabaseConfig.get_database", side_effect=RuntimeError("db down")), \
             patch("core.scheduler.cron._is_weekday", return_value=True):
            job_kline_gap_backfill()  # 不应抛出


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
