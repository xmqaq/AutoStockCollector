"""LLM 预测 — 盘中对池中股票调 LLM 生成买卖建议，与规则 decider 并列。

复用 ai_advanced._fetch_all_stock_data（采集 K线/资金流/新闻/财务）+
_calculate_debate_factors（量化因子）+ _format_stock_data_text（格式化上下文），
单轮 LLMRouter.chat_quick 出建议（不走 6 分析师辩论，省成本）。
结果存 monitor_signals.trading_advice.ai_advice（与规则 advice 并列，不覆盖）。

控成本：① 当日同股缓存（同股同日不重复调 LLM）；② 每日调用 limit 计数；
③ 仅异动/开盘/收盘触发，非每只都跑。
"""
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from config.database import DatabaseConfig
from utils.helpers import beijing_now
from utils.logger import get_logger

from .storage import MonitorStorage

logger = get_logger(__name__)

# 每日 LLM 预测调用上限（控成本）
_DAILY_LIMIT = 30
_AI_CACHE_COL = "monitor_ai_advice_cache"  # 当日同股缓存


class LLMAiAdvisor:
    """LLM 买卖建议预测器。"""

    def __init__(self):
        self._storage = MonitorStorage()
        self._db = DatabaseConfig.get_database()

    def predict(self, code: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """对单只股票生成 LLM 买卖建议。force=True 跳过当日缓存（仍受 limit 约束）。"""
        today = beijing_now().strftime("%Y-%m-%d")

        # 当日同股缓存命中则直接返回（控成本）
        if not force:
            cached = self._load_cache(code, today)
            if cached:
                return cached

        # 每日 limit 检查
        if not force and self._today_count(today) >= _DAILY_LIMIT:
            logger.info(f"[AiAdvisor] daily limit reached ({_DAILY_LIMIT}), skip {code}")
            return None

        try:
            from api.routes.ai_advanced import (
                _fetch_all_stock_data, _calculate_debate_factors, _format_stock_data_text,
            )
            from modules.ai.foundation.llm_router import LLMRouter
        except Exception as e:
            logger.error(f"[AiAdvisor] import ai_advanced/llm_router failed: {e}")
            return None

        try:
            data = _fetch_all_stock_data(code)
            factors = _calculate_debate_factors(data)
            context = _format_stock_data_text(data)
        except Exception as e:
            logger.warning(f"[AiAdvisor] fetch data for {code} failed: {e}")
            return None

        prompt = self._build_prompt(code, context, factors)
        schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["买入", "加仓", "减仓", "卖出", "持有", "观望"]},
                "confidence": {"type": "number"},
                "target_price": {"type": "number"},
                "stop_loss": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["action", "confidence", "reason"],
        }

        try:
            router = LLMRouter()
            result = router.chat_quick(prompt, schema=schema)
            if not result.success or not result.data:
                logger.info(f"[AiAdvisor] LLM no result for {code}")
                return None
            advice = self._parse_advice(result.data)
        except Exception as e:
            logger.warning(f"[AiAdvisor] LLM predict {code} failed: {e}")
            return None

        advice["predicted_at"] = beijing_now().isoformat()
        advice["code"] = code
        self._save_cache(code, today, advice)
        # 写入 monitor_signals.trading_advice.ai_advice（与规则 advice 并列）
        self._db[MonitorStorage.SIGNALS_COL].update_one(
            {"code": code},
            {"$set": {"trading_advice.ai_advice": advice}},
        )
        logger.info(f"[AiAdvisor] predicted {code}: {advice.get('action')} conf={advice.get('confidence')}")
        return advice

    def predict_pool(self, codes: list, trigger: str = "") -> Dict[str, Any]:
        """对池中股票批量预测（按触发条件筛选）。trigger: anomaly/open/close/Manual。"""
        done = 0
        for code in codes:
            r = self.predict(code)
            if r:
                done += 1
        return {"trigger": trigger, "predicted": done, "total": len(codes)}

    def _build_prompt(self, code: str, context: str, factors: Dict) -> str:
        factor_text = "\n".join(f"- {k}: {v}" for k, v in (factors or {}).items()
                                if not isinstance(v, (dict, list)))[:15]
        return f"""你是 A 股短线交易顾问。基于以下实时数据与量化因子，给出明确的买卖建议。

股票代码：{code}

【量化因子】
{factor_text or '无'}

【数据上下文】
{context[:2000]}

请输出 JSON：action(买入/加仓/减仓/卖出/持有/观望)、confidence(0-1)、target_price(目标价,可填0)、stop_loss(止损价,可填0)、reason(一句话理由,不超过50字)。"""

    def _parse_advice(self, data: Dict) -> Dict[str, Any]:
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0
        return {
            "action": str(data.get("action", "观望")),
            "confidence": round(_num(data.get("confidence")), 2),
            "target_price": round(_num(data.get("target_price")), 2),
            "stop_loss": round(_num(data.get("stop_loss")), 2),
            "reason": str(data.get("reason", ""))[:100],
        }

    # ── 当日缓存 + 计数 ──

    def _cache_key(self, code: str, today: str) -> str:
        return hashlib.md5(f"{code}|{today}".encode()).hexdigest()

    def _load_cache(self, code: str, today: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self._db[_AI_CACHE_COL].find_one(
                {"code": code, "date": today}, {"advice": 1, "_id": 0})
            return doc.get("advice") if doc else None
        except Exception:
            return None

    def _save_cache(self, code: str, today: str, advice: Dict) -> None:
        try:
            self._db[_AI_CACHE_COL].update_one(
                {"code": code, "date": today},
                {"$set": {"code": code, "date": today, "advice": advice,
                          "saved_at": datetime.now().isoformat()}},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[AiAdvisor] save cache failed: {e}")

    def _today_count(self, today: str) -> int:
        try:
            return self._db[_AI_CACHE_COL].count_documents({"date": today})
        except Exception:
            return 0
