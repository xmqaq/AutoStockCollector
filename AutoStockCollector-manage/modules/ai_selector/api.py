"""
统一API接口
提供 HTTP + SDK 接口，供前端、回测、任务调度调用
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from utils.logger import get_logger


logger = get_logger(__name__)


class AISelectorAPI:
    def __init__(self):
        self._initialized = False
        self._init_components()

    def _init_components(self):
        if self._initialized:
            return

        from .strategies import (
            SentimentDrivenStrategy,
            FundFlowStrategy,
            ValueStrategy,
            SectorRotationStrategy
        )
        from .factors import factor_registry
        from .backtest import ai_backtest, SignalGenerator
        from .task import task_queue
        from .models import llm_router

        self.strategies = {
            "舆情情绪事件驱动": SentimentDrivenStrategy(),
            "资金异动主力跟踪": FundFlowStrategy(),
            "基本面价值选股": ValueStrategy(),
            "板块轮动题材选股": SectorRotationStrategy()
        }

        self.factor_registry = factor_registry
        self.backtest_engine = ai_backtest
        self.signal_generator = SignalGenerator
        self.task_queue = task_queue
        self.llm_router = llm_router

        self._initialized = True
        logger.info("AISelectorAPI initialized")

    def select(
        self,
        strategy: str,
        codes: Optional[List[str]] = None,
        top_n: int = 20,
        min_score: float = 60.0,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        if strategy not in self.strategies:
            return {"error": f"Unknown strategy: {strategy}"}

        if not codes:
            codes = self._get_default_codes(limit=kwargs.get("limit", 500))

        strategy_obj = self.strategies[strategy]

        try:
            results = strategy_obj.select(codes, top_n=top_n, min_score=min_score, **kwargs)

            return {
                "success": True,
                "strategy": strategy,
                "total_screened": len(codes),
                "selected_count": len(results),
                "results": [r.to_dict() for r in results],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Selection failed: {e}")
            return {"error": str(e), "success": False}

    def select_all(
        self,
        codes: Optional[List[str]] = None,
        min_score: float = 60.0,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        if not codes:
            codes = self._get_default_codes(limit=500)

        all_results = {}
        for name, strategy in self.strategies.items():
            try:
                results = strategy.select(codes, top_n=20, min_score=min_score, **kwargs)
                all_results[name] = [r.to_dict() for r in results]
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                all_results[name] = []

        return {
            "success": True,
            "total_screened": len(codes),
            "strategies": all_results,
            "timestamp": datetime.now().isoformat()
        }

    def analyze(
        self,
        code: str,
        analysis_type: str = "comprehensive",
        use_llm: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        from core.storage.mongo_storage import KlineStorage, StockInfoStorage, NewsStorage

        kline_storage = KlineStorage()
        info_storage = StockInfoStorage()
        news_storage = NewsStorage()

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )
        info = info_storage.get_by_code(code)
        news = news_storage.get_latest_news(code=code, limit=20)

        if analysis_type == "comprehensive":
            analysis = self._comprehensive_analysis(code, klines, info, news, use_llm)
        elif analysis_type == "technical":
            analysis = self._technical_analysis(klines)
        elif analysis_type == "fundamental":
            analysis = self._fundamental_analysis(info)
        elif analysis_type == "sentiment":
            analysis = self._sentiment_analysis(news)
        else:
            return {"error": f"Unknown analysis type: {analysis_type}"}

        analysis["success"] = True
        analysis["timestamp"] = datetime.now().isoformat()
        return analysis

    def _comprehensive_analysis(
        self,
        code: str,
        klines: List[Dict],
        info: Dict,
        news: List[Dict],
        use_llm: bool
    ) -> Dict[str, Any]:
        from .models import llm_router, StockSelectionSchema

        technical = self._technical_analysis(klines)
        fundamental = self._fundamental_analysis(info)
        sentiment = self._sentiment_analysis(news)

        result = {
            "code": code,
            "name": info.get("name", "") if info else "",
            "analysis_type": "comprehensive",
            "technical": technical,
            "fundamental": fundamental,
            "sentiment": sentiment
        }

        if use_llm:
            try:
                prompt = self._build_llm_prompt(code, technical, fundamental, sentiment)
                response = llm_router.chat(
                    prompt,
                    schema=StockSelectionSchema.get_selection_schema()
                )

                if response.success:
                    import json
                    result["llm_analysis"] = json.loads(response.content)
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")
                result["llm_analysis"] = None

        avg_score = (
            technical.get("score", 50) * 0.25 +
            fundamental.get("score", 50) * 0.25 +
            sentiment.get("score", 50) * 0.5
        )
        result["composite_score"] = round(avg_score, 2)

        return result

    def _technical_analysis(self, klines: List[Dict]) -> Dict[str, Any]:
        if not klines:
            return {"score": 50, "error": "No data"}

        import numpy as np

        closes = np.array([k.get("close", 0) for k in klines])
        volumes = np.array([k.get("volume", 0) for k in klines])

        current = closes[0]
        ma5 = np.mean(closes[:5]) if len(closes) >= 5 else current
        ma20 = np.mean(closes[:20]) if len(closes) >= 20 else current
        ma60 = np.mean(closes[:60]) if len(closes) >= 60 else current

        change_pct = 0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (current - closes[1]) / closes[1] * 100

        avg_vol = np.mean(volumes) if len(volumes) > 0 else 1
        vol_ratio = volumes[0] / avg_vol if avg_vol > 0 else 1

        score = 50.0
        if current > ma20:
            score += 15
        elif current < ma20:
            score -= 15

        if change_pct > 3:
            score += 10
        elif change_pct < -3:
            score -= 10

        if vol_ratio > 1.5:
            score += 10

        score = max(0, min(100, score))

        trend = "震荡"
        if current > ma20 > ma10 if len(closes) >= 10 else False:
            trend = "上升"
        elif current < ma20 < ma10 if len(closes) >= 10 else False:
            trend = "下降"

        return {
            "score": round(score, 2),
            "current_price": float(current),
            "ma5": float(ma5),
            "ma20": float(ma20),
            "ma60": float(ma60),
            "change_pct": round(change_pct, 2),
            "volume_ratio": round(vol_ratio, 2),
            "trend": trend
        }

    def _fundamental_analysis(self, info: Optional[Dict]) -> Dict[str, Any]:
        if not info:
            return {"score": 50, "error": "No data"}

        score = 50.0

        pe = info.get("pe") or 0
        if pe and 5 < pe < 25:
            score += 15

        pb = info.get("pb") or 0
        if pb and 0.5 < pb < 3:
            score += 10

        roe = info.get("roe") or 0
        if roe and roe > 15:
            score += 15

        score = max(0, min(100, score))

        return {
            "score": round(score, 2),
            "pe": float(pe) if pe else 0,
            "pb": float(pb) if pb else 0,
            "roe": float(roe) if roe else 0,
            "market_cap": info.get("market_cap", 0)
        }

    def _sentiment_analysis(self, news: List[Dict]) -> Dict[str, Any]:
        if not news:
            return {"score": 50, "sentiment": "neutral"}

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "风险"]

        positive = 0
        negative = 0

        for n in news:
            text = (n.get("title", "") + n.get("content", ""))
            for kw in positive_keywords:
                if kw in text:
                    positive += 1
                    break
            for kw in negative_keywords:
                if kw in text:
                    negative += 1
                    break

        total = positive + negative
        if total == 0:
            score = 50.0
        else:
            score = (positive / total) * 100

        sentiment = "neutral"
        if score > 65:
            sentiment = "positive"
        elif score < 35:
            sentiment = "negative"

        return {
            "score": round(score, 2),
            "sentiment": sentiment,
            "positive_count": positive,
            "negative_count": negative,
            "news_count": len(news)
        }

    def _build_llm_prompt(self, code: str, technical: Dict, fundamental: Dict, sentiment: Dict) -> str:
        return f"""分析股票 {code} 的综合投资价值。

