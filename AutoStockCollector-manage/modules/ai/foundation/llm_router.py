"""统一 LLM 路由：适配器选择(按优先级) + schema 约束 + 降级链 + 缓存 + 调用历史。

caller 边界：(provider, prompt) -> str。默认实现接 model_manager 适配器（能力层期接入）；
测试注入假 caller。
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LLMResult:
    success: bool
    provider: str = ""
    data: Optional[Dict[str, Any]] = None
    raw: str = ""
    from_cache: bool = False
    error: str = ""


class LLMRouter:
    def __init__(
        self,
        providers: Optional[List[str]] = None,
        caller: Optional[Callable[[str, str], str]] = None,
        cache_ttl_hours: int = 6,
    ):
        self.providers = providers or self._load_providers_from_keys()
        self.caller = caller or self._default_caller
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)

    def _load_providers_from_keys(self) -> List[str]:
        """从 ai_keys 读 enabled 的 provider，按 priority 升序。失败返回空。"""
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            docs = db["ai_keys"].find({"enabled": True}).sort("priority", 1)
            return [d["provider"] for d in docs if d.get("provider")]
        except Exception:
            return []

    def _default_caller(self, provider: str, prompt: str,
                        messages: Optional[List[Dict[str, Any]]] = None) -> str:
        """读 ai_keys 配置，经 ProviderCaller 调用对应厂商。

        传入 messages 时按多轮对话格式发送（携带历史上下文），否则按单条 prompt。
        """
        from modules.ai.foundation.llm_caller import ProviderCaller
        if not hasattr(self, "_provider_caller"):
            self._provider_caller = ProviderCaller()
        return self._provider_caller(provider, prompt, messages=messages)

    def _caller_accepts_messages(self) -> bool:
        """检测注入/默认 caller 是否支持 messages 参数（缓存结果）。

        测试里注入的 2 参 caller(provider, prompt) 不支持，走单 prompt 路径，保持兼容。
        """
        if not hasattr(self, "_caller_msgs_ok"):
            import inspect
            try:
                params = inspect.signature(self.caller).parameters.values()
                self._caller_msgs_ok = any(
                    p.name == "messages" or p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in params
                )
            except (TypeError, ValueError):
                self._caller_msgs_ok = False
        return self._caller_msgs_ok

    def _build_prompt(self, prompt: str, schema: Optional[Dict[str, Any]]) -> str:
        if not schema:
            return prompt
        keys = ", ".join(schema.keys())
        return f"{prompt}\n\n请严格输出 JSON，且必须包含字段：{keys}。只返回 JSON，不要其他文字。"

    def _cache_key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()

    def chat(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        task_type: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResult:
        """调用 LLM。传入 messages 时以多轮对话格式发送，跳过缓存（对话有上下文，不宜缓存）。"""
        full_prompt = self._build_prompt(prompt, schema)
        use_cache = use_cache and not messages
        key = self._cache_key(full_prompt)

        if use_cache and key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["ts"] < self._cache_ttl:
                return LLMResult(
                    success=True, provider=entry["provider"],
                    data=entry["data"], raw=entry["raw"], from_cache=True,
                )

        last_error = ""
        send_messages = messages if (messages and self._caller_accepts_messages()) else None
        for provider in self.providers:
            try:
                if send_messages is not None:
                    raw = self.caller(provider, full_prompt, messages=send_messages)
                else:
                    raw = self.caller(provider, full_prompt)
                if schema:
                    data = self._parse_json(raw)
                    if data is None:
                        last_error = "non-json response"
                        continue
                else:
                    data = {"content": raw}
                self._log_history(provider, task_type, True)
                if use_cache:
                    self._cache[key] = {
                        "provider": provider, "data": data,
                        "raw": raw, "ts": datetime.now(),
                    }
                return LLMResult(success=True, provider=provider, data=data, raw=raw)
            except Exception as e:
                last_error = str(e)
                self._log_history(provider, task_type, False, str(e))
                continue

        return LLMResult(success=False, error=last_error or "all providers failed")

    def _parse_json(self, raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        text = raw.strip()

        # 剥离 ```json ... ``` 围栏
        if "```" in text:
            import re
            m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
            if m:
                text = m.group(1).strip()

        # 直接解析
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except (ValueError, TypeError):
            pass

        # LLM 在 JSON 前后加了说明文字：提取第一个 {...}
        import re
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                parsed = json.loads(m.group())
                return parsed if isinstance(parsed, dict) else None
            except (ValueError, TypeError):
                pass

        return None

    def _log_history(self, provider: str, task_type: str, success: bool, error: str = ""):
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            db["ai_call_history"].insert_one({
                "provider": provider, "task_type": task_type,
                "success": success, "error": error,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass

    def chat_stream(self, prompt: str, schema: Optional[Dict[str, Any]] = None,
                    use_cache: bool = False, task_type: str = "general",
                    messages: Optional[List[Dict[str, Any]]] = None):
        """流式调用，返回生成器。传入 messages 时用多轮对话格式。"""
        full_prompt = self._build_prompt(prompt, schema)

        for provider in self.providers:
            try:
                from modules.ai.foundation.llm_caller import ProviderCaller
                caller = ProviderCaller()
                chunks = caller.stream_call(provider, full_prompt, messages=messages)

                for chunk in chunks:
                    if chunk:
                        yield chunk

                self._log_history(provider, task_type, True)
                return

            except Exception as e:
                self._log_history(provider, task_type, False, str(e))
                continue

        yield from []
