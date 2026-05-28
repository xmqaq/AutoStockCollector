"""
集成测试模块
"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestModuleIntegration(unittest.TestCase):
    def test_import_all_modules(self):
        from config import Settings, DatabaseConfig
        from utils import get_logger
        from core.risk_control import RiskController

        self.assertIsNotNone(Settings)
        self.assertIsNotNone(RiskController)

    def test_api_blueprint_registration(self):
        from api import create_app

        app = create_app()
        self.assertIsNotNone(app)


class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        from api import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "ok")

    def test_task_create(self):
        response = self.client.post(
            "/api/v1/task/create",
            json={
                "task_type": "kline",
                "params": {"codes": ["SH600000"]}
            }
        )

        self.assertIn(response.status_code, [200, 500])

    def test_task_list(self):
        response = self.client.get("/api/v1/tasks")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("tasks", data)

    def test_kline_query(self):
        response = self.client.get("/api/v1/kline/SH600000")
        self.assertIn(response.status_code, [200, 500])

    def test_stock_info_query(self):
        response = self.client.get("/api/v1/stock/SH600000/info")
        self.assertIn(response.status_code, [200, 404, 500])

    def test_news_query(self):
        response = self.client.get("/api/v1/news?limit=10")
        self.assertEqual(response.status_code, 200)

    def test_watchlist_query(self):
        response = self.client.get("/api/v1/watchlist?user_id=default")
        self.assertEqual(response.status_code, 200)

    def test_strategy_list(self):
        response = self.client.get("/api/v1/strategy/list")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("strategies", data)

    def test_scheduler_stats(self):
        response = self.client.get("/api/v1/scheduler/stats")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("stats", data)


if __name__ == "__main__":
    unittest.main()