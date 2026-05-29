"""Provider caller 测试：注入假 key-loader 和假 http poster，不连 DB / 不发真实请求。"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.llm_caller import ProviderCaller


class TestProviderCaller(unittest.TestCase):
    def _key_loader(self, doc):
        return lambda provider: doc

    def test_openai_compatible_call(self):
        captured = {}

        def poster(method, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return {"choices": [{"message": {"content": "结果文本"}}]}

        caller = ProviderCaller(
            key_loader=self._key_loader({"api_key": "sk-x", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}),
            poster=poster,
        )
        out = caller("deepseek", "分析一下")
        self.assertEqual(out, "结果文本")
        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["json"]["model"], "deepseek-chat")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-x")

    def test_anthropic_call_uses_messages_endpoint(self):
        captured = {}

        def poster(method, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            return {"content": [{"text": "claude 回复"}]}

        caller = ProviderCaller(
            key_loader=self._key_loader({"api_key": "sk-ant", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-5"}),
            poster=poster,
        )
        out = caller("anthropic", "分析")
        self.assertEqual(out, "claude 回复")
        self.assertTrue(captured["url"].endswith("/v1/messages"))
        self.assertEqual(captured["headers"]["x-api-key"], "sk-ant")

    def test_gemini_call_uses_generatecontent(self):
        captured = {}

        def poster(method, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            return {"candidates": [{"content": {"parts": [{"text": "gemini 回复"}]}}]}

        caller = ProviderCaller(
            key_loader=self._key_loader({"api_key": "g-key", "base_url": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-2.0-flash"}),
            poster=poster,
        )
        out = caller("gemini", "分析")
        self.assertEqual(out, "gemini 回复")
        self.assertIn("generateContent", captured["url"])
        self.assertIn("key=g-key", captured["url"])

    def test_missing_key_raises(self):
        caller = ProviderCaller(key_loader=self._key_loader(None), poster=lambda *a, **k: {})
        with self.assertRaises(ValueError):
            caller("deepseek", "x")

    def test_no_api_key_raises(self):
        caller = ProviderCaller(
            key_loader=self._key_loader({"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}),
            poster=lambda *a, **k: {},
        )
        with self.assertRaises(ValueError):
            caller("deepseek", "x")

    def test_model_fallback_when_not_configured(self):
        captured = {}

        def poster(method, url, headers=None, json=None, timeout=None):
            captured["json"] = json
            return {"choices": [{"message": {"content": "ok"}}]}

        caller = ProviderCaller(
            key_loader=self._key_loader({"api_key": "sk-x", "base_url": "https://api.deepseek.com/v1", "model": ""}),
            poster=poster,
        )
        caller("deepseek", "x")
        self.assertEqual(captured["json"]["model"], "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
