"""
策略基类与流水线抽象
提供标准化选股流水线接口：过滤 → 打分 → 排序 → 组合 → 风控
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import json
from utils.logger import get_logger


logger = get_logger(__name__)


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MarketPhase(Enum):
    BULL = "bull"
    BEAR = "bear"
    CONSOLIDATION = "consolidation"


@dataclass
class SelectionResult:
    code: str
    name: str
    score: float
    technical_score: float = 0.0
    fundamental_score: float = 0.0
    sentiment_score: float = 0.0
    fund_flow_score: float = 0.0
    recommendation: str = "观望"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    stop_loss: float = 0.0
    target_price: float = 0.0
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    position_ratio: float = 0.0
    strategy: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "score": self.score,
            "technical_score": self.technical_score,
            "fundamental_score": self.fundamental_score,
            "sentiment_score": self.sentiment_score,
            "fund_flow_score": self.fund_flow_score,
            "recommendation": self.recommendation,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "risk_factors": self.risk_factors,
            "position_ratio": self.position_ratio,
            "strategy": self.strategy,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class BaseStrategy(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.min_score = 60.0
        self.max_stocks = 20
        self._filters: List[Callable] = []

    def add_filter(self, filter_func: Callable) -> None:
        self._filters.append(filter_func)

    def remove_filter(self, filter_func: Callable) -> None:
        if filter_func in self._filters:
            self._filters.remove(filter_func)

    def _apply_filters(self, code: str, stock_info: Dict[str, Any]) -> bool:
        for f in self._filters:
            try:
                if not f(code, stock_info):
                    return False
            except Exception as e:
                logger.warning(f"Filter failed for {code}: {e}")
                return False
        return True

    @abstractmethod
    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        pass

    @abstractmethod
    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        pass

    @abstractmethod
    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        pass

    def select(
        self,
        codes: List[str],
        top_n: Optional[int] = None,
        min_score: Optional[float] = None,
        **kwargs
    ) -> List[SelectionResult]:
        if top_n is None:
            top_n = self.max_stocks
        if min_score is None:
            min_score = self.min_score

        filtered = self.filter_pool(codes, **kwargs)
        logger.info(f"Strategy {self.name}: filtered {len(codes)} → {len(filtered)}")

        results = []
        for code in filtered:
            try:
                factors = self.calculate_factors(code, **kwargs)
                score = self.score(code, factors, **kwargs)

                if score >= min_score:
                    result = self._build_result(code, factors, score, **kwargs)
                    results.append(result)
            except Exception as e:
                logger.error(f"Selection failed for {code}: {e}")

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]

    def _build_result(
        self,
        code: str,
        factors: Dict[str, float],
        score: float,
        **kwargs
    ) -> SelectionResult:
        current_price = factors.get("current_price", 0)

        recommendation = "观望"
        risk_level = RiskLevel.MEDIUM

        if score >= 75:
            recommendation = "强烈推荐"
            risk_level = RiskLevel.LOW
        elif score >= 65:
            recommendation = "买入"
            risk_level = RiskLevel.MEDIUM
        elif score >= 55:
            recommendation = "谨慎买入"
            risk_level = RiskLevel.MEDIUM
        elif score <= 35:
            recommendation = "回避"
            risk_level = RiskLevel.HIGH

        stop_loss = current_price * 0.95 if current_price > 0 else 0
        target_price = current_price * 1.15 if current_price > 0 else 0

        return SelectionResult(
            code=code,
            name=factors.get("name", ""),
            score=score,
            technical_score=factors.get("technical_score", 50.0),
            fundamental_score=factors.get("fundamental_score", 50.0),
            sentiment_score=factors.get("sentiment_score", 50.0),
            fund_flow_score=factors.get("fund_flow_score", 50.0),
            recommendation=recommendation,
            risk_level=risk_level,
            stop_loss=stop_loss,
            target_price=target_price,
            support_levels=[stop_loss],
            resistance_levels=[target_price],
            risk_factors=[],
            strategy=self.name
        )


class PipelineStrategy(BaseStrategy):
    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self._stage_filters: List[Callable] = []
        self._stage_scorers: List[Callable] = []

    def add_stage(self, stage_func: Callable, stage_type: str = "scorer") -> None:
        if stage_type == "filter":
            self._stage_filters.append(stage_func)
        else:
            self._stage_scorers.append(stage_func)

    def filter_pool(self, codes: List[str], **kwargs) -> List[str]:
        from core.storage.mongo_storage import StockInfoStorage

        info_storage = StockInfoStorage()
        filtered = []

        for code in codes:
            info = info_storage.get_by_code(code)
            if not info:
                continue

            name = info.get("name", "")
            if any(name.startswith(p) for p in ["*ST", "ST", "PT", "退市"]):
                continue

            status = info.get("status", "")
            if status in ("退市", "delisted"):
                continue

            if not self._apply_filters(code, info):
                continue

            for f in self._stage_filters:
                try:
                    if not f(code, info, **kwargs):
                        break
                except:
                    continue
            else:
                filtered.append(code)

        return filtered

    def calculate_factors(self, code: str, **kwargs) -> Dict[str, float]:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage, FundFlowStorage, NewsStorage

        kline_storage = KlineStorage()
        info_storage = StockInfoStorage()
        flow_storage = FundFlowStorage()
        news_storage = NewsStorage()

        factors = {}

        klines = kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=60
        )

        if klines:
            closes = [k.get("close", 0) for k in klines]
            volumes = [k.get("volume", 0) for k in klines]
            current = closes[0]

            ma5 = sum(closes[:5]) / 5 if len(closes) >= 5 else current
            ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else current

            factors["current_price"] = current
            factors["ma5"] = ma5
            factors["ma20"] = ma20
            factors["trend"] = 1 if current > ma20 else -1

            if len(closes) >= 2 and closes[1] > 0:
                factors["change_pct"] = (current - closes[1]) / closes[1] * 100
            else:
                factors["change_pct"] = 0

            avg_vol = sum(volumes) / len(volumes) if volumes else 1
            factors["volume_ratio"] = volumes[0] / avg_vol if avg_vol > 0 else 1

            factors["technical_score"] = self._calculate_technical_score(factors)

        info = info_storage.get_by_code(code)
        if info:
            factors["name"] = info.get("name", "")
            factors["pe"] = info.get("pe", 0) or 0
            factors["pb"] = info.get("pb", 0) or 0
            factors["fundamental_score"] = self._calculate_fundamental_score(info)
        else:
            factors["name"] = ""
            factors["pe"] = 0
            factors["pb"] = 0
            factors["fundamental_score"] = 50.0

        flow = flow_storage.get_latest_flow(code)
        if flow:
            main_inflow = flow.get("main_net_inflow", 0)
            factors["main_inflow"] = main_inflow
            factors["fund_flow_score"] = min(100, 50 + main_inflow / 1e7) if main_inflow > 0 else max(0, 50 + main_inflow / 1e7)
        else:
            factors["main_inflow"] = 0
            factors["fund_flow_score"] = 50.0

        news = news_storage.get_latest_news(code=code, limit=20)
        factors["sentiment_score"] = self._calculate_sentiment_score(news)

        return factors

    def _calculate_technical_score(self, factors: Dict[str, float]) -> float:
        score = 50.0

        if factors.get("trend", 0) > 0:
            score += 15
        else:
            score -= 15

        change_pct = factors.get("change_pct", 0)
        if change_pct > 3:
            score += 10
        elif change_pct < -3:
            score -= 10

        vol_ratio = factors.get("volume_ratio", 1)
        if vol_ratio > 1.5:
            score += 10
        elif vol_ratio < 0.7:
            score -= 5

        return max(0, min(100, score))

    def _calculate_fundamental_score(self, info: Dict[str, Any]) -> float:
        score = 50.0

        pe = info.get("pe") or 0
        if pe and 5 < pe < 25:
            score += 15

        pb = info.get("pb") or 0
        if pb and 0.5 < pb < 3:
            score += 10

        return max(0, min(100, score))

    def _calculate_sentiment_score(self, news: List[Dict[str, Any]]) -> float:
        if not news:
            return 50.0

        positive_keywords = ["增长", "盈利", "突破", "利好", "创新", "合作"]
        negative_keywords = ["亏损", "下跌", "减持", "利空", "违规", "风险"]

        positive_count = 0
        negative_count = 0

        for n in news:
            text = (n.get("title", "") + n.get("content", ""))
            for kw in positive_keywords:
                if kw in text:
                    positive_count += 1
                    break
            for kw in negative_keywords:
                if kw in text:
                    negative_count += 1
                    break

        total = positive_count + negative_count
        if total == 0:
            return 50.0

        return (positive_count / total) * 100

    def score(self, code: str, factors: Dict[str, float], **kwargs) -> float:
        weights = kwargs.get("weights", {
            "technical": 0.25,
            "fundamental": 0.25,
            "sentiment": 0.25,
            "fund_flow": 0.25
        })

        total_score = 0.0
        total_weight = 0.0

        for stage_func in self._stage_scorers:
            try:
                stage_score = stage_func(code, factors, **kwargs)
                total_score += stage_score
                total_weight += 1.0
            except Exception as e:
                logger.warning(f"Stage scorer failed: {e}")

        if total_weight > 0:
            base_score = total_score / total_weight
        else:
            technical = factors.get("technical_score", 50.0)
            fundamental = factors.get("fundamental_score", 50.0)
            sentiment = factors.get("sentiment_score", 50.0)
            fund_flow = factors.get("fund_flow_score", 50.0)

            base_score = (
                technical * weights.get("technical", 0.25) +
                fundamental * weights.get("fundamental", 0.25) +
                sentiment * weights.get("sentiment", 0.25) +
                fund_flow * weights.get("fund_flow", 0.25)
            )

        return max(0, min(100, base_score))