技术面：
- 评分：{technical.get('score', 50)}
- 趋势：{technical.get('trend', '震荡')}
- 涨跌幅：{technical.get('change_pct', 0)}%
- 成交量比：{technical.get('volume_ratio', 1)}倍

基本面：
- 评分：{fundamental.get('score', 50)}
- PE：{fundamental.get('pe', 0)}
- ROE：{fundamental.get('roe', 0)}%

舆情：
- 评分：{sentiment.get('score', 50)}
- 情绪：{sentiment.get('sentiment', 'neutral')}
- 新闻数：{sentiment.get('news_count', 0)}

请输出JSON：
{{"score": 0-100, "recommendation": "强烈推荐/买入/观望/回避", "reasons": [], "risk_factors": [], "stop_loss": 0, "target_price": 0}}"""

    def backtest(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        signal_type: str = "ma_cross",
        initial_cash: float = 1000000,
        **kwargs
    ) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        signal_funcs = {
            "ma_cross": self.signal_generator.ma_cross_signals,
            "momentum": self.signal_generator.momentum_signals,
            "rsi": self.signal_generator.rsi_signals,
            "volume": self.signal_generator.volume_breakout_signals
        }

        signal_func = signal_funcs.get(signal_type, self.signal_generator.ma_cross_signals)

        try:
            result = self.backtest_engine.backtest_strategy(
                codes=codes,
                signals_func=signal_func,
                start_date=start_date,
                end_date=end_date,
                **kwargs
            )

            result["success"] = True
            result["signal_type"] = signal_type
            result["timestamp"] = datetime.now().isoformat()
            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return {"error": str(e), "success": False}

    def submit_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        callback: Optional[callable] = None
    ) -> str:
        if not self._initialized:
            self._init_components()

        task_id = self.task_queue.submit(task_type, params, callback)
        return task_id

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        task = self.task_queue.get_task(task_id)
        if not task:
            return {"error": "Task not found"}

        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "progress": task.progress,
            "completed": task.completed,
            "failed": task.failed,
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._initialized:
            self._init_components()

        from .task import TaskStatus
        status_enum = TaskStatus[status.upper()] if status else None
        return self.task_queue.list_tasks(status_enum)

    def get_model_stats(self) -> Dict[str, Any]:
        if not self._initialized:
            self._init_components()

        return self.llm_router.get_stats()

    def _get_default_codes(self, limit: int = 500) -> List[str]:
        from core.storage.mongo_storage import KlineStorage

        kline_storage = KlineStorage()
        klines = kline_storage.find_many(
            {},
            projection={"code": 1},
            limit=limit
        )

        return list({k.get("code") for k in klines if k.get("code")})


aiselector_api = AISelectorAPI()