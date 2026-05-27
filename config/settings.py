"""
全局配置管理
"""
import os
from typing import Dict, List, Optional
from pathlib import Path


class Settings:
    BASE_DIR = Path(__file__).parent.parent

    LOG_DIR = BASE_DIR / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "stock_collector")

    DATA_SOURCE_PRIORITY = ["sina", "ths", "baidu", "eastmoney"]

    COLLECTOR_CONFIG = {
        "retry_times": 3,
        "retry_delay": 2,
        "request_timeout": 30,
        "default_batch_size": 100,
    }

    RATE_LIMIT_CONFIG = {
        "min_interval": 1.0,
        "normal_interval": 2.0,
        "batch_interval": 3.0,
        "max_concurrent": 5,
    }

    CIRCUIT_BREAKER_CONFIG = {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "half_open_max_calls": 3,
    }

    API_CONFIG = {
        "host": "0.0.0.0",
        "port": 5555,
        "debug": False,
    }

    AI_MODEL_CONFIG = {
        "default_model": "claude-sonnet-4-6",
        "models": ["claude-sonnet-4-6", "gpt-4o", "qwen-plus"],
        "timeout": 60,
        "max_tokens": 4096,
    }

    BACKTEST_CONFIG = {
        "default_cash": 1000000,
        "default_commission": 0.001,
        "default_slippage": 0.001,
    }

    LOG_CONFIG = {
        "normal_retention_days": 30,
        "error_retention_days": 60,
        "default_level": "INFO",
    }

    WATCHLIST_CONFIG = {
        "max_stocks_per_group": 500,
        "max_groups": 50,
        "snapshot_retention_days": 90,
    }

    @classmethod
    def get_collection_config(cls, collection_type: str) -> Dict:
        configs = {
            "kline": {
                "indexes": [
                    [("code", 1), ("date", -1)],
                    [("date", -1)],
                ]
            },
            "stock_info": {
                "indexes": [
                    [("code", 1)],
                    [("update_time", -1)],
                ]
            },
            "financial": {
                "indexes": [
                    [("code", 1), ("report_date", -1)],
                    [("report_date", -1)],
                ]
            },
            "news": {
                "indexes": [
                    [("code", 1), ("publish_date", -1)],
                    [("publish_date", -1)],
                ]
            },
            "fund_flow": {
                "indexes": [
                    [("code", 1), ("date", -1)],
                    [("date", -1)],
                ]
            },
            "task": {
                "indexes": [
                    [("task_id", 1)],
                    [("status", 1), ("create_time", -1)],
                ]
            },
            "watchlist": {
                "indexes": [
                    [("user_id", 1), ("group_id", 1)],
                    [("code", 1)],
                ]
            },
            "ai_result": {
                "indexes": [
                    [("code", 1), ("strategy", 1), ("date", -1)],
                    [("created_at", -1)],
                ]
            },
        }
        return configs.get(collection_type, {})

    @classmethod
    def get_rate_limit_interval(cls, scene: str = "normal") -> float:
        intervals = {
            "incremental": cls.RATE_LIMIT_CONFIG["min_interval"],
            "normal": cls.RATE_LIMIT_CONFIG["normal_interval"],
            "batch": cls.RATE_LIMIT_CONFIG["batch_interval"],
        }
        return intervals.get(scene, cls.RATE_LIMIT_CONFIG["normal_interval"])

    @classmethod
    def get_max_concurrent(cls) -> int:
        return cls.RATE_LIMIT_CONFIG["max_concurrent"]

    @classmethod
    def is_eastmoney_source(cls, source: str) -> bool:
        return source.lower() in ["eastmoney", "em", "东方财富"]

    @classmethod
    def get_data_source_priority(cls, exclude_eastmoney: bool = True) -> List[str]:
        if exclude_eastmoney:
            return [s for s in cls.DATA_SOURCE_PRIORITY if not cls.is_eastmoney_source(s)]
        return cls.DATA_SOURCE_PRIORITY


settings = Settings()