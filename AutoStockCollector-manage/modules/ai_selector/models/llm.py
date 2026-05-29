"""
模型管理层 - 金融专属LLM封装
支持多模型路由、熔断、降级、缓存、成本控制
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
import json
import hashlib
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    response_time: float
    success: bool
    error: Optional[str] = None
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PromptTemplate:
    template_id: str
    name: str
    prompt_text: str
    output_schema: Dict[str, Any]
    version: int = 1


class BaseLLMAdapter:
    def __init__(self, api_key: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = kwargs.get("timeout", 60)
        self.max_tokens = kwargs.get("max_tokens", 4096)
        self.temperature = kwargs.get("temperature", 0.7)
        self.cost_per_token = kwargs.get("cost_per_token", 0.0)

    def chat(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> LLMResponse:
        raise NotImplementedError

    def _build_schema_prompt(self, prompt: str, schema: Dict[str, Any]) -> str:
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        return f"""{prompt}

请严格按以下JSON格式返回（禁止输出其他内容）：
{schema_str}"""


class ClaudeAdapter(BaseLLMAdapter):
    def chat(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> LLMResponse:
        start_time = datetime.now()

        try:
            import anthropic
        except ImportError:
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=0,
                success=False,
                error="anthropic not installed"
            )

        try:
            client = anthropic.Anthropic(api_key=self.api_key)

            if schema:
                prompt = self._build_schema_prompt(prompt, schema)

            response = client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            cost = total_tokens * self.cost_per_token
            response_time = (datetime.now() - start_time).total_seconds()

            return LLMResponse(
                content=content,
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                response_time=response_time,
                success=True
            )

        except Exception as e:
            logger.error(f"Claude call failed: {e}")
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error=str(e)
            )


class OpenAIAdapter(BaseLLMAdapter):
    def chat(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> LLMResponse:
        start_time = datetime.now()

        try:
            from openai import OpenAI
        except ImportError:
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=0,
                success=False,
                error="openai not installed"
            )

        try:
            client = OpenAI(api_key=self.api_key)

            if schema:
                prompt = self._build_schema_prompt(prompt, schema)

            response = client.chat.completions.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
            output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
            total_tokens = input_tokens + output_tokens
            cost = total_tokens * self.cost_per_token
            response_time = (datetime.now() - start_time).total_seconds()

            return LLMResponse(
                content=content,
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                response_time=response_time,
                success=True
            )

        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error=str(e)
            )


class QwenAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model_name: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url

    def chat(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> LLMResponse:
        start_time = datetime.now()

        try:
            from openai import OpenAI
        except ImportError:
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=0,
                success=False,
                error="openai not installed"
            )

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)

            if schema:
                prompt = self._build_schema_prompt(prompt, schema)

            response = client.chat.completions.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
            output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
            total_tokens = input_tokens + output_tokens
            cost = total_tokens * self.cost_per_token
            response_time = (datetime.now() - start_time).total_seconds()

            return LLMResponse(
                content=content,
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                response_time=response_time,
                success=True
            )

        except Exception as e:
            logger.error(f"Qwen call failed: {e}")
            return LLMResponse(
                content="",
                model=self.model_name,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=(datetime.now() - start_time).total_seconds(),
                success=False,
                error=str(e)
            )


class LLMRouter:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._adapters: Dict[str, BaseLLMAdapter] = {}
            self._cache: Dict[str, Dict[str, Any]] = {}
            self._cache_ttl = timedelta(hours=24)
            self._token_stats: Dict[str, Dict[str, int]] = {}
            self._cost_stats: Dict[str, float] = {}
            self._init_adapters()

    def _init_adapters(self):
        import os

        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            self._adapters["claude"] = ClaudeAdapter(
                api_key=anthropic_key,
                model_name="claude-sonnet-4-6",
                cost_per_token=0.000003
            )

        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            self._adapters["openai"] = OpenAIAdapter(
                api_key=openai_key,
                model_name="gpt-4o",
                cost_per_token=0.000005
            )

        dashscope_key = os.getenv("DASHSCOPE_API_KEY", "")
        if dashscope_key:
            self._adapters["qwen"] = QwenAdapter(
                api_key=dashscope_key,
                model_name="qwen-plus",
                cost_per_token=0.000001
            )

    def chat(
        self,
        prompt: str,
        model: str = "claude",
        schema: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs
    ) -> LLMResponse:
        cache_key = f"{model}_{hashlib.md5(prompt.encode()).hexdigest()}"

        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached["timestamp"] < self._cache_ttl:
                logger.debug("Returning cached LLM response")
                cached_response = cached["response"]
                cached_response.cached = True
                return cached_response

        adapter = self._adapters.get(model)
        if not adapter:
            for name, ad in self._adapters.items():
                if name != model:
                    adapter = ad
                    logger.info(f"Falling back to {name}")
                    break

        if not adapter:
            return LLMResponse(
                content="",
                model=model,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0,
                response_time=0,
                success=False,
                error="No available model"
            )

        response = adapter.chat(prompt, schema)

        if response.success:
            self._update_stats(response)

            if use_cache:
                self._cache[cache_key] = {
                    "response": response,
                    "timestamp": datetime.now()
                }

        return response

    def _update_stats(self, response: LLMResponse):
        model = response.model
        if model not in self._token_stats:
            self._token_stats[model] = {"input": 0, "output": 0, "total": 0}
        self._token_stats[model]["input"] += response.input_tokens
        self._token_stats[model]["output"] += response.output_tokens
        self._token_stats[model]["total"] += response.total_tokens

        if model not in self._cost_stats:
            self._cost_stats[model] = 0.0
        self._cost_stats[model] += response.cost

    def get_stats(self) -> Dict[str, Any]:
        return {
            "token_usage": self._token_stats,
            "cost_usage": self._cost_stats,
            "cache_size": len(self._cache),
            "available_models": list(self._adapters.keys())
        }

    def clear_cache(self):
        self._cache.clear()
        logger.info("LLM cache cleared")


class StockSelectionSchema:
    @staticmethod
    def get_selection_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100, "description": "综合评分0-100"},
                "recommendation": {"type": "string", "enum": ["强烈推荐", "买入", "观望", "回避"], "description": "建议"},
                "reasons": {"type": "array", "items": {"type": "string"}, "description": "推荐理由"},
                "risk_factors": {"type": "array", "items": {"type": "string"}, "description": "风险因素"},
                "stop_loss": {"type": "number", "description": "止损位"},
                "target_price": {"type": "number", "description": "目标价"},
                "support_levels": {"type": "array", "items": {"type": "number"}, "description": "支撑位"},
                "resistance_levels": {"type": "array", "items": {"type": "number"}, "description": "压力位"}
            },
            "required": ["score", "recommendation", "reasons"]
        }

    @staticmethod
    def get_analysis_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "recommendation": {"type": "string"},
                "reasons": {"type": "array", "items": {"type": "string"}},
                "risk_factors": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"}
            },
            "required": ["score", "recommendation", "reasons"]
        }


llm_router = LLMRouter()