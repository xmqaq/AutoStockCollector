"""ai_pick 任务执行器测试：mock PickerEngine + Task，不连 DB/不发 LLM。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.scheduler.enums import TaskType


class TestAiPickTaskType(unittest.TestCase):
    def test_ai_pick_enum_exists(self):
        self.assertEqual(TaskType.AI_PICK.value, "ai_pick")


class TestExecuteAiPickTask(unittest.TestCase):
    def _task(self, params=None):
        t = MagicMock()
        t.params = params or {}
        return t

    def test_runs_picker_and_completes(self):
        from core.scheduler.scheduler import scheduler
        task = self._task({"top_n": 5, "candidate_pool": 20, "strategy": "default"})
        with patch("modules.ai.engines.picker.PickerEngine") as MockPicker:
            MockPicker.return_value.run.return_value = {"picks": [{"code": "A"}, {"code": "B"}]}
            scheduler._execute_ai_pick_task(task)
            _, kwargs = MockPicker.return_value.run.call_args
            self.assertEqual(kwargs.get("top_n"), 5)
            self.assertEqual(kwargs.get("candidate_pool"), 20)
        task.complete.assert_called_once()
        task.fail.assert_not_called()

    def test_failure_marks_task_failed(self):
        from core.scheduler.scheduler import scheduler
        task = self._task({})
        with patch("modules.ai.engines.picker.PickerEngine") as MockPicker:
            MockPicker.return_value.run.side_effect = RuntimeError("boom")
            scheduler._execute_ai_pick_task(task)
        task.fail.assert_called_once()


if __name__ == "__main__":
    unittest.main()
