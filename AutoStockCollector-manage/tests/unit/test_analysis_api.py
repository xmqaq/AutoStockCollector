"""分析 API 路由测试：mock AnalysisEngine，用 Flask test client。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAnalysisAPI(unittest.TestCase):
    def setUp(self):
        from api import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_analysis_endpoint_returns_engine_result(self):
        fake_result = {
            "code": "SH600519", "name": "贵州茅台",
            "scores": {"composite": 72.0}, "source": "llm",
            "llm": {"summary": "稳健"}, "disclaimer": "仅供参考",
        }
        with patch("api.routes.AnalysisEngine") as MockEngine:
            MockEngine.return_value.analyze.return_value = fake_result
            resp = self.client.get("/api/v1/ai/stock/600519/analysis")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["code"], "SH600519")

    def test_analysis_endpoint_handles_engine_error(self):
        with patch("api.routes.AnalysisEngine") as MockEngine:
            MockEngine.return_value.analyze.side_effect = RuntimeError("boom")
            resp = self.client.get("/api/v1/ai/stock/600519/analysis")
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(resp.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
