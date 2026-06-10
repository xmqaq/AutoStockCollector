"""
待办事项 API 单元测试
"""
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask
from api.routes.todo import todo_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(todo_bp)
    return app


def _fake_doc(i=0, category="todo", done=False):
    return {
        "_id": f"oid{i}",
        "id": f"id-{i}",
        "text": f"item {i}",
        "category": category,
        "done": done,
        "createdAt": "2026-06-10 09:00:00",
        "updatedAt": "2026-06-10 09:00:00",
        "submitterIp": "10.0.0.1",
    }


class TestGetClientIp(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()

    def test_uses_x_forwarded_for_first(self):
        with self.app.test_request_context(
            headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        ):
            from api.routes.todo import _get_client_ip
            self.assertEqual(_get_client_ip(), "1.2.3.4")

    def test_falls_back_to_remote_addr(self):
        with self.app.test_request_context(
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"}
        ):
            from api.routes.todo import _get_client_ip
            result = _get_client_ip()
            self.assertEqual(result, "127.0.0.1")


class TestListTodos(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.client = self.app.test_client()

    @patch("api.routes.todo._get_db")
    def test_returns_pagination_metadata(self, mock_get_db):
        mock_col = MagicMock()
        mock_get_db.return_value = {"todo": mock_col}
        # count_documents called 2 times (query={} path): filtered(reused as global), global_done
        mock_col.count_documents.side_effect = [25, 10]
        mock_col.find.return_value = iter([_fake_doc(i) for i in range(20)])

        resp = self.client.get("/api/v1/todo?page=1&pageSize=20")
        data = resp.get_json()

        self.assertTrue(data["success"])
        self.assertEqual(data["pagination"]["total"], 25)
        self.assertEqual(data["pagination"]["page"], 1)
        self.assertEqual(data["pagination"]["pageSize"], 20)
        self.assertEqual(len(data["data"]), 20)

    @patch("api.routes.todo._get_db")
    def test_stats_are_global_not_filtered(self, mock_get_db):
        mock_col = MagicMock()
        mock_get_db.return_value = {"todo": mock_col}
        # category=plan filter: 5 matched; global: 25 total, 10 done
        mock_col.count_documents.side_effect = [5, 25, 10]
        mock_col.find.return_value = iter([_fake_doc(i, category="plan") for i in range(5)])

        resp = self.client.get("/api/v1/todo?category=plan&page=1&pageSize=20")
        data = resp.get_json()

        self.assertEqual(data["pagination"]["total"], 5)   # filtered
        self.assertEqual(data["stats"]["total"], 25)       # global
        self.assertEqual(data["stats"]["done"], 10)        # global
        self.assertEqual(data["stats"]["pending"], 15)     # global

    @patch("api.routes.todo._get_db")
    def test_skip_calculated_correctly(self, mock_get_db):
        mock_col = MagicMock()
        mock_get_db.return_value = {"todo": mock_col}
        mock_col.count_documents.side_effect = [50, 5]
        mock_col.find.return_value = iter([_fake_doc(i) for i in range(20)])

        self.client.get("/api/v1/todo?page=3&pageSize=10")

        call_kwargs = mock_col.find.call_args
        skip_val = call_kwargs.kwargs.get("skip", call_kwargs[1].get("skip"))
        limit_val = call_kwargs.kwargs.get("limit", call_kwargs[1].get("limit"))
        self.assertIsNotNone(skip_val, "find() was not called with a 'skip' keyword argument")
        self.assertIsNotNone(limit_val, "find() was not called with a 'limit' keyword argument")
        self.assertEqual(skip_val, 20)
        self.assertEqual(limit_val, 10)

    @patch("api.routes.todo._get_db")
    def test_invalid_category_treated_as_all(self, mock_get_db):
        mock_col = MagicMock()
        mock_get_db.return_value = {"todo": mock_col}
        # query={} path: filtered_total reused as global_total (2 count calls, not 3)
        mock_col.count_documents.side_effect = [30, 5]  # filtered=30(reused as global), global_done=5
        mock_col.find.return_value = iter([_fake_doc(i) for i in range(20)])

        resp = self.client.get("/api/v1/todo?category=invalid_value")
        data = resp.get_json()

        self.assertTrue(data["success"])
        self.assertEqual(data["stats"]["total"], 30)   # same as filtered (query={})
        self.assertEqual(data["stats"]["done"], 5)
        self.assertEqual(data["stats"]["pending"], 25)
        self.assertEqual(data["pagination"]["total"], 30)


class TestCreateTodoIp(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.client = self.app.test_client()

    @patch("api.routes.todo._get_db")
    def test_stores_submitter_ip(self, mock_get_db):
        mock_col = MagicMock()
        mock_get_db.return_value = {"todo": mock_col}

        inserted = {}

        def capture_insert(doc):
            inserted.update(doc)

        mock_col.insert_one.side_effect = capture_insert

        resp = self.client.post(
            "/api/v1/todo",
            json={"text": "test item", "category": "todo"},
            headers={"X-Forwarded-For": "9.9.9.9"},
        )

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(inserted.get("submitterIp"), "9.9.9.9")
        self.assertEqual(resp.get_json()["data"]["submitterIp"], "9.9.9.9")


if __name__ == "__main__":
    unittest.main()
