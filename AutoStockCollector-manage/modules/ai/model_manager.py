"""
AI模型管理模块 - 优化版
多模型调度、容错兜底、成本管控、Token统计
"""
import os
import time
import threading
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from queue import Queue, Empty
from dataclasses import dataclass, field
from collections import defaultdict
from config.settings import Settings
from config.database import get_collection
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class ModelConfig:
    name: str
    api_key: str
    base_url: str
    model_name: str
    timeout: int
    max_tokens: int
    temperature: float
    priority: int
    hourly_limit: int
    daily_limit: int
    enabled: bool
    cost_per_token: float = 0.0


@dataclass
class ModelCall:
    model_name: str
    prompt: str
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    total_tokens: int
    success: bool
    error: Optional[str]
    response_time: float
    cost: float = 0.0


@dataclass
class PromptTemplate:
    template_id: str
    name: str
    prompt_text: str
    version: int
    created_at: datetime
    description: str = ""


class BaseModelAdapter:
    def __init__(self, config: ModelConfig):
        self.config = config
        self._call_count = 0
        self._hourly_count = 0
        self._daily_count = 0
        self._hourly_tokens = 0
        self._daily_tokens = 0
        self._last_hour_reset = beijing_now()
        self._last_day_reset = beijing_now()
        self._lock = threading.Lock()

    def call(self, prompt: str) -> str:
        self._check_and_reset_counters()

        if not self._can_make_call():
            raise Exception(f"Rate limit exceeded for {self.config.name}")

        self._call_count += 1
        self._hourly_count += 1
        self._daily_count += 1

        try:
            response, input_tokens, output_tokens = self._make_request(prompt)
            self._hourly_tokens += input_tokens + output_tokens
            self._daily_tokens += input_tokens + output_tokens
            return response
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise

    def _check_and_reset_counters(self):
        now = beijing_now()

        if (now - self._last_hour_reset).total_seconds() >= 3600:
            with self._lock:
                self._hourly_count = 0
                self._hourly_tokens = 0
                self._last_hour_reset = now

        if (now - self._last_day_reset).total_seconds() >= 86400:
            with self._lock:
                self._daily_count = 0
                self._daily_tokens = 0
                self._last_day_reset = now

    def _can_make_call(self) -> bool:
        with self._lock:
            if self._hourly_count >= self.config.hourly_limit:
                logger.warning(f"Hourly limit reached for {self.config.name}")
                return False
            if self._daily_count >= self.config.daily_limit:
                logger.warning(f"Daily limit reached for {self.config.name}")
                return False
        return True

    def _make_request(self, prompt: str) -> tuple:
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_calls": self._call_count,
                "hourly_calls": self._hourly_count,
                "daily_calls": self._daily_count,
                "hourly_tokens": self._hourly_tokens,
                "daily_tokens": self._daily_tokens
            }


class ClaudeAdapter(BaseModelAdapter):
    def _make_request(self, prompt: str) -> tuple:
        try:
            import anthropic
        except ImportError:
            return self._fallback_response(prompt)

        client = anthropic.Anthropic(api_key=self.config.api_key)

        response = client.messages.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return response.content[0].text, input_tokens, output_tokens

    def _fallback_response(self, prompt: str) -> tuple:
        return "Claude not available", 0, 0


class OpenAIAdapter(BaseModelAdapter):
    def _make_request(self, prompt: str) -> tuple:
        try:
            from openai import OpenAI
        except ImportError:
            return self._fallback_response(prompt)

        client = OpenAI(api_key=self.config.api_key)

        response = client.chat.completions.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0

        return response.choices[0].message.content, input_tokens, output_tokens

    def _fallback_response(self, prompt: str) -> tuple:
        return "OpenAI not available", 0, 0


class QwenAdapter(BaseModelAdapter):
    def _make_request(self, prompt: str) -> tuple:
        try:
            from openai import OpenAI
        except ImportError:
            return self._fallback_response(prompt)

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )

        response = client.chat.completions.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0

        return response.choices[0].message.content, input_tokens, output_tokens

    def _fallback_response(self, prompt: str) -> tuple:
        return "Qwen not available", 0, 0


