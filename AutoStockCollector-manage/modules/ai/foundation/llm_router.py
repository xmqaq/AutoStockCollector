"""统一 LLM 路由：适配器选择(按优先级) + schema 约束 + 降级链 + 缓存 + 调用历史。

caller 边界：(provider, prompt) -> str。默认实现接 model_manager 适配器（能力层期接入）；
测试注入假 caller。
"""
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from typing import Any, Callable, Dict, List, Optional

# ai_call_history 是只增不查→现在已有查询页的审计日志，需要索引 + TTL，否则会无限增长、
# 且分页/聚合查询全表扫描越来越慢。索引创建是幂等的，用进程级标记保证只建一次。
_AI_HISTORY_INDEXES_READY = False


def ensure_ai_call_history_indexes(db) -> None:
    """为 ai_call_history 建立 timestamp TTL 索引 + 过滤索引（幂等，进程内仅执行一次）。

    TTL 天数可用环境变量 AI_CALL_HISTORY_TTL_DAYS 配置（默认 90 天，<=0 关闭过期）。
    注意：TTL 只会删除 timestamp 为 BSON 日期类型的文档，历史遗留的 ISO 字符串记录
    不会被自动清理。
    """
    global _AI_HISTORY_INDEXES_READY
    if _AI_HISTORY_INDEXES_READY:
        return
    try:
        coll = db["ai_call_history"]
        try:
            ttl_days = int(os.environ.get("AI_CALL_HISTORY_TTL_DAYS", "90"))
        except (TypeError, ValueError):
            ttl_days = 90
        if ttl_days > 0:
            coll.create_index([("timestamp", 1)], name="ttl_timestamp",
                              expireAfterSeconds=ttl_days * 86400)
        else:
            coll.create_index([("timestamp", 1)], name="ts")
        coll.create_index([("provider", 1), ("timestamp", -1)], name="provider_ts")
        coll.create_index([("task_type", 1), ("timestamp", -1)], name="tasktype_ts")
        _AI_HISTORY_INDEXES_READY = True
    except Exception:
        # 建索引失败（权限/已存在冲突）不应阻塞写日志
        pass


@dataclass
class LLMResult:
    success: bool
    provider: str = ""
    data: Optional[Dict[str, Any]] = None
    raw: str = ""
    from_cache: bool = False
    error: str = ""


