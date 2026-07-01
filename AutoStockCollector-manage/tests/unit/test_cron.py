"""定时调度测试：直接调 job 函数验证 create+start，不起线程/不等时间。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.scheduler.cron import (
    job_kline_gap_backfill, job_task_cleanup,
    job_portfolio_snapshot,
)


class TestTaskCleanup(unittest.TestCase):
    """任务历史自动清理：只删7天前的已结束任务，运行中/排队的不动。"""

    def test_deletes_only_finished_old_tasks(self):
        coll = MagicMock()
        coll.delete_many.return_value = MagicMock(deleted_count=120)
        db = MagicMock()
        db.__getitem__.side_effect = lambda n: coll
        with patch("config.database.DatabaseConfig.get_database", return_value=db):
            job_task_cleanup()
        coll.delete_many.assert_called_once()
        query = coll.delete_many.call_args[0][0]
        self.assertEqual(set(query["status"]["$in"]),
                         {"completed", "failed", "cancelled"})
        self.assertIn("$lt", query["create_time"])

    def test_swallows_errors(self):
        with patch("config.database.DatabaseConfig.get_database",
                   side_effect=RuntimeError("db down")):
            job_task_cleanup()  # 不应抛出


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


class TestPortfolioSnapshot(unittest.TestCase):
    """净值快照：遍历所有有账户的 user_id 各记一次，单用户失败不影响其他。"""

    def _run(self, uids, fail_uid=None):
        acc = MagicMock()
        acc._col.distinct.return_value = uids
        snap = MagicMock()
        if fail_uid:
            snap.record.side_effect = lambda uid, *a: (_ for _ in ()).throw(RuntimeError("boom")) if uid == fail_uid else None
        with patch("modules.paper_trading.account.PaperAccount", return_value=acc), \
             patch("modules.paper_trading.trade_engine.TradeEngine", return_value=MagicMock()), \
             patch("modules.paper_trading.snapshot.PortfolioSnapshot", return_value=snap), \
             patch("core.scheduler.cron._is_weekday", return_value=True), \
             patch("core.scheduler.cron._record_result"), \
             patch("core.scheduler.cron._persist_cron_status"):
            job_portfolio_snapshot()
        return snap

    def test_records_every_user(self):
        snap = self._run(["default", "u1", "u2"])
        self.assertEqual(snap.record.call_count, 3)

    def test_one_user_failure_does_not_abort_others(self):
        snap = self._run(["default", "u1", "u2"], fail_uid="u1")
        self.assertEqual(snap.record.call_count, 3)  # 仍尝试了全部用户


if __name__ == "__main__":
    unittest.main()
