"""LLMRouter 测试：注入假 caller，验证降级链 / 缓存 / schema 注入，不发真实请求。"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.foundation.llm_router import LLMRouter, LLMResult


class TestLLMRouter(unittest.TestCase):
    def test_uses_first_provider_in_priority_order(self):
        calls = []

        def caller(provider, prompt):
            calls.append(provider)
            return '{"ok": true}'

        router = LLMRouter(providers=["qwen", "openai"], caller=caller)
        # 无 schema 时 raw 被包裹成 {"content": ...}（新行为：自由文本不强制 JSON）
        result = router.chat("hi", use_cache=False)
        self.assertEqual(calls, ["qwen"])
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "qwen")
        # 有 schema 时才要求 JSON 解析
        result2 = router.chat("hi2", schema={"ok": "bool"}, use_cache=False)
        self.assertEqual(result2.data, {"ok": True})

    def test_falls_back_to_next_provider_on_failure(self):
        def caller(provider, prompt):
            if provider == "qwen":
                raise RuntimeError("rate limited")
            return '{"ok": true}'

        router = LLMRouter(providers=["qwen", "openai"], caller=caller)
        result = router.chat("hi", use_cache=False)
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "openai")

    def test_all_providers_fail_returns_unsuccessful(self):
        def caller(provider, prompt):
            raise RuntimeError("down")

        router = LLMRouter(providers=["qwen", "openai"], caller=caller)
        result = router.chat("hi", use_cache=False)
        self.assertFalse(result.success)
        self.assertIsNone(result.data)

    def test_cache_hit_skips_caller(self):
        calls = []

        def caller(provider, prompt):
            calls.append(provider)
            return '{"n": 1}'

        router = LLMRouter(providers=["qwen"], caller=caller, cache={})
        r1 = router.chat("same prompt", use_cache=True)
        r2 = router.chat("same prompt", use_cache=True)
        self.assertEqual(len(calls), 1)
        self.assertTrue(r2.from_cache)
        self.assertEqual(r1.data, r2.data)

    def test_schema_injected_into_prompt(self):
        seen = {}

        def caller(provider, prompt):
            seen["prompt"] = prompt
            return '{"score": 80}'

        router = LLMRouter(providers=["qwen"], caller=caller)
        router.chat("分析", schema={"score": "int"}, use_cache=False)
        self.assertIn("score", seen["prompt"])
        self.assertIn("JSON", seen["prompt"])

    def test_non_json_response_marked_unsuccessful(self):
        def caller(provider, prompt):
            return "这不是 JSON"

        router = LLMRouter(providers=["qwen"], caller=caller)
        # 无 schema：非 JSON 也包裹成功
        result_no_schema = router.chat("hi", use_cache=False)
        self.assertTrue(result_no_schema.success)
        # 有 schema：非 JSON 解析失败→降级→全失败
        result_with_schema = router.chat("hi2", schema={"x": "int"}, use_cache=False)
        self.assertFalse(result_with_schema.success)


class TestDefaultCallerWiring(unittest.TestCase):
    def test_default_caller_delegates_to_provider_caller(self):
        from unittest.mock import patch
        router = LLMRouter(providers=["deepseek"])
        with patch("modules.ai.foundation.llm_caller.ProviderCaller") as MockPC:
            instance = MockPC.return_value
            instance.return_value = '{"ok": true}'
            # 有 schema 时才解析 JSON
            result = router.chat("hi", schema={"ok": "bool"}, use_cache=False)
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"ok": True})


class TestTemperatureMaxTokensPassthrough(unittest.TestCase):
    def test_chat_passes_temperature_and_max_tokens_to_capable_caller(self):
        captured = {}

        def caller(provider, prompt, temperature=0.7, max_tokens=2000, **kw):
            captured.update(temperature=temperature, max_tokens=max_tokens)
            return "ok"

        r = LLMRouter(providers=["p1"], caller=caller).chat(
            "hi", use_cache=False, temperature=0.4, max_tokens=4000)
        self.assertTrue(r.success)
        self.assertEqual(captured, {"temperature": 0.4, "max_tokens": 4000})

    def test_chat_keeps_compat_with_two_arg_caller(self):
        def caller(provider, prompt):
            return "ok"

        r = LLMRouter(providers=["p1"], caller=caller).chat("hi", use_cache=False, temperature=0.4)
        self.assertTrue(r.success)


class TestMessagesCache(unittest.TestCase):
    def test_chat_with_messages_caches_by_prompt_plus_messages(self):
        calls = []

        def caller(provider, prompt, messages=None, **kw):
            calls.append(1)
            return "report"

        router = LLMRouter(providers=["p1"], caller=caller, cache={})
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        r1 = router.chat("u", use_cache=True, messages=msgs)
        r2 = router.chat("u", use_cache=True, messages=msgs)
        self.assertTrue(r1.success and r2.success)
        self.assertTrue(r2.from_cache)
        self.assertEqual(len(calls), 1)
        r3 = router.chat("u", use_cache=True,
                         messages=[{"role": "user", "content": "different"}])
        self.assertFalse(r3.from_cache)
        self.assertEqual(len(calls), 2)


class TestDefaultCallerParamForwarding(unittest.TestCase):
    def test_default_caller_forwards_params_to_provider_caller(self):
        """生产路径:chat→_default_caller→ProviderCaller 参数必须透传。"""
        captured = {}

        class FakeProviderCaller:
            def __call__(self, provider, prompt, temperature=0.7, max_tokens=2000, messages=None):
                captured.update(temperature=temperature, max_tokens=max_tokens)
                return "ok"

        router = LLMRouter(providers=["p1"])          # 不注入 caller,走 _default_caller
        router._provider_caller = FakeProviderCaller() # 预置实例,绕过真实 ProviderCaller 构造
        r = router.chat("hi", use_cache=False, temperature=0.4, max_tokens=4000)
        self.assertTrue(r.success)
        self.assertEqual(captured, {"temperature": 0.4, "max_tokens": 4000})


class TestRetry(unittest.TestCase):
    def setUp(self):
        self._orig_backoff = LLMRouter._RETRY_BACKOFF_SECONDS
        LLMRouter._RETRY_BACKOFF_SECONDS = 0

    def tearDown(self):
        LLMRouter._RETRY_BACKOFF_SECONDS = self._orig_backoff

    def test_chat_retries_once_on_transient_error(self):
        attempts = []

        def flaky(provider, prompt, **kw):
            attempts.append(provider)
            if len(attempts) == 1:
                raise ConnectionError("reset by peer")
            return "ok"

        r = LLMRouter(providers=["p1"], caller=flaky).chat("hi", use_cache=False)
        self.assertTrue(r.success)
        self.assertEqual(r.provider, "p1")
        self.assertEqual(attempts, ["p1", "p1"])

    def test_chat_no_retry_on_config_error(self):
        attempts = []

        def bad(provider, prompt, **kw):
            attempts.append(provider)
            raise ValueError("未找到 provider 配置")

        r = LLMRouter(providers=["p1"], caller=bad).chat("hi", use_cache=False)
        self.assertFalse(r.success)
        self.assertEqual(attempts, ["p1"])   # ValueError 配置错误不重试


class TestSharedCache(unittest.TestCase):
    def setUp(self):
        LLMRouter._GLOBAL_CACHE.clear()

    def tearDown(self):
        LLMRouter._GLOBAL_CACHE.clear()

    def test_cache_shared_across_router_instances(self):
        """深度分析每请求新建 router,缓存必须跨实例命中。"""
        calls = []

        def caller(provider, prompt, **kw):
            calls.append(1)
            return "ok"

        r1 = LLMRouter(providers=["p1"], caller=caller).chat("shared-xyz", use_cache=True)
        r2 = LLMRouter(providers=["p1"], caller=caller).chat("shared-xyz", use_cache=True)
        self.assertFalse(r1.from_cache)
        self.assertTrue(r2.from_cache)
        self.assertEqual(len(calls), 1)

    def test_injected_cache_isolated(self):
        calls = []

        def caller(provider, prompt, **kw):
            calls.append(1)
            return "ok"

        LLMRouter(providers=["p1"], caller=caller, cache={}).chat("shared-xyz", use_cache=True)
        r2 = LLMRouter(providers=["p1"], caller=caller, cache={}).chat("shared-xyz", use_cache=True)
        self.assertFalse(r2.from_cache)
        self.assertEqual(len(calls), 2)


class TestStreamMidFailure(unittest.TestCase):
    def test_raises_after_partial_yield_no_failover_duplication(self):
        """provider 产出部分内容后失败:不许换家重播(会重复开头),应上抛让上游降级。"""
        from unittest.mock import patch

        def fake_stream(self_pc, provider, prompt, messages=None):
            if provider == "p1":
                yield "部分"
                raise ConnectionError("mid-stream broken")
            yield "完整回答"

        router = LLMRouter(providers=["p1", "p2"])
        with patch("modules.ai.foundation.llm_caller.ProviderCaller.stream_call", fake_stream):
            chunks = []
            with self.assertRaises(ConnectionError):
                for c in router.chat_stream("hi"):
                    chunks.append(c)
        self.assertEqual(chunks, ["部分"])  # 不会拼上 p2 的"完整回答"

    def test_failover_when_nothing_yielded(self):
        from unittest.mock import patch

        def fake_stream(self_pc, provider, prompt, messages=None):
            if provider == "p1":
                raise ConnectionError("connect fail")
            yield "ok"

        router = LLMRouter(providers=["p1", "p2"])
        with patch("modules.ai.foundation.llm_caller.ProviderCaller.stream_call", fake_stream):
            self.assertEqual(list(router.chat_stream("hi")), ["ok"])


if __name__ == "__main__":
    unittest.main()
