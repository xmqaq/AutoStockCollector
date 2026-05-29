"""
策略管理模块
管理选股策略的参数配置
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pymongo import ASCENDING, DESCENDING
from config.database import DatabaseConfig
from utils.logger import get_logger


logger = get_logger(__name__)


class StrategyConfig:
    def __init__(
        self,
        name: str,
        strategy_type: str,
        description: str = "",
        params: Dict[str, Any] = None,
        enabled: bool = True
    ):
        self.name = name
        self.strategy_type = strategy_type
        self.description = description
        self.params = params or {}
        self.enabled = enabled
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "strategy_type": self.strategy_type,
            "description": self.description,
            "params": self.params,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        config = cls(
            name=data.get("name", ""),
            strategy_type=data.get("strategy_type", ""),
            description=data.get("description", ""),
            params=data.get("params", {}),
            enabled=data.get("enabled", True),
        )
        if "created_at" in data:
            config.created_at = data["created_at"]
        if "updated_at" in data:
            config.updated_at = data["updated_at"]
        return config


DEFAULT_STRATEGIES = [
    {
        "name": "资金异动策略",
        "strategy_type": "fund_flow",
        "description": "基于资金异动和主力跟踪的选股策略",
        "enabled": True,
        "params": {
            "min_score": 65,
            "min_inflow": 10000000,
            "volume_ratio": 1.5,
            "flow_weight": 0.6,
            "volume_weight": 0.4,
        }
    },
    {
        "name": "趋势跟踪策略",
        "strategy_type": "trend",
        "description": "基于技术分析和趋势跟踪的选股策略",
        "enabled": True,
        "params": {
            "ma_short": 10,
            "ma_long": 20,
            "min_trend_score": 60,
            "volume_threshold": 1.2,
        }
    },
    {
        "name": "价值投资策略",
        "strategy_type": "fundamental",
        "description": "基于基本面分析和价值投资的选股策略",
        "enabled": True,
        "params": {
            "min_pe": 5,
            "max_pe": 30,
            "min_roe": 10,
            "min_growth": 5,
        }
    },
    {
        "name": "超跌反弹策略",
        "strategy_type": "reversal",
        "description": "基于超跌反弹的低风险套利策略",
        "enabled": True,
        "params": {
            "max_drawdown": 10,
            "min_recovery_days": 3,
            "min_volume_ratio": 1.3,
        }
    },
    {
        "name": "板块轮动策略",
        "strategy_type": "sector",
        "description": "基于热门板块轮动的题材选股策略",
        "enabled": True,
        "params": {
            "top_blocks": 10,
            "momentum_days": 3,
            "min_momentum_score": 60,
        }
    },
    {
        "name": "综合评分策略",
        "strategy_type": "multi_factor",
        "description": "综合多个因子进行评分选股",
        "enabled": True,
        "params": {
            "sentiment_weight": 0.2,
            "flow_weight": 0.25,
            "technical_weight": 0.25,
            "fundamental_weight": 0.3,
            "min_total_score": 60,
        }
    },
]


class StrategyConfigManager:
    def __init__(self):
        self.collection_name = "strategy_configs"
        self._ensure_collection()

    def _ensure_collection(self):
        db = DatabaseConfig.get_database()
        if self.collection_name not in db.list_collection_names():
            db.create_collection(self.collection_name)
            collection = db[self.collection_name]
            collection.create_index([("name", ASCENDING)], unique=True)
            collection.create_index([("strategy_type", ASCENDING)])
            collection.create_index([("enabled", ASCENDING)])
            self._init_default_strategies()

    def _init_default_strategies(self):
        for strategy in DEFAULT_STRATEGIES:
            self.create_or_update_strategy(
                name=strategy["name"],
                strategy_type=strategy["strategy_type"],
                description=strategy.get("description", ""),
                params=strategy.get("params", {}),
                enabled=strategy.get("enabled", True)
            )
        logger.info(f"Initialized {len(DEFAULT_STRATEGIES)} default strategies")

    def list_strategies(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]

        query = {"enabled": True} if enabled_only else {}
        strategies = list(collection.find(query).sort("created_at", DESCENDING))

        for s in strategies:
            s.pop("_id", None)
            if "created_at" in s and hasattr(s["created_at"], "isoformat"):
                s["created_at"] = s["created_at"].isoformat()
            if "updated_at" in s and hasattr(s["updated_at"], "isoformat"):
                s["updated_at"] = s["updated_at"].isoformat()

        return strategies

    def get_strategy(self, name: str) -> Optional[Dict[str, Any]]:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]
        strategy = collection.find_one({"name": name})

        if strategy:
            strategy.pop("_id", None)
            if "created_at" in strategy and hasattr(strategy["created_at"], "isoformat"):
                strategy["created_at"] = strategy["created_at"].isoformat()
            if "updated_at" in strategy and hasattr(strategy["updated_at"], "isoformat"):
                strategy["updated_at"] = strategy["updated_at"].isoformat()

        return strategy

    def create_or_update_strategy(
        self,
        name: str,
        strategy_type: str,
        description: str = "",
        params: Dict[str, Any] = None,
        enabled: bool = True
    ) -> bool:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]

        existing = collection.find_one({"name": name})
        now = datetime.now()

        doc = {
            "name": name,
            "strategy_type": strategy_type,
            "description": description,
            "params": params or {},
            "enabled": enabled,
            "updated_at": now,
        }

        if existing:
            doc["created_at"] = existing.get("created_at", now)
            collection.update_one({"name": name}, {"$set": doc})
            logger.info(f"Updated strategy: {name}")
        else:
            doc["created_at"] = now
            collection.insert_one(doc)
            logger.info(f"Created strategy: {name}")

        return True

    def update_strategy_params(self, name: str, params: Dict[str, Any]) -> bool:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]

        result = collection.update_one(
            {"name": name},
            {"$set": {"params": params, "updated_at": datetime.now()}}
        )

        if result.modified_count > 0:
            logger.info(f"Updated params for strategy: {name}")
            return True
        return False

    def toggle_strategy(self, name: str, enabled: bool) -> bool:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]

        result = collection.update_one(
            {"name": name},
            {"$set": {"enabled": enabled, "updated_at": datetime.now()}}
        )

        if result.modified_count > 0:
            logger.info(f"{'Enabled' if enabled else 'Disabled'} strategy: {name}")
            return True
        return False

    def delete_strategy(self, name: str) -> bool:
        db = DatabaseConfig.get_database()
        collection = db[self.collection_name]

        result = collection.delete_one({"name": name})

        if result.deleted_count > 0:
            logger.info(f"Deleted strategy: {name}")
            return True
        return False

    def get_enabled_strategies(self) -> List[Dict[str, Any]]:
        return self.list_strategies(enabled_only=True)


strategy_config_manager = StrategyConfigManager()
