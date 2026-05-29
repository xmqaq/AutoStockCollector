"""Provider caller：给定 provider+prompt，读 ai_keys 配置发请求返回文本。

OpenAI 兼容为主，anthropic / gemini 特化。key_loader 与 poster 依赖注入便于测试。
默认 key_loader 读 ai_keys 集合，默认 poster 用 requests。
"""
from typing import Any, Callable, Dict, Optional

# provider → 缺省模型（ai_keys 未配 model 时兜底）
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-5",
    "qwen": "qwen-plus",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
    "moonshot": "moonshot-v1-8k",
    "glm": "glm-4-flash",
    "doubao": "doubao-pro-32k",
    "mistral": "mistral-small-latest",
    "minimax": "MiniMax-Text-01",
}

_TIMEOUT = 60


def _default_key_loader(provider: str) -> Optional[Dict[str, Any]]:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    return db["ai_keys"].find_one({"provider": provider})


def _default_poster(method: str, url: str, headers=None, json=None, timeout=None) -> Dict[str, Any]:
    import requests
    resp = requests.request(method, url, headers=headers, json=json, timeout=timeout or _TIMEOUT)
    resp.raise_for_status()
    return resp.json()


class ProviderCaller:
    """可调用对象：caller(provider, prompt) -> str。"""

    def __init__(
        self,
        key_loader: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        poster: Optional[Callable[..., Dict[str, Any]]] = None,
    ):
        self.key_loader = key_loader or _default_key_loader
        self.poster = poster or _default_poster

    def __call__(self, provider: str, prompt: str) -> str:
        doc = self.key_loader(provider)
        if not doc:
            raise ValueError(f"未找到 provider 配置: {provider}")
        api_key = doc.get("api_key")
        if not api_key:
            raise ValueError(f"provider {provider} 未配置 API Key")
        base_url = (doc.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ValueError(f"provider {provider} 未配置 Base URL")
        model = doc.get("model") or _DEFAULT_MODELS.get(provider.lower(), "")
        p = provider.lower()

        if p == "anthropic":
            data = self.poster(
                "POST", f"{base_url}/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]},
                timeout=_TIMEOUT,
            )
            blocks = data.get("content", [])
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return texts[0] if texts else ""

        if p == "gemini":
            data = self.poster(
                "POST", f"{base_url}/models/{model}:generateContent?key={api_key}",
                headers={"content-type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=_TIMEOUT,
            )
            cands = data.get("candidates", [])
            if not cands:
                return ""
            parts = cands[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""

        # OpenAI 兼容
        data = self.poster(
            "POST", f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            timeout=_TIMEOUT,
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")
