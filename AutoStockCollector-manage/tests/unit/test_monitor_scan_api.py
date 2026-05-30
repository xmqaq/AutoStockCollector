"""monitor/scan 路由测试：mock MonitorEngine，Flask test client。"""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestMonitorScanAPI(unittest.TestCase):
    def setUp(self):
        from api import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_scan_returns_created_alerts(self):
        fake = [{"id": "alert_x", "code": "SH600519", "type": "price", "ai_advice": {"action": "减仓"}}]
        with patch("api.routes.monitor.MonitorEngine") as MockEng:
            MockEng.return_value.scan.return_value = fake
            resp = self.client.post("/api/v1/monitor/scan")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["data"][0]["code"], "SH600519")

    def test_scan_passes_user_id(self):
        with patch("api.routes.monitor.MonitorEngine") as MockEng:
            MockEng.return_value.scan.return_value = []
            self.client.post("/api/v1/monitor/scan?user_id=u1")
            args, _ = MockEng.return_value.scan.call_args
            self.assertEqual(args[0], "u1")

    def test_scan_handles_error(self):
        with patch("api.routes.monitor.MonitorEngine") as MockEng:
            MockEng.return_value.scan.side_effect = RuntimeError("boom")
            resp = self.client.post("/api/v1/monitor/scan")
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(resp.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
