"""
量化选股策略管理器 - 工业化重构版
对接ai_selector因子层 + 标准化策略接口
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
from utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class StrategyResult:
    code: str
    name: str
    score: float
    technical_score: float
    fundamental_score: float
    sentiment_score: float
    fund_flow_score: float
    recommendation: str
    risk_level: str
    stop_loss: float
    target_price: float
    strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "score": round(self.score, 2),
            "technical_score": round(self.technical_score, 2),
            "fundamental_score": round(self.fundamental_score, 2),
            "sentiment_score": round(self.sentiment_score, 2),
            "fund_flow_score": round(self.fund_flow_score, 2),
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
            "stop_loss": round(self.stop_loss, 2),
            "target_price": round(self.target_price, 2),
            "strategy": self.strategy,
            "metadata": self.metadata
        }


class BaseStrategy(ABC):
    def __init__(
        self,
        name: str,
        description: str = "",
        min_score: float = 60.0,
        max_stocks: int = 20
    ):
        self.name = name
        self.description = description
        self.min_score = min_score
        self.max_stocks = max_stocks
        self._weights = {
            "technical": 0.25,
            "fundamental": 0.25,
            "sentiment": 0.25,
            "fund_flow": 0.25
        }

    def set_weights(self, weights: Dict[str, float]):
        self._weights.update(weights)

    @abstractmethod
    def calculate_scores(self, code: str) -> Dict[str, float]:
        pass

    def select(
        self,
        codes: List[str],
        top_n: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> List[StrategyResult]:
        if top_n is None:
            top_n = self.max_stocks
        if min_score is None:
            min_score = self.min_score

        results = []
        for code in codes:
            try:
                scores = self.calculate_scores(code)
                total_score = self._compute_weighted_score(scores)

                if total_score >= min_score:
                    result = self._build_result(code, scores, total_score)
                    results.append(result)
            except Exception as e:
                logger.error(f"Strategy {self.name} failed for {code}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]

    def _compute_weighted_score(self, scores: Dict[str, float]) -> float:
        total = 0.0
        for key, weight in self._weights.items():
            total += scores.get(key, 50) * weight
        return max(0, min(100, total))

    def _build_result(
        self,
        code: str,
        scores: Dict[str, float],
        total_score: float
    ) -> StrategyResult:
        from core.storage.mongo_storage import StockInfoStorage

        info_storage = StockInfoStorage()
        info = info_storage.get_by_code(code)
        name = info.get("name", "") if info else ""

        current_price = scores.get("current_price", 0)
        stop_loss = current_price * 0.95 if current_price > 0 else 0
        target_price = current_price * 1.15 if current_price > 0 else 0

        recommendation = "观望"
        risk_level = "中"

        if total_score >= 75:
            recommendation = "强烈推荐"
            risk_level = "低"
        elif total_score >= 65:
            recommendation = "买入"
            risk_level = "中"
        elif total_score >= 55:
            recommendation = "谨慎买入"
            risk_level = "中"
        elif total_score <= 35:
            recommendation = "回避"
            risk_level = "高"

        return StrategyResult(
            code=code,
            name=name,
            score=total_score,
            technical_score=scores.get("technical", 50),
            fundamental_score=scores.get("fundamental", 50),
            sentiment_score=scores.get("sentiment", 50),
            fund_flow_score=scores.get("fund_flow", 50),
            recommendation=recommendation,
            risk_level=risk_level,
            stop_loss=stop_loss,
            target_price=target_price,
            strategy=self.name,
            metadata=scores
        )


class SentimentDrivenStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="舆情情绪事件驱动",
            description="基于舆情情绪事件驱动选股",
            min_score=60.0,
            max_stocks=20
        )
        self._weights = {"sentiment": 0.7, "technical": 0.3}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, NewsStorage
        from modules.ai.ai_analyzer import ai_analyzer

        kline_storage = KlineStorage()
        news_storage = NewsStorage()

        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=10
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]
            scores["current_price"] = current

            if len(closes) >= 2 and closes[1] > 0:
                change_pct = (current - closes[1]) / closes[1] * 100
                scores["change_pct"] = change_pct
                scores["technical"] = 50 + min(20, change_pct * 3) if change_pct > 0 else max(0, 50 + change_pct * 3)

        news = news_storage.get_latest_news(code=code, limit=20)
        scores["sentiment"] = self._calculate_sentiment(news)

        return scores

    def _calculate_sentiment(self, news: List[Dict]) -> float:
        if not news:
            return 50.0

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作", "扩张"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "诉讼"]

        positive_count = sum(1 for n in news if any(kw in (n.get("title", "") + n.get("content", "")) for kw in positive_keywords))
        negative_count = sum(1 for n in news if any(kw in (n.get("title", "") + n.get("content", "")) for kw in negative_keywords))

        total = positive_count + negative_count
        if total == 0:
            return 50.0

        return (positive_count / total) * 100


class FundFlowStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="资金异动主力跟踪",
            description="基于资金异动主力跟踪选股",
            min_score=65.0,
            max_stocks=20
        )
        self._weights = {"fund_flow": 0.6, "technical": 0.4}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, FundFlowStorage
        import numpy as np

        kline_storage = KlineStorage()
        flow_storage = FundFlowStorage()

        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            volumes = [k.get("volume", 0) for k in klines]
            current = closes[0]

            scores["current_price"] = current
            ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current
            scores["trend"] = 1 if current > ma20 else -1

            avg_vol = np.mean(volumes[1:]) if len(volumes) > 1 else volumes[0]
            vol_ratio = volumes[0] / avg_vol if avg_vol > 0 else 1.0
            scores["volume_ratio"] = vol_ratio

            tech_score = 50
            if scores["trend"] > 0:
                tech_score += 15
            if vol_ratio > 1.5:
                tech_score += 15
            scores["technical"] = max(0, min(100, tech_score))

        flow = flow_storage.get_latest_flow(code)
        if flow:
            main_inflow = flow.get("main_net_inflow", 0)
            if main_inflow > 1e8:
                scores["fund_flow"] = 85
            elif main_inflow > 5e7:
                scores["fund_flow"] = 75
            elif main_inflow > 1e7:
                scores["fund_flow"] = 65
            elif main_inflow > 0:
                scores["fund_flow"] = 55
            else:
                scores["fund_flow"] = 40

        return scores


class ValueStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="基本面价值选股",
            description="基于基本面价值选股",
            min_score=55.0,
            max_stocks=20
        )
        self._weights = {"fundamental": 1.0}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import StockInfoStorage

        info_storage = StockInfoStorage()
        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        info = info_storage.get_by_code(code)
        if info:
            scores["current_price"] = info.get("close", 0)

            pe = info.get("pe") or 0
            pb = info.get("pb") or 0
            roe = info.get("roe") or 0

            val_score = 50.0
            if pe and 5 < pe < 25:
                val_score += 15
            if pb and 0.5 < pb < 3:
                val_score += 10
            if roe and roe > 15:
                val_score += 15

            scores["fundamental"] = max(0, min(100, val_score))
            scores["pe"] = pe
            scores["pb"] = pb
            scores["roe"] = roe

        return scores


class SectorRotationStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="板块轮动题材选股",
            description="基于板块轮动题材选股",
            min_score=60.0,
            max_stocks=20
        )
        self._weights = {"technical": 0.7, "sector": 0.3}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage
        from core.collector.fund_flow_collector import BlockCollector

        kline_storage = KlineStorage()
        info_storage = StockInfoStorage()
        block_collector = BlockCollector()

        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=20
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]
            scores["current_price"] = current

            ma10 = sum(closes[:10]) / 10 if len(closes) >= 10 else current
            recent_change = sum((closes[i] - closes[i+1]) / closes[i+1] * 100 for i in range(min(5, len(closes)-1)) if closes[i+1] > 0)
            scores["technical"] = max(0, min(100, 50 + recent_change * 2))

        info = info_storage.get_by_code(code)
        industry = info.get("industry", "") if info else ""

        hot_blocks = block_collector.collect_hot_blocks() or []
        sector_score = 30
        for block in hot_blocks[:10]:
            block_name = block.get("name", "")
            if block_name and (industry in block_name or block_name in industry):
                rank = block.get("rank", 50)
                sector_score = max(0, 100 - rank * 5)
                break

        scores["sector_score"] = sector_score

        return scores


class TechFundFusionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="技术+资金融合趋势",
            description="技术+资金融合趋势选股",
            min_score=65.0,
            max_stocks=20
        )
        self._weights = {"technical": 0.5, "fund_flow": 0.5}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, FundFlowStorage

        kline_storage = KlineStorage()
        flow_storage = FundFlowStorage()

        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]
            scores["current_price"] = current

            ma10 = sum(closes[:10]) / 10
            ma20 = sum(closes[:20]) / 20

            tech_score = 50
            if current > ma10 > ma20:
                tech_score = 80
            elif current < ma10 < ma20:
                tech_score = 30
            scores["technical"] = tech_score

        flow = flow_storage.get_latest_flow(code)
        if flow:
            main_inflow = flow.get("main_net_inflow", 0)
            scores["fund_flow"] = min(100, 50 + main_inflow / 1e7) if main_inflow > 0 else max(0, 50 + main_inflow / 1e7)

        return scores


class LowRiskReversalStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="低风险反转套利",
            description="低风险反转套利选股",
            min_score=55.0,
            max_stocks=15
        )
        self._weights = {"technical": 0.4, "reversal": 0.6}

    def calculate_scores(self, code: str) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage
        import numpy as np

        kline_storage = KlineStorage()
        scores = {"technical": 50, "fundamental": 50, "sentiment": 50, "fund_flow": 50}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=30
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            current = closes[0]
            scores["current_price"] = current

            ma20 = sum(closes[:20]) / 20

            oversold_score = 50
            if current < ma20 * 0.9:
                oversold_score = min(100, 50 + (ma20 * 0.9 - current) / ma20 * 500)

            recovery_score = 50
            if len(closes) >= 4:
                recent_up = sum(1 for i in range(3) if closes[i] > closes[i+1])
                if recent_up >= 3:
                    recovery_score = 80

            scores["reversal_score"] = oversold_score * 0.4 + recovery_score * 0.6
            scores["technical"] = scores["reversal_score"]

        return scores


class StrategyManager:
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {
            "舆情情绪事件驱动": SentimentDrivenStrategy(),
            "资金异动主力跟踪": FundFlowStrategy(),
            "基本面价值选股": ValueStrategy(),
            "板块轮动题材选股": SectorRotationStrategy(),
            "技术+资金融合趋势": TechFundFusionStrategy(),
            "低风险反转套利": LowRiskReversalStrategy(),
        }

    def list_strategies(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": strategy.description,
                "min_score": strategy.min_score,
                "max_stocks": strategy.max_stocks,
                "weights": strategy._weights
            }
            for name, strategy in self._strategies.items()
        ]

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(name)

    def run_strategy(
        self,
        strategy_name: str,
        codes: List[str],
        top_n: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_name}")

        results = strategy.select(codes, top_n=top_n, min_score=min_score)
        return [r.to_dict() for r in results]

    def run_all_strategies(
        self,
        codes: List[str],
        min_score: float = 60
    ) -> Dict[str, List[Dict[str, Any]]]:
        results = {}

        for name, strategy in self._strategies.items():
            try:
                strategy_results = strategy.select(codes, min_score=min_score)
                results[name] = [r.to_dict() for r in strategy_results]
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                results[name] = []

        return results

    def run_combined(
        self,
        codes: List[str],
        strategy_names: List[str],
        combination_type: str = "weighted",
        min_score: float = 60.0
    ) -> List[Dict[str, Any]]:
        all_results: Dict[str, List[Dict[str, Any]]] = {}

        for name in strategy_names:
            strategy = self._strategies.get(name)
            if strategy:
                try:
                    all_results[name] = strategy.select(codes)
                except Exception as e:
                    logger.error(f"Strategy {name} failed: {e}")

        combined_scores: Dict[str, Dict[str, Any]] = {}

        for name, results in all_results.items():
            for r in results:
                code = r.code
                if code not in combined_scores:
                    combined_scores[code] = {
                        "code": code,
                        "name": r.name,
                        "scores": {},
                        "count": 0
                    }
                combined_scores[code]["scores"][name] = r.score
                combined_scores[code]["count"] += 1

        final_results = []
        strategy_weights = {
            "舆情情绪事件驱动": 0.15,
            "资金异动主力跟踪": 0.20,
            "基本面价值选股": 0.20,
            "板块轮动题材选股": 0.15,
            "技术+资金融合趋势": 0.15,
            "低风险反转套利": 0.10,
        }

        for code, data in combined_scores.items():
            if combination_type == "intersection":
                if data["count"] >= len(strategy_names) * 0.5:
                    avg_score = sum(data["scores"].values()) / data["count"]
                    if avg_score >= min_score:
                        final_results.append({
                            "code": code,
                            "name": data["name"],
                            "score": round(avg_score, 2),
                            "strategies_count": data["count"]
                        })
            elif combination_type == "weighted":
                total_weighted = 0.0
                total_weight = 0.0
                for strat_name, score in data["scores"].items():
                    weight = strategy_weights.get(strat_name, 0.1)
                    total_weighted += score * weight
                    total_weight += weight
                if total_weight > 0:
                    weighted_score = total_weighted / total_weight
                    if weighted_score >= min_score:
                        final_results.append({
                            "code": code,
                            "name": data["name"],
                            "score": round(weighted_score, 2),
                            "strategies_count": data["count"]
                        })
            elif combination_type == "union":
                max_score = max(data["scores"].values()) if data["scores"] else 0
                if max_score >= min_score:
                    final_results.append({
                        "code": code,
                        "name": data["name"],
                        "score": round(max_score, 2),
                        "strategies_count": data["count"]
                    })

        final_results.sort(key=lambda x: x["score"], reverse=True)
        return final_results


strategy_manager = StrategyManager()


class SceneAdaptiveManager:
    def __init__(self):
        self.kline_storage = None
        self._init_storage()

    def _init_storage(self):
        from core.storage.mongo_storage import KlineStorage
        self.kline_storage = KlineStorage()

    def detect_market_scene(self) -> str:
        try:
            klines = self.kline_storage.find_many(
                {"code": "SH000001"},
                sort=[("date", -1)],
                limit=30
            )

            if len(klines) < 20:
                return "consolidation"

            closes = [k.get("close", 0) for k in klines]
            ma20 = sum(closes[:20]) / 20
            ma60 = sum(closes[:60]) / min(60, len(closes))
            current = closes[0]

            if current > ma20 > ma60:
                return "bull"
            elif current < ma20 < ma60:
                return "bear"
            else:
                return "consolidation"

        except Exception as e:
            logger.error(f"Scene detection error: {e}")
            return "consolidation"

    def get_scene_config(self, scene: str) -> Dict[str, Any]:
        configs = {
            "bull": {
                "name": "牛市",
                "threshold_multiplier": 0.9,
                "max_stocks": 15,
                "stop_loss": 0.07,
                "take_profit": 0.15,
                "preferred_strategies": ["资金异动主力跟踪", "技术+资金融合趋势"]
            },
            "bear": {
                "name": "熊市",
                "threshold_multiplier": 1.2,
                "max_stocks": 5,
                "stop_loss": 0.05,
                "take_profit": 0.08,
                "preferred_strategies": ["低风险反转套利", "基本面价值选股"]
            },
            "consolidation": {
                "name": "震荡市",
                "threshold_multiplier": 1.0,
                "max_stocks": 10,
                "stop_loss": 0.06,
                "take_profit": 0.10,
                "preferred_strategies": ["舆情情绪事件驱动", "板块轮动题材选股"]
            }
        }
        return configs.get(scene, configs["consolidation"])

    def run_adaptive(
        self,
        codes: List[str],
        min_score: float = 60.0
    ) -> Dict[str, Any]:
        scene = self.detect_market_scene()
        config = self.get_scene_config(scene)

        adjusted_min_score = min_score * config["threshold_multiplier"]

        results = {}
        for strat_name in config["preferred_strategies"]:
            try:
                strategy = strategy_manager.get_strategy(strat_name)
                if strategy:
                    strat_results = strategy.select(codes, top_n=config["max_stocks"], min_score=adjusted_min_score)
                    results[strat_name] = [r.to_dict() for r in strat_results]
            except Exception as e:
                logger.error(f"Strategy {strat_name} failed in adaptive mode: {e}")

        return {
            "scene": scene,
            "scene_config": config,
            "adjusted_min_score": round(adjusted_min_score, 1),
            "strategy_results": results,
            "timestamp": datetime.now().isoformat()
        }


scene_adaptive_manager = SceneAdaptiveManager()