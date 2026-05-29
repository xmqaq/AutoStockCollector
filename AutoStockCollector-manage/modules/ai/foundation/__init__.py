"""AI 一体化体系底座层：因子引擎 / 数据访问层 / LLM 路由"""
from modules.ai.foundation import factors
from modules.ai.foundation.dal import StockDAL, StockDataBundle
from modules.ai.foundation.llm_router import LLMRouter, LLMResult

__all__ = ["factors", "StockDAL", "StockDataBundle", "LLMRouter", "LLMResult"]
