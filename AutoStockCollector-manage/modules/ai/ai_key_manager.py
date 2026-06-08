"""
AI Key 管理模块
支持多厂商API Key配置，含自定义 Base URL
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from config.database import DatabaseConfig
from utils.logger import get_logger


logger = get_logger(__name__)

# 内置厂商默认配置
_BUILTIN: Dict[str, Dict] = {
    "openai":    {"name": "OpenAI",              "base_url": "https://api.openai.com/v1",                           "priority": 1},
    "anthropic": {"name": "Anthropic (Claude)",  "base_url": "https://api.anthropic.com",                           "priority": 2},
    "qwen":      {"name": "通义千问",             "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",   "priority": 3},
    "deepseek":  {"name": "DeepSeek",            "base_url": "https://api.deepseek.com/v1",                         "priority": 4},
    "gemini":    {"name": "Google Gemini",       "base_url": "https://generativelanguage.googleapis.com/v1beta",    "priority": 5},
    "moonshot":  {"name": "月之暗面 (Moonshot)",  "base_url": "https://api.moonshot.cn/v1",                          "priority": 6},
    "glm":       {"name": "智谱 AI (GLM)",        "base_url": "https://open.bigmodel.cn/api/paas/v4",               "priority": 7},
    "doubao":    {"name": "字节豆包",             "base_url": "https://ark.cn-beijing.volces.com/api/v3",            "priority": 8},
    "mistral":   {"name": "Mistral AI",          "base_url": "https://api.mistral.ai/v1",                           "priority": 9},
    "minimax":   {"name": "MiniMax",             "base_url": "https://api.minimaxi.com/v1",                         "priority": 10},
    "agnes":     {"name": "Agnes AI",            "base_url": "https://apihub.agnes-ai.com/v1",                      "priority": 11},
}


class AIKeyManager:
    def __init__(self):
        self.collection_name = "ai_keys"
        self._ensure_collection()

    def _ensure_collection(self):
        db = DatabaseConfig.get_database()
        if self.collection_name not in db.list_collection_names():
            db.create_collection(self.collection_name)
            db[self.collection_name].create_index([("provider", 1)], unique=True)
            self._init_default_keys()

    def _init_default_keys(self):
        for provider, cfg in list(_BUILTIN.items())[:3]:  # 默认只初始化前3个
            self.update_key(
                provider=provider,
                name=cfg["name"],
                enabled=False,
                priority=cfg["priority"],
                base_url=cfg["base_url"],
            )

    def list_keys(self) -> List[Dict[str, Any]]:
        db = DatabaseConfig.get_database()
        keys = list(db[self.collection_name].find({}, {"_id": 0}))
        for k in keys:
            raw_key = k.pop("api_key", None)
            k["has_key"] = bool(raw_key)
            k.setdefault("model", "")
        return sorted(keys, key=lambda x: x.get("priority", 99))

    def update_key(
        self,
        provider: str,
        name: str,
        enabled: bool = False,
        priority: int = 99,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bool:
        import os
        db = DatabaseConfig.get_database()
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }
        if api_key:
            env_key = env_map.get(provider.lower())
            if env_key:
                os.environ[env_key] = api_key

        doc: Dict[str, Any] = {
            "provider": provider,
            "name": name,
            "enabled": enabled,
            "priority": priority,
            "updated_at": datetime.now().isoformat(),
        }
        if api_key:
            doc["api_key"] = api_key
            doc["has_key"] = True
        if base_url is not None:
            doc["base_url"] = base_url
        if model is not None:
            doc["model"] = model

        db[self.collection_name].update_one({"provider": provider}, {"$set": doc}, upsert=True)
        logger.info(f"Updated AI key config for {provider}")
        return True

    def restore_keys_from_db(self):
        """服务重启后从 DB 恢复环境变量"""
        import os
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }
        try:
            db = DatabaseConfig.get_database()
            for doc in db[self.collection_name].find({"api_key": {"$exists": True, "$ne": ""}}):
                provider = doc.get("provider", "")
                api_key = doc.get("api_key")
                if not api_key:
                    continue
                env_key = env_map.get(provider.lower())
                if env_key:
                    os.environ[env_key] = api_key
                    logger.info(f"Restored API key for {provider} from database")
        except Exception as e:
            logger.warning(f"Failed to restore API keys: {e}")

    def delete_key(self, provider: str) -> bool:
        import os
        db = DatabaseConfig.get_database()
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }
        env_key = env_map.get(provider.lower())
        if env_key:
            os.environ.pop(env_key, None)
        db[self.collection_name].delete_one({"provider": provider})
        logger.info(f"Deleted AI key for {provider}")
        return True

    def test_key(self, provider: str, api_key: str, base_url: str = "") -> dict:
        """向厂商 API 发一个轻量请求验证 Key 有效性。
        自定义 base_url 视为 OpenAI 兼容接口。"""
        import requests as req
        p = provider.lower()
        timeout = 12

        effective_url = base_url.strip() or (_BUILTIN.get(p, {}).get("base_url", ""))

        try:
            if p == "anthropic" and not base_url:
                resp = req.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    timeout=timeout,
                )
            elif p == "gemini" and not base_url:
                resp = req.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                    timeout=timeout,
                )
            elif p == "minimax":
                resp = req.post(
                    "https://api.minimaxi.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "MiniMax-Text-01",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 5
                    },
                    timeout=timeout,
                )
            elif effective_url:
                url = effective_url.rstrip("/") + "/models"
                resp = req.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
            else:
                return {"valid": False, "message": f"未知厂商 {provider}，请配置 Base URL"}

            if resp.status_code == 200:
                return {"valid": True, "message": "API Key 有效"}
            elif resp.status_code in (401, 403):
                error_msg = "API Key 无效或已过期"
                try:
                    err_data = resp.json()
                    if err_data.get("base_resp", {}).get("status_msg"):
                        error_msg = f"API Key 无效: {err_data['base_resp']['status_msg']}"
                    elif err_data.get("error", {}).get("message"):
                        error_msg = f"API Key 无效: {err_data['error']['message']}"
                except:
                    pass
                return {"valid": False, "message": error_msg}
            elif resp.status_code == 429:
                return {"valid": True, "message": "Key 有效（触发速率限制）"}
            else:
                try:
                    err_data = resp.json()
                    err_msg = err_data.get("base_resp", {}).get("status_msg") or err_data.get("error", {}).get("message") or resp.text[:100].strip()
                    return {"valid": False, "message": f"HTTP {resp.status_code}: {err_msg}"}
                except:
                    return {"valid": False, "message": f"HTTP {resp.status_code}: {resp.text[:100].strip()}"}

        except req.exceptions.Timeout:
            return {"valid": False, "message": "连接超时，请检查网络或 VPN"}
        except req.exceptions.ConnectionError:
            return {"valid": False, "message": "连接失败，请检查网络环境"}
        except Exception as e:
            return {"valid": False, "message": f"验证出错: {str(e)[:80]}"}

    def fetch_models(self, provider: str, api_key: str, base_url: str = "") -> dict:
        """从厂商 API 拉取可用模型列表。"""
        import requests as req
        p = provider.lower()
        timeout = 12
        effective_url = base_url.strip() or (_BUILTIN.get(p, {}).get("base_url", ""))

        try:
            if p == "anthropic":
                resp = req.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    return {"models": ids, "source": "api"}

            elif p == "gemini":
                resp = req.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ids = [m.get("name", "").split("/")[-1]
                           for m in data.get("models", [])
                           if "generateContent" in m.get("supportedGenerationMethods", [])]
                    return {"models": ids, "source": "api"}

            elif p == "minimax":
                resp = req.get(
                    "https://api.minimaxi.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ids = data.get("data", []) if isinstance(data, dict) else data
                    if isinstance(ids, list):
                        model_ids = [m.get("id") or m.get("name") or m for m in ids if isinstance(m, dict) or isinstance(m, str)]
                        return {"models": model_ids, "source": "api"}
                    return {"models": [], "source": "fallback"}

            elif effective_url:
                url = effective_url.rstrip("/") + "/models"
                resp = req.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    # 兼容 OpenAI 格式 {data: [{id:...}]} 和直接数组
                    items = data.get("data") or data.get("models") or (data if isinstance(data, list) else [])
                    ids = []
                    for m in items:
                        mid = m.get("id") or m.get("name") or (m if isinstance(m, str) else None)
                        if mid:
                            ids.append(mid)
                    if ids:
                        # 优先展示非 embedding/moderation 类模型
                        chat_ids = [i for i in ids if not any(x in i.lower() for x in ("embed", "moderat", "whisper", "tts", "dall"))]
                        return {"models": chat_ids or ids, "source": "api"}

        except Exception as e:
            logger.warning(f"fetch_models failed for {provider}: {e}")

        return {"models": [], "source": "fallback"}

    def get_best_provider(self) -> Optional[str]:
        db = DatabaseConfig.get_database()
        key = db[self.collection_name].find_one({"enabled": True}, sort=[("priority", 1)])
        return key["provider"] if key else None


ai_key_manager = AIKeyManager()
