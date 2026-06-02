"""Provider caller：给定 provider+prompt，读 ai_keys 配置发请求返回文本。

OpenAI 兼容为主，anthropic / gemini 特化。key_loader 与 poster 依赖注入便于测试。
默认 key_loader 读 ai_keys 集合，默认 poster 用 requests。
"""
from typing import Any, Callable, Dict, List, Optional

_DEFAULT_MODELS: Dict[str, str] = {}

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

    def __call__(self, provider: str, prompt: str,
                 temperature: float = 0.7, max_tokens: int = 2000,
                 messages: Optional[List[Dict[str, str]]] = None) -> str:
        """调用 LLM。传入 messages 时用多轮对话格式，否则将 prompt 包装成单条 user 消息。"""
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

        msg_list = messages if messages else [{"role": "user", "content": prompt}]

        if p == "anthropic":
            # Anthropic 不支持 system role 混在 messages 里，过滤出 system 单独传
            system_msgs = [m["content"] for m in msg_list if m.get("role") == "system"]
            user_msgs = [m for m in msg_list if m.get("role") != "system"]
            payload: Dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": user_msgs}
            if system_msgs:
                payload["system"] = system_msgs[0]
            data = self.poster(
                "POST", f"{base_url}/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json=payload,
                timeout=_TIMEOUT,
            )
            blocks = data.get("content", [])
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return texts[0] if texts else ""

        if p == "gemini":
            # Gemini 用 contents 格式，多轮用 role=user/model
            role_map = {"user": "user", "assistant": "model", "system": "user"}
            contents = [{"role": role_map.get(m["role"], "user"), "parts": [{"text": m["content"]}]}
                        for m in msg_list]
            data = self.poster(
                "POST", f"{base_url}/models/{model}:generateContent?key={api_key}",
                headers={"content-type": "application/json"},
                json={"contents": contents,
                      "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
                timeout=_TIMEOUT,
            )
            cands = data.get("candidates", [])
            if not cands:
                return ""
            parts = cands[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""

        # OpenAI 兼容（minimax / deepseek / 本地等）
        data = self.poster(
            "POST", f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            json={"model": model, "messages": msg_list,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=_TIMEOUT,
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    def stream_call(self, provider: str, prompt: str,
                    messages: Optional[List[Dict[str, str]]] = None):
        """流式调用，返回生成器。传入 messages 时用多轮对话格式。"""
        import json
        import urllib.request
        import urllib.error

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

        msg_list = messages if messages else [{"role": "user", "content": prompt}]

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "model": model,
            "messages": msg_list,
            "temperature": 0.7,
            "stream": True
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(content)
                            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise Exception(f"HTTP {e.code}: {error_body}")
        except Exception as e:
            raise Exception(f"Stream call failed: {str(e)}")
