"""advice / pick API 路由测试：mock 引擎，Flask test client。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAdvicePickerAPI(unittest.TestCase):
    def setUp(self):
        from api import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_advice_endpoint(self):
        fake = {"code": "SH600519", "advice": {"action": "关注"}, "source": "llm", "disclaimer": "仅供参考"}
        with patch("api.routes.AdviceEngine") as MockEng:
            MockEng.return_value.advise.return_value = fake
            resp = self.client.post("/api/v1/ai/stock/600519/advice", json={"cost": 18.0, "position": 0.3})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["advice"]["action"], "关注")

    def test_advice_passes_position_args(self):
        with patch("api.routes.AdviceEngine") as MockEng:
            MockEng.return_value.advise.return_value = {"code": "SH600519"}
            self.client.post("/api/v1/ai/stock/600519/advice", json={"cost": 18.0, "position": 0.3})
            _, kwargs = MockEng.return_value.advise.call_args
            self.assertEqual(kwargs.get("cost"), 18.0)
            self.assertEqual(kwargs.get("position"), 0.3)

    def test_pick_run_endpoint(self):
        fake = {"strategy": "default", "picks": [{"code": "A", "composite": 85}], "timestamp": "t"}
        with patch("api.routes.PickerEngine") as MockEng:
            MockEng.return_value.run.return_value = fake
            resp = self.client.post("/api/v1/ai/pick/run", json={"top_n": 5, "candidate_pool": 20})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        self.assertEqual(len(resp.get_json()["data"]["picks"]), 1)

    def test_pick_results_reads_latest(self):
        fake_doc = {"strategy": "default", "picks": [], "timestamp": "t"}
        with patch("api.routes._latest_pick_result", return_value=fake_doc):
            resp = self.client.get("/api/v1/ai/pick/results")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    def test_pick_results_empty(self):
        with patch("api.routes._latest_pick_result", return_value=None):
            resp = self.client.get("/api/v1/ai/pick/results")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.get_json()["data"])


if __name__ == "__main__":
    unittest.main()