class MiniMaxAdapter(BaseModelAdapter):
    def _make_request(self, prompt: str) -> tuple:
        try:
            import requests
        except ImportError:
            return self._fallback_response(prompt)

        api_key = self.config.api_key
        if not api_key:
            return "MiniMax API key not configured", 0, 0

        url = f"https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId={api_key}"

        payload = {
            "model": self.config.model_name,
            "tokens_to_generate": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"sender_type": "user", "text": prompt}]
        }

        try:
            response = requests.post(url, json=payload, timeout=self.config.timeout)
            if response.status_code == 200:
                result = response.json()
                text = result.get("choices", [{}])[0].get("text", "")
                tokens = len(prompt) + len(text)
                return text, tokens // 2, tokens // 2
            else:
                return f"Error: {response.status_code}", 0, 0
        except Exception as e:
            return f"MiniMax error: {str(e)}", 0, 0

    def _fallback_response(self, prompt: str) -> tuple:
        return "MiniMax not available", 0, 0


class SparkAdapter(BaseModelAdapter):
    """
    讯飞星火适配器 - 使用 WebSocket + HMAC-SHA256 鉴权
    配置说明:
      api_key   格式: "<api_key>:<api_secret>"（冒号分隔）
      base_url  填写星火 app_id
      model_name 填写模型域名，如 "generalv3.5"
    """

    # WebSocket 接入地址（按 model_name 映射）
    _WS_HOST = "spark-api.xf-yun.com"
    _WS_PATH_MAP = {
        "lite": "/v1.1/chat",
        "generalv2": "/v2.1/chat",
        "generalv3": "/v3.1/chat",
        "generalv3.5": "/v3.5/chat",
        "4.0Ultra": "/v4.0/chat",
    }

    def _build_ws_url(self, api_key: str, api_secret: str) -> str:
        import hmac
        import hashlib
        import base64
        import urllib.parse
        from email.utils import formatdate

        date = formatdate(usegmt=True)
        path = self._WS_PATH_MAP.get(self.config.model_name, "/v3.5/chat")
        signature_origin = (
            f"host: {self._WS_HOST}\n"
            f"date: {date}\n"
            f"GET {path} HTTP/1.1"
        )
        sig = base64.b64encode(
            hmac.new(api_secret.encode(), signature_origin.encode(), digestmod=hashlib.sha256).digest()
        ).decode()
        auth_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{sig}"'
        )
        authorization = base64.b64encode(auth_origin.encode()).decode()
        params = urllib.parse.urlencode({
            "authorization": authorization,
            "date": date,
            "host": self._WS_HOST,
        })
        return f"wss://{self._WS_HOST}{path}?{params}"

    def _make_request(self, prompt: str) -> tuple:
        try:
            import websocket
            import json as _json
            import threading as _threading
        except ImportError:
            raise RuntimeError("websocket-client not installed, run: pip install websocket-client")

        raw_key = self.config.api_key
        if not raw_key or ":" not in raw_key:
            raise ValueError("Spark api_key must be '<api_key>:<api_secret>'")

        api_key, api_secret = raw_key.split(":", 1)
        app_id = self.config.base_url or ""
        ws_url = self._build_ws_url(api_key, api_secret)

        result_chunks: list = []
        error_holder: list = []
        done_event = _threading.Event()

        def on_message(ws, message):
            data = _json.loads(message)
            code = data.get("header", {}).get("code", -1)
            if code != 0:
                error_holder.append(f"Spark error code {code}: {data.get('header', {}).get('message', '')}")
                done_event.set()
                return
            choices = data.get("payload", {}).get("choices", {}).get("text", [])
            for item in choices:
                result_chunks.append(item.get("content", ""))
            status = data.get("header", {}).get("status", -1)
            if status == 2:
                done_event.set()

        def on_error(ws, error):
            error_holder.append(str(error))
            done_event.set()

        def on_open(ws):
            payload = {
                "header": {"app_id": app_id, "uid": "user"},
                "parameter": {
                    "chat": {
                        "domain": self.config.model_name,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                    }
                },
                "payload": {"message": {"text": [{"role": "user", "content": prompt}]}},
            }
            ws.send(_json.dumps(payload))

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
        )
        t = _threading.Thread(target=ws_app.run_forever, daemon=True)
        t.start()
        done_event.wait(timeout=self.config.timeout)
        ws_app.close()

        if error_holder:
            raise RuntimeError(error_holder[0])

        text = "".join(result_chunks)
        input_tokens = len(prompt) // 4
        output_tokens = len(text) // 4
        return text, input_tokens, output_tokens


