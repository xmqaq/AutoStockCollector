"""fusion 连续入选(consecutive_days)口径测试：quick 盘中快照不得污染 prev。

背景：quick 和 daily 都写 fusion_pick_results，按 created_at 排序。若 _latest_fusion_runs
不过滤 mode，盘中 quick 快照会被当成"上一轮 daily"参与 consecutive_days 计算，导致
连选口径失真。修后 _latest_fusion_runs 只取 mode=="full" 的 run。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.monitor.lifecycle import MonitorLifecycle


def _run(run_id, codes, mode, created_at):
    """构造一条 fusion_pick_results 文档。"""
    return {
        "run_id": run_id,
        "mode": mode,
        "created_at": created_at,
        "picks": [{"code": c, "name": c} for c in codes],
    }


class TestLatestFusionRunsModeFilter(unittest.TestCase):
    """_latest_fusion_runs 只返回 mode==full 的 run，quick 不参与。"""

    def _lifecycle_with_runs(self, runs_in_db):
        """mock db.find 真正按查询条件过滤 mode。"""
        lc = MonitorLifecycle.__new__(MonitorLifecycle)  # 跳过 __init__ 连 DB
        lc.db = MagicMock()

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs
            def sort(self, *_a, **_k):
                return self
            def limit(self, n):
                return self._docs[:n]

        def _find(query, *_a, **_k):
            mode = query.get("mode")
            docs = [r for r in runs_in_db if mode is None or r.get("mode") == mode]
            return _Cursor(docs)
        lc.db["fusion_pick_results"].find.side_effect = _find
        return lc

    def test_quick_excluded_from_latest_runs(self):
        """DB 里有 [daily-full, quick, daily-full]（按时间倒序），只应取回 2 条 full。"""
        runs = [
            _run("d2", ["SH1"], "full", "2026-07-01T16:20:00"),    # 最新 daily
            _run("q1", ["SH2"], "quick", "2026-07-01T10:30:00"),   # 盘中 quick
            _run("d1", ["SH1"], "full", "2026-06-30T16:20:00"),    # 上一 daily
        ]
        lc = self._lifecycle_with_runs(runs)
        result = lc._latest_fusion_runs(2)
        modes = [r.get("mode") for r in result]
        self.assertEqual(modes, ["full", "full"], f"quick 不应出现, got {modes}")
        # 关键：prev 是 d1(SH1) 而非 q1(SH2)
        self.assertEqual(result[0]["run_id"], "d2")
        self.assertEqual(result[1]["run_id"], "d1")

    def test_find_query_includes_mode_full(self):
        """查询条件必须带 mode:'full' 过滤。"""
        lc = self._lifecycle_with_runs([])
        lc._latest_fusion_runs(2)
        query = lc.db["fusion_pick_results"].find.call_args[0][0]
        self.assertEqual(query, {"mode": "full"},
                         f"查询应过滤 mode==full, got {query}")


class TestConsecutiveDaysUnpollutedByQuick(unittest.TestCase):
    """端到端：quick 夹在两个 daily 之间，consecutive_days 应按 daily-daily 连续性算。"""

    def _lifecycle(self, runs_in_db, signals_docs):
        lc = MonitorLifecycle.__new__(MonitorLifecycle)
        lc.db = MagicMock()

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs
            def sort(self, *_a, **_k):
                return self
            def limit(self, n):
                return self._docs[:n]

        def _find(query, *_a, **_k):
            mode = query.get("mode")
            docs = [r for r in runs_in_db if mode is None or r.get("mode") == mode]
            return _Cursor(docs)
        lc.db["fusion_pick_results"].find.side_effect = _find

        signals_by_code = {d["code"]: d for d in signals_docs}
        lc.db["monitor_signals"].find_one.side_effect = \
            lambda q, *a, **k: signals_by_code.get(q.get("code"))
        lc.db["monitor_signals"].update_one.return_value = MagicMock()
        return lc

    def test_quick_between_dailies_does_not_break_streak(self):
        """SH1 在 d1 和 d2 两个 daily 都入选，中间夹个 q1(quick, 不含SH1)。
        修前：prev=q1 不含 SH1 → consec 重置为 1（错误打断连选）。
        修后：prev=d1 含 SH1 → consec=旧+1=2（正确延续）。
        """
        runs = [
            _run("d2", ["SH1"], "full", "2026-07-01T16:20:00"),
            _run("q1", ["SH2"], "quick", "2026-07-01T10:30:00"),
            _run("d1", ["SH1"], "full", "2026-06-30T16:20:00"),
        ]
        # SH1 已有文档：上次 d1 入选过，consecutive_days=1，last_fusion_run_id=d1
        existing = {
            "code": "SH1", "consecutive_days": 1,
            "last_fusion_run_id": "d1", "sources": ["fusion_pick"],
            "first_selected_at": "2026-06-30T16:20:00",
        }
        lc = self._lifecycle(runs, [existing])
        from datetime import datetime
        fake_now = datetime.fromisoformat("2026-07-01T16:20:00")
        with patch("modules.monitor.lifecycle.beijing_now", return_value=fake_now):
            res = lc.sync_fusion_pick_tracking("default")

        # SH1 应更新为 consecutive_days=2（d1→d2 连续），而非被 q1 打断成 1
        update_call = lc.db["monitor_signals"].update_one.call_args
        update_doc = update_call[0][1]  # (filter, update) 的第二个位置参数
        set_fields = update_doc["$set"]
        self.assertEqual(set_fields["consecutive_days"], 2,
                         f"SH1 连续两轮 daily 入选应=2, got {set_fields['consecutive_days']}")
        self.assertEqual(res["run_id"], "d2")

    def test_quick_only_no_streak_inflation(self):
        """DB 里只有 quick run（没有 daily full）时，sync 应返回 no_fusion_data，不误算。"""
        runs = [_run("q1", ["SH2"], "quick", "2026-07-01T10:30:00")]
        lc = self._lifecycle(runs, [])
        res = lc.sync_fusion_pick_tracking("default")
        self.assertTrue(res.get("no_fusion_data"),
                         "无 daily full run 时不应算连续入选")


if __name__ == "__main__":
    unittest.main()
