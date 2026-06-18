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
        # 单次外部调用（典型是 akshare 接口）的墙钟硬超时（秒）。
        # akshare 内部不暴露 timeout，外部源挂起会无限阻塞并占用并发槽，
        # 直到任务级看门狗（3600s）才强杀。这里把单次调用兜底，使熔断器能对
        # "挂起不返回"生效。需 < 任务超时(_TASK_TIMEOUT_SECONDS=3600)，
        # 且 > 单股多接口顺序拉取的正常耗时。
        "call_timeout": 120,
    }

    RATE_LIMIT_CONFIG = {
        "min_interval": 0.5,
        "normal_interval": 1.0,
        "batch_interval": 2.0,
        "max_concurrent": 8,
    }

    CIRCUIT_BREAKER_CONFIG = {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "half_open_max_calls": 3,
    }

    API_CONFIG = {
        "host": "0.0.0.0",
        "port": 5555,
        # 默认关闭 debug:生产容器曾因默认 true 跑在 debug 模式
        # (werkzeug 调试器可被利用 RCE,且 reloader 双进程白耗内存)。
        # 本地开发需要热重载时显式 export FLASK_DEBUG=true
        "debug": os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1"),
    }

    AI_MODEL_CONFIG = {
        "default_model": "claude-sonnet-4-6",
        "models": ["claude-sonnet-4-6", "gpt-4o", "qwen-plus"],
        "timeout": 60,
        "max_tokens": 4096,
    }

    # Deep/Quick/Routing LLM 分级策略
    LLM_TIERS = {
        "deep": {
            "description": "复杂推理：synthesis, judge, portfolio_manager",
            "temperature": 0.5,
            "max_tokens": 4096,
            "cost_multiplier": 1.0,
        },
        "quick": {
            "description": "例行分析：analyst agents, backtest",
            "temperature": 0.3,
            "max_tokens": 1024,
            "cost_multiplier": 0.15,
        },
        "routing": {
            "description": "分类决策：涨跌/买卖判断",
            "temperature": 0.1,
            "max_tokens": 256,
            "cost_multiplier": 0.05,
        },
    }

    # Agent → Tier 映射
    AGENT_TIER_MAP = {
        "portfolio_manager": "deep",
        "debate_judge": "deep",
        "research_manager": "deep",
        "market_analyst": "quick",
        "technical_analyst": "quick",
        "sentiment_analyst": "quick",
        "fund_analyst": "quick",
        "fundamental_analyst": "quick",
        "risk_analyst": "quick",
        "bull_analyst": "quick",
        "bear_analyst": "quick",
        "signal_classifier": "routing",
        "risk_level": "routing",
        "recommendation": "routing",
    }

    # 上下文压缩配置
    COMPRESSION_CONFIG = {
        "enabled": True,
        "threshold": 0.8,
        "max_tokens": 128000,
        "layer1_max_trim": 5000,
        "layer3_llm_model": "quick",
    }

    # 多智能体编排配置
    ORCHESTRATION_CONFIG = {
        "analyst_use_tools": True,   # 分析师工具增强(计划→取数→分析)总开关；关闭可省 LLM 调用
        "max_debate_rounds": 3,      # 多空辩论最大轮数
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