class LLMRouter:
    _RETRY_BACKOFF_SECONDS: float = 1.0  # 网络类瞬时错误重试间隔（秒），测试可置 0
    # 进程级共享缓存:深度分析等每请求新建 router,实例级缓存跨请求必 miss;
    # key 含 prompt+messages 哈希,与 provider 无关,跨实例共享安全。测试可注入 cache 隔离。
    _GLOBAL_CACHE: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        providers: Optional[List[str]] = None,
        caller: Optional[Callable[[str, str], str]] = None,
        cache_ttl_hours: int = 6,
        memory_synthesizer=None,
        cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.providers = providers or self._load_providers_from_keys()
        self.caller = caller or self._default_caller
        self._cache = cache if cache is not None else LLMRouter._GLOBAL_CACHE
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self.memory_synthesizer = memory_synthesizer

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
                        temperature: float = 0.7, max_tokens: int = 2000,
                        messages: Optional[List[Dict[str, Any]]] = None) -> str:
        """读 ai_keys 配置，经 ProviderCaller 调用对应厂商。

        传入 messages 时按多轮对话格式发送（携带历史上下文），否则按单条 prompt。
        """
        from modules.ai.foundation.llm_caller import ProviderCaller
        if not hasattr(self, "_provider_caller"):
            self._provider_caller = ProviderCaller()
        result = self._provider_caller(provider, prompt,
                                       temperature=temperature, max_tokens=max_tokens,
                                       messages=messages)
        self._last_model = getattr(self._provider_caller, "last_model", None)
        self._last_input_tokens = getattr(self._provider_caller, "last_input_tokens", 0)
        self._last_output_tokens = getattr(self._provider_caller, "last_output_tokens", 0)
        return result

    def _caller_accepts(self, name: str) -> bool:
        """检测 caller 是否支持某关键字参数（结果缓存）。"""
        cache = getattr(self, "_caller_param_cache", None)
        if cache is None:
            cache = self._caller_param_cache = {}
        if name not in cache:
            import inspect
            try:
                params = inspect.signature(self.caller).parameters.values()
                cache[name] = any(
                    p.name == name or p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in params
                )
            except (TypeError, ValueError):
                cache[name] = False
        return cache[name]

    def _caller_accepts_messages(self) -> bool:
        """检测注入/默认 caller 是否支持 messages 参数（缓存结果）。

        测试里注入的 2 参 caller(provider, prompt) 不支持，走单 prompt 路径，保持兼容。
        """
        return self._caller_accepts("messages")

    def _build_prompt(self, prompt: str, schema: Optional[Dict[str, Any]]) -> str:
        if not schema:
            return prompt
        keys = ", ".join(schema.keys())
        return f"{prompt}\n\n请严格输出 JSON，且必须包含字段：{keys}。只返回 JSON，不要其他文字。"

    def _cache_key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_src(full_prompt: str, messages: Optional[List[Dict[str, Any]]] = None) -> str:
        if not messages:
            return full_prompt
        return full_prompt + "\x00" + json.dumps(messages, ensure_ascii=False, sort_keys=True)

    def cache_get(self, prompt: str,
                  messages: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """读共享缓存的原始文本(供流式路径秒回),未命中/过期返回 None。"""
        key = self._cache_key(self._cache_src(prompt, messages))
        entry = self._cache.get(key)
        if entry and beijing_now() - entry["ts"] < self._cache_ttl:
            return entry["raw"]
        return None

    def cache_put(self, prompt: str, raw: str,
                  messages: Optional[List[Dict[str, Any]]] = None,
                  provider: str = "stream") -> None:
        """流式完成后回填缓存,与 chat() 同一套 key,两条路径互通。"""
        key = self._cache_key(self._cache_src(prompt, messages))
        self._cache[key] = {"provider": provider, "data": {"content": raw},
                            "raw": raw, "ts": beijing_now()}

    def _get_tier_config(self, tier: str = "quick") -> Dict[str, Any]:
        from config.settings import Settings
        tiers = getattr(Settings, "LLM_TIERS", {})
        config = tiers.get(tier, tiers.get("quick", {}))
        return {
            "temperature": config.get("temperature", 0.3),
            "max_tokens": config.get("max_tokens", 1024),
        }

    def chat_deep(self, prompt: str, **kwargs) -> LLMResult:
        tier_cfg = self._get_tier_config("deep")
        kwargs.setdefault("temperature", tier_cfg["temperature"])
        kwargs.setdefault("max_tokens", tier_cfg["max_tokens"])
        return self.chat(prompt, **kwargs)

    def chat_quick(self, prompt: str, **kwargs) -> LLMResult:
        tier_cfg = self._get_tier_config("quick")
        kwargs.setdefault("temperature", tier_cfg["temperature"])
        kwargs.setdefault("max_tokens", tier_cfg["max_tokens"])
        return self.chat(prompt, **kwargs)

    def chat_routing(self, prompt: str, **kwargs) -> LLMResult:
        tier_cfg = self._get_tier_config("routing")
        kwargs.setdefault("temperature", tier_cfg["temperature"])
        kwargs.setdefault("max_tokens", tier_cfg["max_tokens"])
        return self.chat(prompt, **kwargs)

    def _inject_memory(self, prompt: str, user_id: str = None,
                        stock_code: str = None) -> str:
        """注入用户记忆到 prompt"""
        if not self.memory_synthesizer or not user_id:
            return prompt
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            context = loop.run_until_complete(
                self.memory_synthesizer.synthesize(user_id, stock_code)
            )
            loop.close()
            if context:
                from modules.memory.prompt_injector import PromptInjector
                return PromptInjector.inject(prompt, context)
        except Exception:
            pass
        return prompt

    def chat_with_memory(
        self,
        prompt: str,
        user_id: str = None,
        stock_code: str = None,
        schema: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        task_type: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResult:
        """带用户记忆增强的 LLM 调用"""
        enhanced = self._inject_memory(prompt, user_id, stock_code)
        return self.chat(
            prompt=enhanced,
            schema=schema,
            use_cache=use_cache,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )

    def chat(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        task_type: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        messages: Optional[List[Dict[str, Any]]] = None,
        tier: Optional[str] = None,
    ) -> LLMResult:
        """调用 LLM。传入 messages 时以多轮对话格式发送；缓存 key 纳入 messages 内容，
        数据决定的 messages（如深度分析）可命中缓存；真正的多轮对话由调用方传 use_cache=False 控制。"""
        if tier:
            tier_cfg = self._get_tier_config(tier)
            temperature = tier_cfg.get("temperature", temperature)
            max_tokens = tier_cfg.get("max_tokens", max_tokens)

        full_prompt = self._build_prompt(prompt, schema)
        # 缓存 key 纳入 messages:深度分析等"数据决定的 messages"可命中缓存;
        # 真正的多轮对话由调用方传 use_cache=False 控制
        key = self._cache_key(self._cache_src(full_prompt, messages))

        if use_cache and key in self._cache:
            entry = self._cache[key]
            if beijing_now() - entry["ts"] < self._cache_ttl:
                return LLMResult(
                    success=True, provider=entry["provider"],
                    data=entry["data"], raw=entry["raw"], from_cache=True,
                )

        last_error = ""
        send_messages = messages if (messages and self._caller_accepts_messages()) else None
        call_kwargs: Dict[str, Any] = {}
        if self._caller_accepts("temperature"):
            call_kwargs["temperature"] = temperature
        if self._caller_accepts("max_tokens"):
            call_kwargs["max_tokens"] = max_tokens
        for provider in self.providers:
            raw = None
            got_response = False
            for attempt in (1, 2):
                try:
                    t0 = beijing_now()
                    if send_messages is not None:
                        raw = self.caller(provider, full_prompt, messages=send_messages, **call_kwargs)
                    else:
                        raw = self.caller(provider, full_prompt, **call_kwargs)
                    resp_time = (beijing_now() - t0).total_seconds()
                    got_response = True
                    break
                except ValueError as e:
                    last_error = str(e)
                    self._log_history(provider, task_type, False, str(e))
                    break
                except Exception as e:
                    last_error = str(e)
                    self._log_history(provider, task_type, False, str(e))
                    if attempt == 1:
                        import time
                        time.sleep(self._RETRY_BACKOFF_SECONDS)
            if not got_response:
                continue
            if schema:
                data = self._parse_json(raw)
                if data is None:
                    last_error = "non-json response"
                    continue
            else:
                data = {"content": raw}
            model_name = getattr(self, '_last_model', provider)
            input_tokens = getattr(self, '_last_input_tokens', 0)
            output_tokens = getattr(self, '_last_output_tokens', 0)
            self._log_history(provider, task_type, True, model_name=model_name,
                              input_tokens=input_tokens, output_tokens=output_tokens,
                              response_time=resp_time)
            if use_cache:
                self._cache[key] = {
                    "provider": provider, "data": data,
                    "raw": raw, "ts": beijing_now(),
                }
            return LLMResult(success=True, provider=provider, data=data, raw=raw)

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

    def _log_history(self, provider: str, task_type: str, success: bool, error: str = "",
                     model_name: str = "", input_tokens: int = 0, output_tokens: int = 0,
                     response_time: float = 0.0):
        try:
            from config.database import DatabaseConfig
            db = DatabaseConfig.get_database()
            ensure_ai_call_history_indexes(db)
            # timestamp 统一存 datetime（与 model_manager 一致）：字符串/日期混存会让
            # 排序与 $gte 范围查询按 BSON 类型分桶而非按时间，且 TTL 只对 date 字段生效。
            db["ai_call_history"].insert_one({
                "provider": provider,
                "task_type": task_type,
                "model_name": model_name,
                "success": success,
                "error": error or "",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (input_tokens or 0) + (output_tokens or 0),
                "response_time": round(response_time, 3),
                "timestamp": beijing_now(),
            })
        except Exception:
            pass

    def chat_stream(self, prompt: str, schema: Optional[Dict[str, Any]] = None,
                    use_cache: bool = False, task_type: str = "general",
                    messages: Optional[List[Dict[str, Any]]] = None):
        """流式调用，返回生成器。传入 messages 时用多轮对话格式。"""
        full_prompt = self._build_prompt(prompt, schema)

        for provider in self.providers:
            yielded = False
            try:
                from modules.ai.foundation.llm_caller import ProviderCaller
                caller = ProviderCaller()
                t0 = beijing_now()
                chunks = caller.stream_call(provider, full_prompt, messages=messages)

                for chunk in chunks:
                    if chunk:
                        yielded = True
                        yield chunk

                resp_time = (beijing_now() - t0).total_seconds()
                model_name = caller.last_model or provider
                self._log_history(provider, task_type, True,
                                  model_name=model_name,
                                  input_tokens=caller.last_input_tokens,
                                  output_tokens=caller.last_output_tokens,
                                  response_time=resp_time)
                return

            except Exception as e:
                self._log_history(provider, task_type, False, str(e))
                if yielded:
                    raise
                continue

        yield from []
