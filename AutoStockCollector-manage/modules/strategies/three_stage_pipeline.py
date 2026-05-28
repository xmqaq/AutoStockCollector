"""
三段式标准化选股流水线
正向因子打分 + 负向一票否决 + 行情自适应修正
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod
from core.storage.mongo_storage import KlineStorage, StockInfoStorage, NewsStorage, FundFlowStorage
from modules.ai.ai_analyzer import ai_analyzer
from utils.logger import get_logger


logger = get_logger(__name__)


class MarketPhase(Enum):
    BULL = "bull"
    BEAR = "bear"
    CONSOLIDATION = "consolidation"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class ScoreComponent:
    dimension: str
    raw_score: float
    weight: float
    description: str = ""


@dataclass
class RiskCheck:
    risk_type: str
    severity: str
    description: str
    passed: bool


@dataclass
class StockAnalysis:
    code: str
    name: str = ""

    technical_score: float = 50.0
    fundamental_score: float = 50.0
    sentiment_score: float = 50.0
    fund_flow_score: float = 50.0

    total_score: float = 50.0
    adjusted_score: float = 50.0
    recommendation: str = "观望"

    risk_checks: List[RiskCheck] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM

    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    stop_loss: float = 0.0
    target_price: float = 0.0

    reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    current_price: float = 0.0
    current_ma20: float = 0.0
    trend: str = "unknown"

    market_phase: MarketPhase = MarketPhase.CONSOLIDATION
    analysis_timestamp: datetime = field(default_factory=datetime.now)


class BaseScoringModel(ABC):
    def __init__(self):
        self.technical_weight = 0.25
        self.fundamental_weight = 0.25
        self.sentiment_weight = 0.25
        self.fund_flow_weight = 0.25

    @abstractmethod
    def calculate_technical_score(self, code: str, klines: List[Dict]) -> float:
        pass

    @abstractmethod
    def calculate_fundamental_score(self, code: str) -> float:
        pass

    @abstractmethod
    def calculate_sentiment_score(self, code: str) -> float:
        pass

    @abstractmethod
    def calculate_fund_flow_score(self, code: str) -> float:
        pass


class StandardScoringModel(BaseScoringModel):
    def calculate_technical_score(self, code: str, klines: List[Dict]) -> float:
        if len(klines) < 10:
            return 50.0

        closes = [k.get("close", 0) for k in klines]
        volumes = [k.get("volume", 0) for k in klines]

        current_price = closes[0] if closes else 0
        ma5 = sum(closes[:5]) / min(5, len(closes)) if len(closes) >= 5 else current_price
        ma10 = sum(closes[:10]) / min(10, len(closes)) if len(closes) >= 10 else current_price
        ma20 = sum(closes[:20]) / min(20, len(closes)) if len(closes) >= 20 else current_price

        trend_score = 50.0
        if current_price > ma20 > ma10 > ma5:
            trend_score = 80.0
        elif current_price > ma20 and current_price > ma10:
            trend_score = 70.0
        elif current_price < ma20 < ma10 < ma5:
            trend_score = 20.0
        elif current_price < ma20 and current_price < ma10:
            trend_score = 30.0
        else:
            trend_score = 50.0

        change_pct = 0.0
        if len(closes) >= 2 and closes[1] > 0:
            change_pct = (closes[0] - closes[1]) / closes[1] * 100

        change_score = 50.0
        if change_pct > 0:
            change_score = min(100, 50 + change_pct * 5)
        else:
            change_score = max(0, 50 + change_pct * 5)

        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = volumes[0] / avg_volume if avg_volume > 0 else 1

        volume_score = 50.0
        if volume_ratio > 2:
            volume_score = 80.0
        elif volume_ratio > 1.5:
            volume_score = 70.0
        elif volume_ratio > 1.0:
            volume_score = 60.0
        elif volume_ratio < 0.5:
            volume_score = 30.0

        total_score = trend_score * 0.5 + change_score * 0.3 + volume_score * 0.2
        return round(min(100, max(0, total_score)), 2)

    def calculate_fundamental_score(self, code: str) -> float:
        try:
            analysis = ai_analyzer.analyze(code, "fundamental")
            ai_score = analysis.get("score", 50)

            rating_scores = {"推荐": 90, "中性": 60, "回避": 30}
            rating = analysis.get("investment_rating", "中性")
            rating_score = rating_scores.get(rating, 50)

            risk_scores = {"低": 80, "中": 60, "高": 30}
            risk_level = analysis.get("risk_level", "中")
            risk_score = risk_scores.get(risk_level, 50)

            return (ai_score * 0.4 + rating_score * 0.3 + risk_score * 0.3)
        except Exception as e:
            logger.error(f"Fundamental scoring error for {code}: {e}")
            return 50.0

    def calculate_sentiment_score(self, code: str) -> float:
        try:
            analysis = ai_analyzer.analyze(code, "sentiment")
            sentiment_score = analysis.get("score", 50)
            return sentiment_score
        except Exception as e:
            logger.error(f"Sentiment scoring error for {code}: {e}")
            return 50.0

    def calculate_fund_flow_score(self, code: str) -> float:
        try:
            flow_storage = FundFlowStorage()
            latest_flow = flow_storage.get_latest_flow(code)

            flow_score = 50.0
            if latest_flow:
                main_inflow = latest_flow.get("main_net_inflow", 0)
                if main_inflow > 100000000:
                    flow_score = 90.0
                elif main_inflow > 50000000:
                    flow_score = 75.0
                elif main_inflow > 0:
                    flow_score = 60.0
                elif main_inflow < -100000000:
                    flow_score = 20.0
                elif main_inflow < -50000000:
                    flow_score = 35.0

            return flow_score
        except Exception as e:
            logger.error(f"Fund flow scoring error for {code}: {e}")
            return 50.0


class NegativeVetoChecker:
    def __init__(self):
        self.risk_checks = []

    def add_check(self, check: RiskCheck):
        self.risk_checks.append(check)

    def check_delisting_risk(self, code: str) -> RiskCheck:
        try:
            stock_info_storage = StockInfoStorage()
            info = stock_info_storage.get_by_code(code)

            if not info:
                return RiskCheck("delisting", "low", "股票信息不存在，跳过退市检查", True)

            status = info.get("上市状态", "上市")
            if status in ["暂停上市", "终止上市"]:
                return RiskCheck("delisting", "extreme", "股票已暂停或终止上市", False)

            return RiskCheck("delisting", "low", "无退市风险", True)
        except Exception as e:
            logger.error(f"Delisting check error: {e}")
            return RiskCheck("delisting", "low", f"检查异常: {str(e)}", True)

    def check_st_risk(self, code: str, klines: List[Dict]) -> RiskCheck:
        try:
            stock_info_storage = StockInfoStorage()
            info = stock_info_storage.get_by_code(code)

            is_st = info.get("is_st", False) or info.get("股票简称", "").startswith("ST")

            if is_st:
                return RiskCheck("st_status", "high", "股票为ST或*ST", False)

            return RiskCheck("st_status", "low", "非ST股票", True)
        except Exception as e:
            return RiskCheck("st_status", "low", f"检查异常: {str(e)}", True)

    def check_limit_up_risk(self, code: str, klines: List[Dict]) -> RiskCheck:
        if not klines:
            return RiskCheck("limit_up", "low", "无K线数据", True)

        latest = klines[0]
        pct_chg = latest.get("涨跌幅", 0) or latest.get("pct_chg", 0)

        if pct_chg >= 9.5:
            return RiskCheck("limit_up", "medium", f"涨停状态，买入受限", False)
        elif pct_chg >= 7.0:
            return RiskCheck("limit_up", "low", f"接近涨停({pct_chg:.1f}%)", True)

        return RiskCheck("limit_up", "low", "非涨停状态", True)

    def check_liquidity_risk(self, code: str, klines: List[Dict]) -> RiskCheck:
        if len(klines) < 5:
            return RiskCheck("liquidity", "low", "数据不足", True)

        recent_volumes = [k.get("volume", 0) for k in klines[:5]]
        avg_volume = sum(recent_volumes) / len(recent_volumes)

        if avg_volume < 1000000:
            return RiskCheck("liquidity", "high", "流动性极低，日均成交量不足100万", False)
        elif avg_volume < 5000000:
            return RiskCheck("liquidity", "medium", "流动性偏低", True)

        return RiskCheck("liquidity", "low", "流动性正常", True)

    def check_price_structure_risk(self, code: str, klines: List[Dict]) -> RiskCheck:
        if len(klines) < 20:
            return RiskCheck("price_structure", "low", "数据不足", True)

        closes = [k.get("close", 0) for k in klines[:20]]
        current_price = closes[0]

        ma20 = sum(closes[:20]) / 20
        ma60_sum = sum(closes[:min(60, len(closes))])
        ma60 = ma60_sum / min(60, len(closes))

        if current_price < ma20 * 0.7:
            return RiskCheck("price_structure", "high", "价格跌破MA20的70%，下跌趋势明显", False)
        elif current_price < ma20 * 0.85:
            return RiskCheck("price_structure", "medium", "价格低于MA20，可能继续调整", True)

        return RiskCheck("price_structure", "low", "价格结构正常", True)

    def check_all(self, code: str, klines: List[Dict]) -> List[RiskCheck]:
        checks = [
            self.check_delisting_risk(code),
            self.check_st_risk(code, klines),
            self.check_limit_up_risk(code, klines),
            self.check_liquidity_risk(code, klines),
            self.check_price_structure_risk(code, klines),
        ]

        failed_checks = [c for c in checks if not c.passed]
        return checks, failed_checks

    def has_critical_failure(self, failed_checks: List[RiskCheck]) -> bool:
        return any(c.severity in ["extreme", "high"] for c in failed_checks)


class MarketAdaptiveModifier:
    def __init__(self):
        self.bull_market_multiplier = 1.2
        self.bear_market_multiplier = 0.8
        self.consolidation_multiplier = 1.0

    def detect_market_phase(self) -> MarketPhase:
        try:
            kline_storage = KlineStorage()
            index_codes = ["SH000001", "SH000300"]

            index_changes = []
            for code in index_codes:
                klines = kline_storage.find_many(
                    {"code": code},
                    sort=[("date", -1)],
                    limit=20
                )
                if len(klines) >= 10:
                    closes = [k.get("close", 0) for k in klines]
                    if closes[10] > 0:
                        change = (closes[0] - closes[10]) / closes[10] * 100
                        index_changes.append(change)

            if not index_changes:
                return MarketPhase.CONSOLIDATION

            avg_change = sum(index_changes) / len(index_changes)

            if avg_change > 10:
                return MarketPhase.BULL
            elif avg_change < -10:
                return MarketPhase.BEAR
            else:
                return MarketPhase.CONSOLIDATION
        except Exception as e:
            logger.error(f"Market phase detection error: {e}")
            return MarketPhase.CONSOLIDATION

    def adjust_score(
        self,
        base_score: float,
        market_phase: MarketPhase,
        market_volatility: float = 0.0
    ) -> float:
        multiplier = self.consolidation_multiplier

        if market_phase == MarketPhase.BULL:
            multiplier = self.bull_market_multiplier
        elif market_phase == MarketPhase.BEAR:
            multiplier = self.bear_market_multiplier

        if market_volatility > 0.3:
            multiplier *= 0.9

        adjusted = base_score * multiplier
        return round(min(100, max(0, adjusted)), 2)

    def get_adaptive_threshold(
        self,
        market_phase: MarketPhase,
        base_threshold: float = 60.0
    ) -> float:
        if market_phase == MarketPhase.BULL:
            return base_threshold * 0.9
        elif market_phase == MarketPhase.BEAR:
            return base_threshold * 1.1
        else:
            return base_threshold


class ThreeStagePipeline:
    def __init__(self):
        self.scoring_model = StandardScoringModel()
        self.veto_checker = NegativeVetoChecker()
        self.market_modifier = MarketAdaptiveModifier()

        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.news_storage = NewsStorage()
        self.fund_flow_storage = FundFlowStorage()

    def run(
        self,
        code: str,
        base_threshold: float = 60.0
    ) -> StockAnalysis:
        analysis = StockAnalysis(code=code)

        try:
            stock_info = self.stock_info_storage.get_by_code(code)
            analysis.name = stock_info.get("name", "") if stock_info else ""

            klines = self.kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=60
            )

            analysis.current_price = klines[0].get("close", 0) if klines else 0
            closes = [k.get("close", 0) for k in klines]
            analysis.current_ma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else analysis.current_price

            if analysis.current_price > analysis.current_ma20:
                analysis.trend = "上升"
            elif analysis.current_price < analysis.current_ma20:
                analysis.trend = "下降"
            else:
                analysis.trend = "震荡"

        except Exception as e:
            logger.error(f"Data preparation error for {code}: {e}")

        analysis.market_phase = self.market_modifier.detect_market_phase()

        stage1_scores = self._run_stage1_scoring(code, klines)
        analysis.technical_score = stage1_scores["technical"]
        analysis.fundamental_score = stage1_scores["fundamental"]
        analysis.sentiment_score = stage1_scores["sentiment"]
        analysis.fund_flow_score = stage1_scores["fund_flow"]

        weights = {
            "technical": self.scoring_model.technical_weight,
            "fundamental": self.scoring_model.fundamental_weight,
            "sentiment": self.scoring_model.sentiment_weight,
            "fund_flow": self.scoring_model.fund_flow_weight,
        }

        analysis.total_score = (
            analysis.technical_score * weights["technical"] +
            analysis.fundamental_score * weights["fundamental"] +
            analysis.sentiment_score * weights["sentiment"] +
            analysis.fund_flow_score * weights["fund_flow"]
        )
        analysis.total_score = round(analysis.total_score, 2)

        stage2_result = self._run_stage2_veto(code, klines)
        analysis.risk_checks = stage2_result["checks"]
        analysis.risk_level = stage2_result["risk_level"]

        if self.veto_checker.has_critical_failure(stage2_result["failed_checks"]):
            analysis.adjusted_score = 0
            analysis.recommendation = "回避"
            analysis.risk_factors = [
                f"{c.risk_type}: {c.description}"
                for c in stage2_result["failed_checks"]
            ]
            return analysis

        stage3_result = self._run_stage3_adaptation(analysis)
        analysis.adjusted_score = stage3_result["adjusted_score"]
        analysis.stop_loss = stage3_result["stop_loss"]
        analysis.target_price = stage3_result["target_price"]
        analysis.support_levels = stage3_result["support_levels"]
        analysis.resistance_levels = stage3_result["resistance_levels"]

        threshold = self.market_modifier.get_adaptive_threshold(
            analysis.market_phase,
            base_threshold
        )

        if analysis.adjusted_score >= threshold:
            analysis.recommendation = "买入"
        elif analysis.adjusted_score >= threshold * 0.8:
            analysis.recommendation = "观望"
        else:
            analysis.recommendation = "回避"

        return analysis

    def _run_stage1_scoring(
        self,
        code: str,
        klines: List[Dict]
    ) -> Dict[str, float]:
        scores = {
            "technical": 50.0,
            "fundamental": 50.0,
            "sentiment": 50.0,
            "fund_flow": 50.0,
        }

        try:
            scores["technical"] = self.scoring_model.calculate_technical_score(code, klines)
        except Exception as e:
            logger.error(f"Technical scoring error: {e}")

        try:
            scores["fundamental"] = self.scoring_model.calculate_fundamental_score(code)
        except Exception as e:
            logger.error(f"Fundamental scoring error: {e}")

        try:
            scores["sentiment"] = self.scoring_model.calculate_sentiment_score(code)
        except Exception as e:
            logger.error(f"Sentiment scoring error: {e}")

        try:
            scores["fund_flow"] = self.scoring_model.calculate_fund_flow_score(code)
        except Exception as e:
            logger.error(f"Fund flow scoring error: {e}")

        return scores

    def _run_stage2_veto(
        self,
        code: str,
        klines: List[Dict]
    ) -> Dict[str, Any]:
        checks, failed_checks = self.veto_checker.check_all(code, klines)

        risk_level = RiskLevel.MEDIUM
        if any(c.severity == "extreme" for c in failed_checks):
            risk_level = RiskLevel.EXTREME
        elif any(c.severity == "high" for c in failed_checks):
            risk_level = RiskLevel.HIGH
        elif any(c.severity == "medium" for c in failed_checks):
            risk_level = RiskLevel.MEDIUM

        return {
            "checks": checks,
            "failed_checks": failed_checks,
            "risk_level": risk_level
        }

    def _run_stage3_adaptation(
        self,
        analysis: StockAnalysis
    ) -> Dict[str, Any]:
        adjusted_score = self.market_modifier.adjust_score(
            analysis.total_score,
            analysis.market_phase
        )

        current_price = analysis.current_price
        ma20 = analysis.current_ma20

        stop_loss = round(current_price * 0.95, 2)
        target_price = round(current_price * 1.15, 2)

        support_levels = [
            round(ma20 * 0.95, 2),
            round(ma20 * 0.90, 2),
            round(current_price * 0.92, 2),
        ]

        resistance_levels = [
            round(ma20 * 1.05, 2),
            round(ma20 * 1.10, 2),
            round(current_price * 1.08, 2),
        ]

        return {
            "adjusted_score": adjusted_score,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
        }

    def run_batch(
        self,
        codes: List[str],
        base_threshold: float = 60.0
    ) -> List[StockAnalysis]:
        results = []

        for code in codes:
            try:
                analysis = self.run(code, base_threshold)
                results.append(analysis)
            except Exception as e:
                logger.error(f"Pipeline error for {code}: {e}")

        return results


pipeline = ThreeStagePipeline()