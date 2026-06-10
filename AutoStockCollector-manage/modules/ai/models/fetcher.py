"""
AI模型列表拉取模块
从官方网站接口获取可用模型列表，支持缓存策略和异常处理
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from utils.helpers import beijing_now
import threading
import requests
from utils.logger import get_logger


logger = get_logger(__name__)


class ModelCache:
    """模型列表缓存管理器"""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def get(self, provider: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的模型列表"""
        with self._lock:
            entry = self._cache.get(provider.lower())
            if entry is None:
                return None

            cached_time = entry.get('_cached_at')
            if cached_time is None:
                return None

            if beijing_now() - cached_time > timedelta(seconds=self._ttl_seconds):
                del self._cache[provider.lower()]
                return None

            return entry.get('models')

    def set(self, provider: str, models: List[Dict[str, Any]]) -> None:
        """设置模型列表缓存"""
        with self._lock:
            self._cache[provider.lower()] = {
                'models': models,
                '_cached_at': beijing_now()
            }

    def invalidate(self, provider: Optional[str] = None) -> None:
        """清除缓存"""
        with self._lock:
            if provider:
                self._cache.pop(provider.lower(), None)
            else:
                self._cache.clear()

    def get_all_cached(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有缓存的模型列表"""
        result = {}
        with self._lock:
            for key, entry in self._cache.items():
                cached_time = entry.get('_cached_at')
                if cached_time and beijing_now() - cached_time <= timedelta(seconds=self._ttl_seconds):
                    result[key] = entry.get('models', [])
        return result


class ModelListFetcher:
    """模型列表拉取器"""

    PROVIDER_ENDPOINTS: Dict[str, str] = {
        'openai': 'https://api.openai.com/v1/models',
        'anthropic': 'https://api.anthropic.com/v1/models',
        'deepseek': 'https://api.deepseek.com/v1/models',
        'moonshot': 'https://api.moonshot.cn/v1/models',
        'glm': 'https://open.bigmodel.cn/api/paas/v4/models',
        'doubao': 'https://ark.cn-beijing.volces.com/api/v3/models',
        'mistral': 'https://api.mistral.ai/v1/models',
        'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1/models',
        'minimax': 'https://api.minimaxi.com/v1/models',
        'agnes': 'https://apihub.agnes-ai.com/v1/models',
    }

    def __init__(self, cache_ttl_seconds: int = 3600, timeout: int = 10):
        self._cache = ModelCache(ttl_seconds=cache_ttl_seconds)
        self._timeout = timeout

    def fetch_models(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        从官方接口拉取模型列表

        Args:
            provider: 提供商名称
            api_key: API密钥
            base_url: 自定义Base URL（可选）

        Returns:
            模型列表
        """
        provider_lower = provider.lower()

        cached_models = self._cache.get(provider_lower)
        if cached_models is not None:
            logger.info(f"Using cached models for {provider}")
            return cached_models

        try:
            models = self._fetch_from_api(provider_lower, api_key, base_url)
            if models:
                self._cache.set(provider_lower, models)
                logger.info(f"Fetched {len(models)} models for {provider}")
                return models
        except Exception as e:
            logger.warning(f"Failed to fetch models from API for {provider}: {e}")
            return []

    def _fetch_from_api(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str]
    ) -> List[Dict[str, Any]]:
        """从API拉取模型列表"""
        endpoint = base_url or self.PROVIDER_ENDPOINTS.get(provider)

        if not endpoint:
            raise ValueError(f"Unknown provider: {provider}")

        if not endpoint.startswith('https://'):
            raise ValueError(f"Only HTTPS endpoints are allowed: {endpoint}")

        if not api_key:
            raise ValueError("API key is required")

        headers = self._build_headers(provider, api_key)
        url = self._build_url_for_provider(endpoint, provider)

        response = requests.get(url, headers=headers, timeout=self._timeout)

        if response.status_code == 401:
            raise PermissionError("Invalid API key")
        if response.status_code == 403:
            raise PermissionError("API key lacks permission")
        if response.status_code == 429:
            raise RuntimeError("Rate limit exceeded")
        if response.status_code != 200:
            raise RuntimeError(f"API returned status {response.status_code}")

        data = response.json()
        return self._parse_response(data, provider)

    def _build_headers(self, provider: str, api_key: str) -> Dict[str, str]:
        """构建请求头"""
        if provider == 'anthropic':
            return {
                'Authorization': f'Bearer {api_key}',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            }
        elif provider == 'minimax':
            return {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        else:
            return {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

    def _build_url(self, endpoint: str) -> str:
        """构建完整URL"""
        endpoint = endpoint.rstrip('/')
        if not endpoint.endswith('/models'):
            endpoint += '/models'
        return endpoint

    def _build_url_for_provider(self, endpoint: str, provider: str) -> str:
        """根据提供商构建完整URL"""
        if provider == 'minimax':
            return endpoint.rstrip('/')
        return self._build_url(endpoint)

    def _parse_response(self, data: Any, provider: str) -> List[Dict[str, Any]]:
        """解析响应数据"""
        if not data:
            raise ValueError("Empty response data")

        models_list = []

        if isinstance(data, dict):
            if 'data' in data:
                models_list = data['data']
            elif 'models' in data:
                models_list = data['models']
            elif 'object' in data and data['object'] == 'list':
                models_list = data.get('data', [])
            else:
                raise ValueError(f"Unexpected response format for {provider}")

        elif isinstance(data, list):
            models_list = data

        else:
            raise ValueError(f"Invalid response type: {type(data)}")

        if not models_list:
            raise ValueError("Model list is empty")

        validated_models = []
        for model in models_list:
            if not isinstance(model, dict):
                continue

            model_id = model.get('id') or model.get('name') or model.get('model')
            if not model_id:
                continue

            validated_models.append({
                'id': str(model_id),
                'name': str(model_id),
                'provider': provider,
                'type': model.get('type', 'chat'),
                'context_length': model.get('context_length') or model.get('max_tokens'),
                'created': model.get('created')
            })

        return validated_models

    def get_default_model(self, provider: str) -> Optional[str]:
        """获取默认模型（返回None，需用户手动配置）"""
        return None

    def invalidate_cache(self, provider: Optional[str] = None) -> None:
        """清除缓存"""
        self._cache.invalidate(provider)

    def get_cache_status(self) -> Dict[str, Any]:
        """获取缓存状态"""
        return {
            'cached_providers': list(self._cache.get_all_cached().keys()),
            'cache_ttl': self._cache._ttl_seconds
        }


model_list_fetcher = ModelListFetcher()