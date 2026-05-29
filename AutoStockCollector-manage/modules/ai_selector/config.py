"""
配置模块
"""
from typing import Dict, Any
import os


class AIConfig:
    MODEL_CONFIG: Dict[str, Any] = {
        "default_model": os.getenv("AI_DEFAULT_MODEL", "claude"),
        "claude_model": os.getenv("AI_CLAUDE_MODEL", "claude-sonnet-4-6"),
        "openai_model": os.getenv("AI_OPENAI_MODEL", "gpt-4o"),
        "qwen_model": os.getenv("AI_QWEN_MODEL", "qwen-plus"),
        "timeout": 60,
        "max_tokens": 4096,
        "hourly_limit": 100,
        "daily_limit": 1000,
    }

    SELECTION_CONFIG: Dict[str, Any] = {
        "default_top_n": 20,
        "default_min_score": 60.0,
        "max_stocks_per_strategy": 50,
        "cache_ttl_seconds": 3600,
    }

    BACKTEST_CONFIG: Dict[str, Any] = {
        "initial_cash": 1000000,
        "commission": 0.001,
        "slippage": 0.001,
        "stop_loss": 0.05,
        "take_profit": 0.10,
        "max_position": 0.20,
        "min_position": 0.02,
    }

    TASK_CONFIG: Dict[str, Any] = {
        "max_workers": 3,
        "queue_size": 1000,
        "task_timeout_seconds": 3600,
    }

    FACTOR_WEIGHTS: Dict[str, float] = {
        "technical": 0.25,
        "fundamental": 0.25,
        "sentiment": 0.25,
        "fund_flow": 0.25,
    }

    STRATEGY_CONFIGS: Dict[str, Dict[str, Any]] = {
        "舆情情绪事件驱动": {
            "min_score": 60.0,
            "max_stocks": 20,
            "weights": {"sentiment": 0.7, "technical": 0.3}
        },
        "资金异动主力跟踪": {
            "min_score": 65.0,
            "max_stocks": 20,
            "weights": {"fund_flow": 0.6, "technical": 0.4}
        },
        "基本面价值选股": {
            "min_score": 55.0,
            "max_stocks": 20,
            "weights": {"fundamental": 1.0}
        },
        "板块轮动题材选股": {
            "min_score": 60.0,
            "max_stocks": 20,
            "weights": {"technical": 0.7, "sector": 0.3}
        },
        "技术+资金融合趋势": {
            "min_score": 65.0,
            "max_stocks": 20,
            "weights": {"technical": 0.5, "fund_flow": 0.5}
        },
        "低风险反转套利": {
            "min_score": 55.0,
            "max_stocks": 15,
            "weights": {"technical": 0.4, "reversal": 0.6}
        },
        "自选股精细化优选": {
            "min_score": 50.0,
            "max_stocks": 10,
            "weights": {"comprehensive": 1.0}
        },
    }


ai_config = AIConfig()