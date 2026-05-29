"""内容风控过滤器纯函数测试（无 DB / 无网络）"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.content_risk import sanitize_text, RISK_DISCLAIMER


class TestSanitizeText(unittest.TestCase):
    def test_replaces_absolute_terms(self):
        text, hits = sanitize_text("该股必涨，保证收益，建议全仓买入")
        self.assertNotIn("必涨", text)
        self.assertNotIn("保证收益", text)
        self.assertNotIn("全仓", text)
        self.assertIn("必涨", hits)
        self.assertIn("保证收益", hits)
        self.assertIn("全仓", hits)

    def test_clean_text_unchanged(self):
        original = "技术面偏强，可关注回调机会，注意控制仓位"
        text, hits = sanitize_text(original)
        self.assertEqual(text, original)
        self.assertEqual(hits, [])

    def test_empty_input(self):
        text, hits = sanitize_text("")
        self.assertEqual(text, "")
        self.assertEqual(hits, [])

    def test_none_input_safe(self):
        text, hits = sanitize_text(None)
        self.assertEqual(text, "")
        self.assertEqual(hits, [])

    def test_disclaimer_is_nonempty_string(self):
        self.assertIsInstance(RISK_DISCLAIMER, str)
        self.assertIn("参考", RISK_DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
