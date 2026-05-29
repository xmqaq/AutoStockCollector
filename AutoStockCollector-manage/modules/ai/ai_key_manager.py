"""
AI Key 管理模块
支持多厂商API Key配置
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from config.database import DatabaseConfig
from utils.logger import get_logger


logger = get_logger(__name__)


class AIKeyManager:
    def __init__(self):
        self.collection_name = "ai_keys"
        self._ensure_collection()

    def _ensure_collection(self):
        db = DatabaseConfig.get_database()
        if self.collection_name not in db.list_collection_names():
            db.create_collection(self.collection_name)
            collection = db[self.collection_name]
            collection.create_index([("provider", "provider")], unique=True)
            self._init_default_keys()

    def _init_default_keys(self):
        defaults = [
            {"provider": "openai", "name": "OpenAI", "enabled": False, "priority": 1},
            {"provider": "anthropic", "name": "Anthropic", "enabled": False, "priority": 2},
            {"provider": "qwen", "name": "通义千问", "enabled": False, "priority": 3},
        ]
        for d in defaults:
            self.update_key(d["provider"], d["name"], d["enabled"], d["priority"])

    def list_keys(self) -> List[Dict[str, Any]]:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]
        keys = list(collection.find({}, {"_id": 0, "api_key": 0}))
        return sorted(keys, key=lambda x: x.get("priority", 99))

    def get_enabled_key(self, provider: str) -> Optional[str]:
        import os
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
        }
        env_key = env_map.get(provider.lower())
        if not env_key:
            return None
        return os.getenv(env_key)

    def update_key(
        self,
        provider: str,
        name: str,
        enabled: bool = False,
        priority: int = 99,
        api_key: Optional[str] = None,
    ) -> bool:
        import os
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
        }
        if api_key:
            env_key = env_map.get(provider.lower())
            if env_key:
                os.environ[env_key] = api_key
        doc = {
            "provider": provider,
            "name": name,
            "enabled": enabled,
            "priority": priority,
            "updated_at": datetime.now().isoformat(),
        }
        if api_key:
            doc["has_key"] = bool(api_key)
        collection.update_one(
            {"provider": provider},
            {"$set": doc},
            upsert=True,
        )
        logger.info(f"Updated AI key config for {provider}")
        return True

    def delete_key(self, provider: str) -> bool:
        import os
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
        }
        env_key = env_map.get(provider.lower())
        if env_key:
            os.environ.pop(env_key, None)
        collection.delete_one({"provider": provider})
        logger.info(f"Deleted AI key for {provider}")
        return True

    def get_best_provider(self) -> Optional[str]:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]
        key = collection.find_one(
            {"enabled": True},
            sort=[("priority", 1)]
        )
        return key["provider"] if key else None


ai_key_manager = AIKeyManager()