class PromptVersionManager:
    def __init__(self):
        self._templates: Dict[str, List[PromptTemplate]] = defaultdict(list)
        self._active_versions: Dict[str, int] = {}
        self._lock = threading.Lock()

    def register_template(
        self,
        template_id: str,
        name: str,
        prompt_text: str,
        description: str = ""
    ) -> PromptTemplate:
        with self._lock:
            existing = self._templates.get(template_id, [])
            version = len(existing) + 1

            template = PromptTemplate(
                template_id=template_id,
                name=name,
                prompt_text=prompt_text,
                version=version,
                created_at=beijing_now(),
                description=description
            )

            self._templates[template_id].append(template)

            if template_id not in self._active_versions:
                self._active_versions[template_id] = version

            self._save_to_db(template)

            logger.info(f"Registered prompt template {template_id} v{version}")
            return template

    def _save_to_db(self, template: PromptTemplate):
        collection = get_collection("ai_prompt_templates")
        collection.update_one(
            {"template_id": template.template_id, "version": template.version},
            {"$set": {
                "name": template.name,
                "prompt_text": template.prompt_text,
                "version": template.version,
                "description": template.description,
                "created_at": template.created_at
            }},
            upsert=True
        )

    def get_active_template(self, template_id: str) -> Optional[PromptTemplate]:
        with self._lock:
            version = self._active_versions.get(template_id)
            if version is None:
                return None

            templates = self._templates.get(template_id, [])
            for t in templates:
                if t.version == version:
                    return t
            return None

    def get_template_version(self, template_id: str, version: int) -> Optional[PromptTemplate]:
        with self._lock:
            templates = self._templates.get(template_id, [])
            for t in templates:
                if t.version == version:
                    return t
            return None

    def rollback(self, template_id: str, target_version: int) -> bool:
        with self._lock:
            templates = self._templates.get(template_id, [])
            version_exists = any(t.version == target_version for t in templates)

            if not version_exists:
                return False

            self._active_versions[template_id] = target_version
            logger.info(f"Rolled back {template_id} to version {target_version}")
            return True

    def list_templates(self, template_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            templates = self._templates.get(template_id, [])
            return [
                {
                    "version": t.version,
                    "name": t.name,
                    "description": t.description,
                    "created_at": t.created_at.isoformat(),
                    "active": t.version == self._active_versions.get(template_id)
                }
                for t in templates
            ]


# AsyncCallProcessor removed — replaced by LangGraph ThreadPoolExecutor in orchestration/graph.py


class ModelManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True

            self._models: Dict[str, BaseModelAdapter] = {}
            self._model_configs: Dict[str, ModelConfig] = {}
            self._call_history: List[ModelCall] = []
            self._result_cache: Dict[str, Any] = {}
            self._cache_ttl = timedelta(hours=24)

            self._token_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            self._cost_usage: Dict[str, float] = defaultdict(float)

            self._prompt_manager = PromptVersionManager()

            self._init_models()

            logger.info("ModelManager initialized with enhanced features")

    def _init_models(self):
        configs = Settings.AI_MODEL_CONFIG

        self._model_configs["claude"] = ModelConfig(
            name="claude",
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url="https://api.anthropic.com",
            model_name=configs.get("claude_model", ""),
            timeout=configs.get("timeout", 60),
            max_tokens=configs.get("max_tokens", 4096),
            temperature=0.7,
            priority=1,
            hourly_limit=configs.get("hourly_limit", 100),
            daily_limit=configs.get("daily_limit", 1000),
            enabled=bool(os.getenv("ANTHROPIC_API_KEY")),
            cost_per_token=0.000003
        )

        self._model_configs["openai"] = ModelConfig(
            name="openai",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url="https://api.openai.com/v1",
            model_name=configs.get("openai_model", ""),
            timeout=configs.get("timeout", 60),
            max_tokens=configs.get("max_tokens", 4096),
            temperature=0.7,
            priority=2,
            hourly_limit=configs.get("hourly_limit", 100),
            daily_limit=configs.get("daily_limit", 1000),
            enabled=bool(os.getenv("OPENAI_API_KEY")),
            cost_per_token=0.000005
        )

        self._model_configs["qwen"] = ModelConfig(
            name="qwen",
            api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_name=configs.get("qwen_model", ""),
            timeout=configs.get("timeout", 60),
            max_tokens=configs.get("max_tokens", 4096),
            temperature=0.7,
            priority=3,
            hourly_limit=configs.get("hourly_limit", 100),
            daily_limit=configs.get("daily_limit", 1000),
            enabled=bool(os.getenv("DASHSCOPE_API_KEY")),
            cost_per_token=0.000001
        )

        self._model_configs["minimax"] = ModelConfig(
            name="minimax",
            api_key=os.getenv("MINIMAX_API_KEY", ""),
            base_url="https://api.minimaxi.com/v1",
            model_name=configs.get("minimax_model", ""),
            timeout=configs.get("timeout", 30),
            max_tokens=configs.get("max_tokens", 2048),
            temperature=0.7,
            priority=4,
            hourly_limit=configs.get("hourly_limit", 50),
            daily_limit=configs.get("daily_limit", 500),
            enabled=bool(os.getenv("MINIMAX_API_KEY")),
            cost_per_token=0.000001
        )

        self._model_configs["spark"] = ModelConfig(
            name="spark",
            api_key=os.getenv("SPARK_API_KEY", ""),
            base_url=os.getenv("SPARK_APP_ID", "general"),
            model_name=configs.get("spark_model", ""),
            timeout=configs.get("timeout", 30),
            max_tokens=configs.get("max_tokens", 2048),
            temperature=0.7,
            priority=5,
            hourly_limit=configs.get("hourly_limit", 50),
            daily_limit=configs.get("daily_limit", 500),
            enabled=bool(os.getenv("SPARK_API_KEY")),
            cost_per_token=0.0000005
        )

    def get_adapter(self, model_name: str = "default") -> Optional[BaseModelAdapter]:
        if model_name == "default":
            model_name = Settings.AI_MODEL_CONFIG.get("default_model", "claude")

        if model_name not in self._models:
            config = self._model_configs.get(model_name)
            if not config or not config.enabled:
                return None

            with self._lock:
                if model_name == "claude":
                    self._models[model_name] = ClaudeAdapter(config)
                elif model_name == "openai":
                    self._models[model_name] = OpenAIAdapter(config)
                elif model_name == "qwen":
                    self._models[model_name] = QwenAdapter(config)
                elif model_name == "minimax":
                    self._models[model_name] = MiniMaxAdapter(config)
                elif model_name == "spark":
                    self._models[model_name] = SparkAdapter(config)

        return self._models.get(model_name)

    def call_model(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        use_cache: bool = True,
        async_call: bool = False
    ) -> Optional[str]:
        cache_key = f"{model_name}_{hash(prompt)}"

        if use_cache and cache_key in self._result_cache:
            cached = self._result_cache[cache_key]
            if beijing_now() - cached["timestamp"] < self._cache_ttl:
                logger.info(f"Returning cached result for prompt")
                return cached["response"]

        if model_name is None:
            model_name = Settings.AI_MODEL_CONFIG.get("default_model", "claude")

        adapter = self.get_adapter(model_name)

        if not adapter:
            adapter = self._find_next_available_model(model_name)

        if not adapter:
            logger.error("No available model")
            return self._fallback_response(prompt)

        if async_call:
            call_id = f"{model_name}_{int(time.time() * 1000)}"
            self._async_processor.submit(call_id, self._sync_call, adapter, prompt, cache_key)
            return None

        return self._sync_call(adapter, prompt, cache_key)

    def _sync_call(
        self,
        adapter: BaseModelAdapter,
        prompt: str,
        cache_key: str,
        use_cache: bool = True
    ) -> Optional[str]:
        try:
            start_time = time.time()
            response = adapter.call(prompt)
            response_time = time.time() - start_time

            input_tokens = len(prompt) // 4
            output_tokens = len(response) // 4
            total_tokens = input_tokens + output_tokens
            cost = total_tokens * adapter.config.cost_per_token

            model_name = adapter.config.name
            self._token_usage[model_name]["input"] += input_tokens
            self._token_usage[model_name]["output"] += output_tokens
            self._token_usage[model_name]["total"] += total_tokens
            self._cost_usage[model_name] += cost

            self._record_call(
                model_name=model_name,
                prompt=prompt,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                success=True,
                error=None,
                response_time=response_time,
                cost=cost
            )

            if use_cache:
                self._result_cache[cache_key] = {
                    "response": response,
                    "timestamp": beijing_now()
                }

            return response

        except Exception as e:
            self._record_call(
                model_name=adapter.config.name,
                prompt=prompt,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                success=False,
                error=str(e),
                response_time=0,
                cost=0
            )

            for backup_name in self._get_fallback_order(adapter.config.name):
                backup_adapter = self.get_adapter(backup_name)
                if backup_adapter:
                    try:
                        logger.info(f"Retrying with {backup_name}")
                        return self._sync_call(backup_adapter, prompt, cache_key)
                    except:
                        continue

            return self._fallback_response(prompt)

    def _find_next_available_model(self, original_model: str) -> Optional[BaseModelAdapter]:
        for model_name in self._get_fallback_order(original_model):
            adapter = self.get_adapter(model_name)
            if adapter:
                return adapter
        return None

    def _get_fallback_order(self, current_model: str) -> List[str]:
        fallback_order = [
            name for name, config in sorted(
                self._model_configs.items(),
                key=lambda x: x[1].priority
            )
            if name != current_model and config.enabled
        ]
        return fallback_order

    def _fallback_response(self, prompt: str) -> str:
        logger.warning("All AI models failed, using rule engine fallback")
        return rule_engine_fallback.execute(prompt)

    def _record_call(
        self,
        model_name: str,
        prompt: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        success: bool,
        error: Optional[str],
        response_time: float,
        cost: float
    ):
        call = ModelCall(
            model_name=model_name,
            prompt=prompt[:500],
            timestamp=beijing_now(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            success=success,
            error=error,
            response_time=response_time,
            cost=cost
        )

        self._call_history.append(call)

        if len(self._call_history) > 1000:
            self._call_history = self._call_history[-500:]

        collection = get_collection("ai_call_history")
        collection.insert_one({
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "success": success,
            "error": error,
            "response_time": response_time,
            "cost": cost,
            "timestamp": beijing_now()
        })

    def get_model_stats(self) -> Dict[str, Any]:
        total_calls = len(self._call_history)
        successful_calls = sum(1 for c in self._call_history if c.success)

        stats_by_model = {}
        for model_name in self._model_configs:
            model_calls = [c for c in self._call_history if c.model_name == model_name]
            if model_calls:
                stats_by_model[model_name] = {
                    "total_calls": len(model_calls),
                    "successful_calls": sum(1 for c in model_calls if c.success),
                    "avg_response_time": sum(c.response_time for c in model_calls) / len(model_calls),
                    "total_tokens": sum(c.total_tokens for c in model_calls),
                    "total_cost": sum(c.cost for c in model_calls)
                }

        return {
            "total_calls": total_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "cache_size": len(self._result_cache),
            "models": stats_by_model,
            "token_usage": dict(self._token_usage),
            "cost_usage": dict(self._cost_usage)
        }

    def get_token_usage_summary(self) -> Dict[str, Any]:
        summary = {}
        for model_name, usage in self._token_usage.items():
            summary[model_name] = {
                "input_tokens": usage["input"],
                "output_tokens": usage["output"],
                "total_tokens": usage["total"],
                "estimated_cost": self._cost_usage.get(model_name, 0)
            }
        return summary

    def register_prompt_template(
        self,
        template_id: str,
        name: str,
        prompt_text: str,
        description: str = ""
    ) -> PromptTemplate:
        return self._prompt_manager.register_template(template_id, name, prompt_text, description)

    def get_prompt_template(self, template_id: str) -> Optional[PromptTemplate]:
        return self._prompt_manager.get_active_template(template_id)

    def rollback_prompt(self, template_id: str, version: int) -> bool:
        return self._prompt_manager.rollback(template_id, version)

    def clear_cache(self):
        self._result_cache.clear()
        logger.info("AI result cache cleared")

    def clear_token_stats(self):
        self._token_usage.clear()
        self._cost_usage.clear()
        logger.info("Token statistics cleared")

    def shutdown(self):
        logger.info("ModelManager shutdown")


class RuleEngineFallback:
    def __init__(self):
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()

    def execute(self, prompt: str) -> str:
        try:
            code = self._extract_code_from_prompt(prompt)
            if code:
                return self._analyze_with_rules(code)
            return self._generate_neutral_response()
        except Exception as e:
            logger.error(f"Rule engine error: {e}")
            return self._generate_neutral_response()

    def _extract_code_from_prompt(self, prompt: str) -> Optional[str]:
        import re
        patterns = [
            r"股票\s*([A-Z]{2}\d{6})",
            r"code\s*([A-Z]{2}\d{6})",
            r"([A-Z]{2}\d{6})",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1)
        return None

    def _analyze_with_rules(self, code: str) -> str:
        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if len(klines) < 5:
            return self._generate_neutral_response()

        closes = [k.get("close", 0) for k in klines]
        volumes = [k.get("volume", 0) for k in klines]

        current_price = closes[0]
        ma5 = sum(closes[:5]) / min(5, len(closes))
        ma10 = sum(closes[:10]) / min(10, len(closes))
        ma20 = sum(closes[:20]) / min(20, len(closes))
        ma60 = sum(closes[:min(60, len(closes))]) / min(60, len(closes))

        change_pct = 0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (closes[0] - closes[1]) / closes[1] * 100

        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = volumes[0] / avg_volume if avg_volume > 0 else 1

        trend = "unknown"
        score = 50

        if current_price > ma20 > ma10 > ma5:
            trend = "上升趋势"
            score = 65
        elif current_price < ma20 < ma10 < ma5:
            trend = "下降趋势"
            score = 35
        else:
            trend = "震荡整理"
            score = 50

        if change_pct > 3:
            score += 10
        elif change_pct < -3:
            score -= 10

        if volume_ratio > 2:
            score += 5
        elif volume_ratio < 0.5:
            score -= 5

        score = min(100, max(0, score))

        recommendation = "观望"
        if score >= 70:
            recommendation = "买入"
        elif score <= 30:
            recommendation = "回避"

        return self._format_structured_response(
            code=code,
            score=score,
            recommendation=recommendation,
            trend=trend,
            change_pct=change_pct,
            volume_ratio=volume_ratio,
            current_price=current_price,
            ma5=ma5,
            ma20=ma20
        )

    def _format_structured_response(
        self,
        code: str,
        score: float,
        recommendation: str,
        trend: str,
        change_pct: float,
        volume_ratio: float,
        current_price: float,
        ma5: float,
        ma20: float
    ) -> str:
        import json
        stock_info = self.stock_info_storage.get_by_code(code)
        stock_name = stock_info.get("name", "") if stock_info else ""

        response = {
            "code": code,
            "name": stock_name,
            "score": round(score, 2),
            "recommendation": recommendation,
            "reasons": [
                f"趋势判断：{trend}",
                f"涨跌幅：{change_pct:.2f}%",
                f"成交量比：{volume_ratio:.2f}倍",
                f"现价：{current_price:.2f}",
                f"MA5：{ma5:.2f}",
                f"MA20：{ma20:.2f}"
            ],
            "risk_factors": [],
            "support_levels": [round(ma20 * 0.95, 2)],
            "resistance_levels": [round(ma20 * 1.05, 2)],
            "stop_loss": round(current_price * 0.95, 2),
            "target_price": round(current_price * 1.10, 2),
            "summary": f"基于规则引擎的量化分析，{recommendation}",
            "analysis_method": "rule_engine_fallback",
            "analyzed_at": beijing_now().isoformat()
        }

        return json.dumps(response, ensure_ascii=False)

    def _generate_neutral_response(self) -> str:
        import json
        response = {
            "code": "UNKNOWN",
            "name": "未知",
            "score": 50,
            "recommendation": "观望",
            "reasons": ["数据不足，无法分析"],
            "risk_factors": ["市场不确定性较高"],
            "support_levels": [],
            "resistance_levels": [],
            "stop_loss": 0,
            "target_price": 0,
            "summary": "规则引擎分析，数据不足，建议观望",
            "analysis_method": "rule_engine_fallback",
            "analyzed_at": beijing_now().isoformat()
        }
        return json.dumps(response, ensure_ascii=False)


rule_engine_fallback = RuleEngineFallback()

model_manager = ModelManager()