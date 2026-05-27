"""
量化选股策略管理器 - 增强版
包含三段式流水线整合与A/B测试框架
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod
from core.storage.mongo_storage import KlineStorage, StockInfoStorage
from modules.ai.ai_analyzer import ai_analyzer
from utils.logger import get_logger


logger = get_logger(__name__)


class BaseStrategy(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def score(self, code: str) -> float:
        pass


class Strategy1NewsSentiment(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="舆情情绪事件驱动",
            description="基于舆情情绪事件驱动选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 60:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy1 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            analysis = ai_analyzer.analyze(code, "sentiment")
            sentiment_score = analysis.get("score", 50)

            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=5
            )

            price_change = 0
            if len(klines) >= 2:
                current_price = klines[0].get("close", 0)
                prev_price = klines[1].get("close", 0)
                if prev_price > 0:
                    price_change = (current_price - prev_price) / prev_price * 100

            total_score = sentiment_score * 0.7 + max(0, price_change + 50) * 0.3
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy2FundFlow(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="资金异动主力跟踪",
            description="基于资金异动主力跟踪选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 65:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy2 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            from core.storage.mongo_storage import FundFlowStorage

            flow_storage = FundFlowStorage()
            latest_flow = flow_storage.get_latest_flow(code)

            flow_score = 50
            if latest_flow:
                main_inflow = latest_flow.get("main_net_inflow", 0)
                if main_inflow > 0:
                    flow_score = min(100, 50 + main_inflow / 10000000)

            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=20
            )

            volume_score = 50
            if len(klines) >= 5:
                volumes = [k.get("volume", 0) for k in klines]
                avg_volume = sum(volumes) / len(volumes)
                current_volume = volumes[0] if volumes else 0

                if avg_volume > 0 and current_volume > avg_volume * 1.5:
                    volume_score = min(100, 50 + (current_volume / avg_volume - 1) * 30)

            total_score = flow_score * 0.6 + volume_score * 0.4
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy3Fundamental(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="基本面价值选股",
            description="基于基本面价值选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 55:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy3 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            from modules.strategies.valuation_factor import ValuationFactorAnalyzer

            # ── AI 基本面分析得分（占 50%）────────────────────────────────
            ai_score = 50
            try:
                analysis = ai_analyzer.analyze(code, "fundamental")
                rating_scores = {"推荐": 90, "中性": 60, "回避": 30}
                rating = analysis.get("investment_rating", "中性")
                rating_score = rating_scores.get(rating, 50)

                risk_score = 50
                risk_level = analysis.get("risk_level", "中")
                if risk_level == "低":
                    risk_score = 80
                elif risk_level == "高":
                    risk_score = 30

                ai_score = rating_score * 0.6 + risk_score * 0.4
            except Exception as e:
                logger.warning(f"AI analysis failed for {code}, using valuation only: {e}")

            # ── PE/ROE 量化估值得分（占 50%）──────────────────────────────
            valuation_score = 50
            try:
                vf = ValuationFactorAnalyzer().analyze(code)
                valuation_score = vf.valuation_score
            except Exception as e:
                logger.warning(f"Valuation analysis failed for {code}: {e}")

            total_score = ai_score * 0.5 + valuation_score * 0.5
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy4SectorRotation(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="板块轮动题材选股",
            description="基于板块轮动题材选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 60:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy4 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            from core.collector.fund_flow_collector import BlockCollector

            block_collector = BlockCollector()
            hot_blocks = block_collector.collect_hot_blocks() or []

            block_scores = {}
            for block in hot_blocks[:10]:
                block_scores[block.get("code")] = max(0, 100 - block.get("rank", 50) * 5)

            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=5
            )

            momentum_score = 50
            if len(klines) >= 2:
                recent_change = 0
                for i in range(min(3, len(klines) - 1)):
                    if klines[i + 1].get("close", 0) > 0:
                        change = (klines[i].get("close", 0) - klines[i + 1].get("close", 0)) / klines[i + 1].get("close", 0) * 100
                        recent_change += change

                momentum_score = min(100, max(0, 50 + recent_change))

            stock_info_storage = StockInfoStorage()
            stock_info = stock_info_storage.get_by_code(code) or {}
            industry = stock_info.get("industry", "")

            # 用行业名称匹配热门板块，计算真实板块得分
            sector_score = 30  # 行业不在热门板块时给低分
            if industry:
                # block_scores key 是板块代码，需要通过名称匹配
                for block in hot_blocks[:10]:
                    block_name = block.get("name", "")
                    if block_name and (industry in block_name or block_name in industry):
                        rank = block.get("rank", 50)
                        sector_score = max(0, 100 - rank * 5)
                        break
                else:
                    # 尝试部分匹配
                    for block in hot_blocks[:20]:
                        block_name = block.get("name", "")
                        if block_name and any(w in block_name for w in industry.split()):
                            rank = block.get("rank", 50)
                            sector_score = max(0, 80 - rank * 4)
                            break

            total_score = momentum_score * 0.7 + sector_score * 0.3
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy5TechFundFusion(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="技术+资金融合趋势",
            description="技术+资金融合趋势选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 65:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy5 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=30
            )

            if len(klines) < 10:
                return 0

            closes = [k.get("close", 0) for k in klines]

            ma10 = sum(closes[:10]) / 10
            ma20 = sum(closes[:20]) / 20

            trend_score = 50
            if closes[0] > ma10 > ma20:
                trend_score = 80
            elif closes[0] < ma10 < ma20:
                trend_score = 30
            else:
                trend_score = 50

            from core.storage.mongo_storage import FundFlowStorage
            flow_storage = FundFlowStorage()
            flow_data = flow_storage.get_latest_flow(code)

            flow_score = 50
            if flow_data:
                main_inflow = flow_data.get("main_net_inflow", 0)
                if main_inflow > 0:
                    flow_score = min(100, 70)

            total_score = trend_score * 0.5 + flow_score * 0.5
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy6LowRiskReversal(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="低风险反转套利",
            description="低风险反转套利选股"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 55:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy6 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=30
            )

            if len(klines) < 10:
                return 0

            closes = [k.get("close", 0) for k in klines]
            current_price = closes[0]

            ma20 = sum(closes[:20]) / 20

            oversold_score = 50
            if current_price < ma20 * 0.9:
                oversold_score = min(100, 50 + (ma20 * 0.9 - current_price) / ma20 * 500)

            recovery_score = 50
            if len(klines) >= 3:
                recent_changes = []
                for i in range(min(3, len(closes) - 1)):
                    if closes[i + 1] > 0:
                        change = (closes[i] - closes[i + 1]) / closes[i + 1] * 100
                        recent_changes.append(change)

                if recent_changes and all(c > 0 for c in recent_changes):
                    recovery_score = 80

            total_score = oversold_score * 0.4 + recovery_score * 0.6
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class Strategy7WatchlistOptimizer(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="自选股精细化优选",
            description="自选股精细化优选策略"
        )

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        results = []
        for code in codes:
            try:
                score = self.score(code)
                if score >= 50:
                    results.append({
                        "code": code,
                        "score": score,
                        "strategy": self.name
                    })
            except Exception as e:
                logger.error(f"Strategy7 scoring failed for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    def score(self, code: str) -> float:
        try:
            analysis = ai_analyzer.analyze(code, "comprehensive")

            score = analysis.get("score", 50)

            kline_storage = KlineStorage()
            klines = kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=5
            )

            stability_score = 50
            if len(klines) >= 3:
                changes = []
                for i in range(len(klines) - 1):
                    if klines[i + 1].get("close", 0) > 0:
                        change = abs((klines[i].get("close", 0) - klines[i + 1].get("close", 0)) / klines[i + 1].get("close", 0) * 100)
                        changes.append(change)

                if changes:
                    avg_volatility = sum(changes) / len(changes)
                    stability_score = max(0, 100 - avg_volatility * 10)

            total_score = score * 0.7 + stability_score * 0.3
            return min(100, total_score)

        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0


class StrategyManager:
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {
            "舆情情绪事件驱动": Strategy1NewsSentiment(),
            "资金异动主力跟踪": Strategy2FundFlow(),
            "基本面价值选股": Strategy3Fundamental(),
            "板块轮动题材选股": Strategy4SectorRotation(),
            "技术+资金融合趋势": Strategy5TechFundFusion(),
            "低风险反转套利": Strategy6LowRiskReversal(),
            "自选股精细化优选": Strategy7WatchlistOptimizer(),
        }

    def list_strategies(self) -> List[Dict[str, str]]:
        return [
            {
                "name": name,
                "description": strategy.description
            }
            for name, strategy in self._strategies.items()
        ]

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(name)

    def run_strategy(
        self,
        strategy_name: str,
        codes: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        strategy = self._strategies.get(strategy_name)

        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_name}")

        return strategy.select(codes, **kwargs)

    def run_all_strategies(
        self,
        codes: List[str],
        min_score: float = 60
    ) -> Dict[str, List[Dict[str, Any]]]:
        results = {}

        for name, strategy in self._strategies.items():
            try:
                strategy_results = strategy.select(codes)
                filtered = [r for r in strategy_results if r["score"] >= min_score]
                results[name] = filtered
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                results[name] = []

        return results


strategy_manager = StrategyManager()


class ThreeStageStrategy(BaseStrategy):
    def __init__(self, base_threshold: float = 60.0):
        super().__init__(
            name="三段式标准化选股",
            description="基于正向打分+负向否决+行情自适应的标准化选股流水线"
        )
        self.base_threshold = base_threshold
        self._pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            from modules.strategies.three_stage_pipeline import ThreeStagePipeline
            self._pipeline = ThreeStagePipeline()
        return self._pipeline

    def select(self, codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        threshold = kwargs.get("threshold", self.base_threshold)
        results = []

        for code in codes:
            try:
                analysis = self.pipeline.run(code, base_threshold=threshold)
                result = self._analysis_to_result(analysis)
                if result["score"] >= threshold:
                    results.append(result)
            except Exception as e:
                logger.error(f"ThreeStageStrategy error for {code}: {e}")

        return sorted(results, key=lambda x: x["score"], reverse=True)[:20]

    def score(self, code: str) -> float:
        try:
            analysis = self.pipeline.run(code, base_threshold=self.base_threshold)
            return analysis.adjusted_score
        except Exception as e:
            logger.error(f"Scoring error for {code}: {e}")
            return 0

    def _analysis_to_result(self, analysis) -> Dict[str, Any]:
        return {
            "code": analysis.code,
            "name": analysis.name,
            "score": analysis.adjusted_score,
            "total_score": analysis.total_score,
            "recommendation": analysis.recommendation,
            "risk_level": analysis.risk_level.value if hasattr(analysis.risk_level, 'value') else str(analysis.risk_level),
            "strategy": self.name,
            "technical_score": analysis.technical_score,
            "fundamental_score": analysis.fundamental_score,
            "sentiment_score": analysis.sentiment_score,
            "fund_flow_score": analysis.fund_flow_score,
            "stop_loss": analysis.stop_loss,
            "target_price": analysis.target_price,
            "support_levels": analysis.support_levels,
            "resistance_levels": analysis.resistance_levels,
            "risk_factors": analysis.risk_factors,
            "trend": analysis.trend,
            "market_phase": analysis.market_phase.value if hasattr(analysis.market_phase, 'value') else str(analysis.market_phase),
        }


class ABTestFramework:
    def __init__(self):
        self._test_results: Dict[str, List[Dict[str, Any]]] = {}
        self._active_tests: Dict[str, Dict[str, Any]] = {}

    def create_test(
        self,
        test_id: str,
        name: str,
        description: str = ""
    ) -> bool:
        self._active_tests[test_id] = {
            "name": name,
            "description": description,
            "created_at": datetime.now(),
            "variant_a": None,
            "variant_b": None,
            "status": "created"
        }
        logger.info(f"Created A/B test: {test_id}")
        return True

    def set_variant_a(self, test_id: str, strategy_config: Dict[str, Any]) -> bool:
        if test_id not in self._active_tests:
            return False
        self._active_tests[test_id]["variant_a"] = strategy_config
        logger.info(f"Set variant A for test {test_id}")
        return True

    def set_variant_b(self, test_id: str, strategy_config: Dict[str, Any]) -> bool:
        if test_id not in self._active_tests:
            return False
        self._active_tests[test_id]["variant_b"] = strategy_config
        logger.info(f"Set variant B for test {test_id}")
        return True

    def run_test(
        self,
        test_id: str,
        codes: List[str]
    ) -> Dict[str, Any]:
        if test_id not in self._active_tests:
            return {"error": f"Test {test_id} not found"}

        test_config = self._active_tests[test_id]
        if not test_config.get("variant_a") or not test_config.get("variant_b"):
            return {"error": "Both variants must be configured"}

        test_config["status"] = "running"

        variant_a_results = self._run_variant(
            test_config["variant_a"],
            codes
        )

        variant_b_results = self._run_variant(
            test_config["variant_b"],
            codes
        )

        comparison = self._compare_results(variant_a_results, variant_b_results)

        result = {
            "test_id": test_id,
            "test_name": test_config["name"],
            "variant_a": variant_a_results,
            "variant_b": variant_b_results,
            "comparison": comparison,
            "timestamp": datetime.now().isoformat()
        }

        self._test_results[test_id] = result
        test_config["status"] = "completed"

        return result

    def _run_variant(
        self,
        strategy_config: Dict[str, Any],
        codes: List[str]
    ) -> Dict[str, Any]:
        strategy_type = strategy_config.get("type")
        threshold = strategy_config.get("threshold", 60)

        if strategy_type == "three_stage":
            strategy = ThreeStageStrategy(base_threshold=threshold)
        elif strategy_type == "fund_flow":
            strategy = Strategy2FundFlow()
        elif strategy_type == "sentiment":
            strategy = Strategy1NewsSentiment()
        else:
            return {"error": f"Unknown strategy type: {strategy_type}"}

        try:
            results = strategy.select(codes)
            return {
                "total_stocks": len(codes),
                "selected_count": len(results),
                "avg_score": sum(r.get("score", 0) for r in results) / len(results) if results else 0,
                "top_stocks": results[:5] if results else [],
                "results": results
            }
        except Exception as e:
            logger.error(f"Variant run error: {e}")
            return {"error": str(e)}

    def _compare_results(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        if "error" in variant_a or "error" in variant_b:
            return {"error": "One or both variants failed"}

        a_count = variant_a.get("selected_count", 0)
        b_count = variant_b.get("selected_count", 0)
        a_avg = variant_a.get("avg_score", 0)
        b_avg = variant_b.get("avg_score", 0)

        winner = "tie"
        if a_count > b_count:
            winner = "variant_a"
        elif b_count > a_count:
            winner = "variant_b"
        elif a_avg > b_avg:
            winner = "variant_a"
        elif b_avg > a_avg:
            winner = "variant_b"

        return {
            "winner": winner,
            "variant_a_selected": a_count,
            "variant_b_selected": b_count,
            "variant_a_avg_score": round(a_avg, 2),
            "variant_b_avg_score": round(b_avg, 2),
            "score_diff": round(a_avg - b_avg, 2),
            "recommendation": self._generate_recommendation(winner)
        }

    def _generate_recommendation(self, winner: str) -> str:
        if winner == "variant_a":
            return "推荐使用A方案：选股数量更多或评分更高"
        elif winner == "variant_b":
            return "推荐使用B方案：选股数量更多或评分更高"
        else:
            return "两种方案效果相近，可根据其他因素选择"

    def get_test_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        return self._test_results.get(test_id)

    def list_tests(self) -> List[Dict[str, Any]]:
        return [
            {
                "test_id": test_id,
                "name": config["name"],
                "status": config["status"],
                "created_at": config["created_at"].isoformat()
            }
            for test_id, config in self._active_tests.items()
        ]


class MultiPeriodAnalyzer:
    def __init__(self):
        self.kline_storage = KlineStorage()

    def analyze(
        self,
        code: str,
        periods: List[str] = None
    ) -> Dict[str, Any]:
        if periods is None:
            periods = ["daily", "weekly", "monthly"]

        results = {}

        for period in periods:
            try:
                results[period] = self._analyze_single_period(code, period)
            except Exception as e:
                logger.error(f"Period {period} analysis error for {code}: {e}")
                results[period] = {"error": str(e)}

        consensus = self._generate_consensus(results)

        return {
            "code": code,
            "periods": results,
            "consensus": consensus,
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_single_period(self, code: str, period: str) -> Dict[str, Any]:
        limit_map = {
            "daily": 60,
            "weekly": 52,
            "monthly": 24
        }

        klines = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=limit_map.get(period, 30)
        )

        if len(klines) < 5:
            return {"error": "Insufficient data"}

        closes = [k.get("close", 0) for k in klines]
        volumes = [k.get("volume", 0) for k in klines]

        current_price = closes[0] if closes else 0

        period_map = {"daily": 20, "weekly": 10, "monthly": 6}
        ma_period = period_map.get(period, 20)
        ma = sum(closes[:min(ma_period, len(closes))]) / min(ma_period, len(closes)) if closes else 0

        trend = "unknown"
        if current_price > ma:
            trend = "上升"
        elif current_price < ma:
            trend = "下降"
        else:
            trend = "震荡"

        change_pct = 0
        if len(closes) >= 2 and closes[-1] > 0:
            change_pct = (closes[0] - closes[-1]) / closes[-1] * 100

        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = volumes[0] / avg_volume if avg_volume > 0 else 1

        return {
            "current_price": current_price,
            "ma": round(ma, 2),
            "trend": trend,
            "change_pct": round(change_pct, 2),
            "volume_ratio": round(volume_ratio, 2),
            "data_points": len(klines)
        }

    def _generate_consensus(self, results: Dict[str, Any]) -> Dict[str, Any]:
        trends = []
        avg_scores = []

        for period, data in results.items():
            if "error" not in data:
                if data.get("trend") == "上升":
                    trends.append(1)
                elif data.get("trend") == "下降":
                    trends.append(-1)
                else:
                    trends.append(0)

                if data.get("change_pct", 0) > 0:
                    avg_scores.append(min(100, 50 + data["change_pct"]))
                else:
                    avg_scores.append(max(0, 50 + data["change_pct"]))

        consensus_trend = "unknown"
        if trends:
            avg_trend = sum(trends) / len(trends)
            if avg_trend > 0.3:
                consensus_trend = "上升趋势确认"
            elif avg_trend < -0.3:
                consensus_trend = "下降趋势确认"
            else:
                consensus_trend = "趋势不一致"

        consensus_score = sum(avg_scores) / len(avg_scores) if avg_scores else 50

        buy_signal = "观望"
        if consensus_trend == "上升趋势确认" and consensus_score > 60:
            buy_signal = "买入"
        elif consensus_trend == "下降趋势确认" or consensus_score < 40:
            buy_signal = "回避"

        return {
            "trend_consensus": consensus_trend,
            "avg_score": round(consensus_score, 2),
            "buy_signal": buy_signal,
            "period_count": len(trends),
            "reliability": "高" if len(trends) >= 2 else "低"
        }


class DynamicPositionManager:
    def __init__(self, base_position: float = 0.10):
        self.base_position = base_position
        self.max_position = 0.30
        self.min_position = 0.02

    def calculate_position(
        self,
        stock_score: float,
        market_volatility: float = 0.2,
        current_positions: List[float] = None
    ) -> float:
        if current_positions is None:
            current_positions = []

        used_capacity = sum(current_positions)
        available_capacity = self.max_position - used_capacity

        if available_capacity <= 0:
            return 0.0

        score_factor = stock_score / 100.0

        volatility_factor = 1.0
        if market_volatility > 0.3:
            volatility_factor = 0.7
        elif market_volatility > 0.4:
            volatility_factor = 0.5

        raw_position = self.base_position * score_factor * volatility_factor

        position = min(raw_position, available_capacity)
        position = max(position, self.min_position)

        return round(position, 4)

    def adjust_for_market(
        self,
        base_position: float,
        market_phase: str,
        market_volatility: float
    ) -> float:
        phase_multipliers = {
            "bull": 1.2,
            "consolidation": 1.0,
            "bear": 0.7
        }

        volatility_multipliers = {
            "low": 1.2,
            "medium": 1.0,
            "high": 0.7,
            "extreme": 0.5
        }

        phase = market_phase if market_phase in phase_multipliers else "consolidation"

        vol_level = "medium"
        if market_volatility < 0.15:
            vol_level = "low"
        elif market_volatility > 0.35:
            vol_level = "high"
        elif market_volatility > 0.5:
            vol_level = "extreme"

        adjusted = base_position * phase_multipliers[phase] * volatility_multipliers[vol_level]
        adjusted = min(adjusted, self.max_position)
        adjusted = max(adjusted, self.min_position)

        return round(adjusted, 4)


ab_test_framework = ABTestFramework()
multi_period_analyzer = MultiPeriodAnalyzer()
dynamic_position_manager = DynamicPositionManager()


class SceneGrayAdapter:
    def __init__(self):
        self.kline_storage = KlineStorage()

    def detect_scene(self) -> str:
        try:
            index_codes = ["SH000001"]
            klines = self.kline_storage.find_many(
                {"code": index_codes[0]},
                sort=[("date", -1)],
                limit=20
            )

            if len(klines) < 10:
                return "consolidation"

            closes = [k.get("close", 0) for k in klines]
            if len(closes) >= 20:
                ma20 = sum(closes[:20]) / 20
                ma60_sum = sum(closes[:min(60, len(closes))])
                ma60 = ma60_sum / min(60, len(closes))

                current = closes[0]

                if current > ma20 > ma60:
                    return "bull"
                elif current < ma20 < ma60:
                    return "bear"
                else:
                    return "consolidation"

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
                "description": "积极进攻，关注趋势股",
                "preferred_strategies": ["资金异动主力跟踪", "技术+资金融合趋势"],
                "stop_loss_percent": 0.07,
                "profit_target_percent": 0.15
            },
            "bear": {
                "name": "熊市",
                "threshold_multiplier": 1.2,
                "max_stocks": 5,
                "description": "保守防御，关注防御股",
                "preferred_strategies": ["低风险反转套利", "基本面价值选股"],
                "stop_loss_percent": 0.05,
                "profit_target_percent": 0.08
            },
            "consolidation": {
                "name": "震荡市",
                "threshold_multiplier": 1.0,
                "max_stocks": 10,
                "description": "平衡配置，关注轮动机会",
                "preferred_strategies": ["舆情情绪事件驱动", "板块轮动题材选股"],
                "stop_loss_percent": 0.06,
                "profit_target_percent": 0.10
            }
        }

        return configs.get(scene, configs["consolidation"])

    def adjust_threshold(self, base_threshold: float, scene: str) -> float:
        config = self.get_scene_config(scene)
        return base_threshold * config["threshold_multiplier"]


class MultiStrategyCombiner:
    def __init__(self):
        self.strategy_manager = StrategyManager()

    def combine_strategies(
        self,
        codes: List[str],
        strategy_names: List[str],
        combination_type: str = "intersection",
        min_score: float = 60.0,
        min_agreement: float = 0.5
    ) -> List[Dict[str, Any]]:
        if not strategy_names:
            return []

        all_results = {}
        for name in strategy_names:
            try:
                results = self.strategy_manager.run_strategy(name, codes)
                for r in results:
                    code = r["code"]
                    if code not in all_results:
                        all_results[code] = []
                    all_results[code].append({
                        "strategy": name,
                        "score": r.get("score", 0)
                    })
            except Exception as e:
                logger.error(f"Strategy {name} error: {e}")

        if combination_type == "intersection":
            return self._intersection_filter(all_results, min_agreement, min_score)
        elif combination_type == "union":
            return self._union_filter(all_results, min_score)
        elif combination_type == "weighted":
            return self._weighted_combination(all_results, min_score)
        else:
            return []

    def _intersection_filter(
        self,
        all_results: Dict,
        min_agreement: float,
        min_score: float
    ) -> List[Dict[str, Any]]:
        required_count = int(len(all_results) * min_agreement)

        filtered = []
        for code, results in all_results.items():
            if len(results) >= required_count:
                avg_score = sum(r["score"] for r in results) / len(results)
                if avg_score >= min_score:
                    filtered.append({
                        "code": code,
                        "score": avg_score,
                        "strategies_count": len(results),
                        "strategy_details": results
                    })

        filtered.sort(key=lambda x: (x["strategies_count"], x["score"]), reverse=True)
        return filtered

    def _union_filter(
        self,
        all_results: Dict,
        min_score: float
    ) -> List[Dict[str, Any]]:
        filtered = []
        for code, results in all_results.items():
            max_score = max(r["score"] for r in results)
            if max_score >= min_score:
                filtered.append({
                    "code": code,
                    "score": max_score,
                    "strategies_count": len(results),
                    "strategy_details": results
                })

        filtered.sort(key=lambda x: x["score"], reverse=True)
        return filtered

    def _weighted_combination(
        self,
        all_results: Dict,
        min_score: float
    ) -> List[Dict[str, Any]]:
        strategy_weights = {
            "舆情情绪事件驱动": 0.15,
            "资金异动主力跟踪": 0.20,
            "基本面价值选股": 0.20,
            "板块轮动题材选股": 0.15,
            "技术+资金融合趋势": 0.15,
            "低风险反转套利": 0.10,
            "自选股精细化优选": 0.05,
        }

        weighted_results = []
        for code, results in all_results.items():
            total_weighted_score = 0.0
            total_weight = 0.0

            for r in results:
                weight = strategy_weights.get(r["strategy"], 0.1)
                total_weighted_score += r["score"] * weight
                total_weight += weight

            if total_weight > 0:
                weighted_score = total_weighted_score / total_weight
                if weighted_score >= min_score:
                    weighted_results.append({
                        "code": code,
                        "score": round(weighted_score, 2),
                        "strategies_count": len(results),
                        "strategy_details": results
                    })

        weighted_results.sort(key=lambda x: x["score"], reverse=True)
        return weighted_results


scene_adapter = SceneGrayAdapter()
multi_strategy_combiner = MultiStrategyCombiner()