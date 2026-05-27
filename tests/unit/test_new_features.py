"""
新增模块测试用例
针对三段式流水线、回测风控、模型管理等新增功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from modules.strategies.three_stage_pipeline import (
    ThreeStagePipeline,
    NegativeVetoChecker,
    MarketAdaptiveModifier,
    MarketPhase,
    RiskLevel,
    StockAnalysis,
    RiskCheck,
)
from modules.backtest.backtest_engine import (
    BacktestEngine,
    RiskControlMixin,
    PerformanceMetrics,
)


class TestRiskControlMixin:
    def test_stop_loss_check(self):
        mixin = RiskControlMixin()
        mixin.set_stop_loss(0.05)

        assert mixin.check_stop_loss(100, 94) is True
        assert mixin.check_stop_loss(100, 96) is False
        assert mixin.check_stop_loss(100, 105) is False

    def test_take_profit_check(self):
        mixin = RiskControlMixin()
        mixin.set_take_profit(0.10)

        assert mixin.check_take_profit(100, 111) is True
        assert mixin.check_take_profit(100, 105) is False
        assert mixin.check_take_profit(100, 95) is False

    def test_slippage_application(self):
        mixin = RiskControlMixin()
        mixin.set_slippage(0.001)

        buy_price = mixin.apply_slippage(100, is_buy=True)
        sell_price = mixin.apply_slippage(100, is_buy=False)

        assert buy_price == 100.1
        assert sell_price == 99.9

    def test_should_exit(self):
        mixin = RiskControlMixin()
        mixin.set_stop_loss(0.05)
        mixin.set_take_profit(0.10)

        should_exit, reason = mixin.should_exit(100, 94)
        assert should_exit is True
        assert reason == "stop_loss"

        should_exit, reason = mixin.should_exit(100, 112)
        assert should_exit is True
        assert reason == "take_profit"

        should_exit, reason = mixin.should_exit(100, 103)
        assert should_exit is False
        assert reason == ""

    def test_trailing_stop(self):
        mixin = RiskControlMixin()
        mixin.enable_trailing_stop(0.05)
        assert mixin.use_trailing_stop is True
        assert mixin.trailing_percent == 0.05


class TestNegativeVetoChecker:
    def test_limit_up_risk_check(self):
        checker = NegativeVetoChecker()

        klines_normal = [{"涨跌幅": 2.0}]
        result = checker.check_limit_up_risk("SH600000", klines_normal)
        assert result.passed is True

        klines_limit = [{"涨跌幅": 9.9}]
        result = checker.check_limit_up_risk("SH600000", klines_limit)
        assert result.passed is False
        assert "涨停" in result.description

    def test_liquidity_risk_check(self):
        checker = NegativeVetoChecker()

        klines_low_volume = [{"volume": 500000}, {"volume": 400000}] * 3
        result = checker.check_liquidity_risk("SH600000", klines_low_volume)
        assert result.passed is False
        assert "流动性" in result.description

        klines_normal = [{"volume": 10000000}] * 5
        result = checker.check_liquidity_risk("SH600000", klines_normal)
        assert result.passed is True

    def test_has_critical_failure(self):
        checker = NegativeVetoChecker()

        low_risk = [RiskCheck("type1", "low", "desc", True)]
        assert checker.has_critical_failure(low_risk) is False

        high_risk = [
            RiskCheck("type1", "high", "desc", False),
            RiskCheck("type2", "low", "desc", True),
        ]
        assert checker.has_critical_failure(high_risk) is True


class TestMarketAdaptiveModifier:
    def test_detect_market_phase(self):
        modifier = MarketAdaptiveModifier()

        with patch("modules.strategies.three_stage_pipeline.KlineStorage") as mock_storage:
            mock_instance = MagicMock()
            mock_storage.return_value = mock_instance

            klines_bull = [
                {"code": "SH000001", "date": "2024-01-01", "close": 3500},
                {"code": "SH000001", "date": "2024-01-15", "close": 3400},
            ]
            mock_instance.find_many.return_value = klines_bull * 10

            phase = modifier.detect_market_phase()
            assert phase in [MarketPhase.BULL, MarketPhase.BEAR, MarketPhase.CONSOLIDATION]

    def test_adjust_score(self):
        modifier = MarketAdaptiveModifier()

        score = modifier.adjust_score(60, MarketPhase.BULL)
        assert score > 60

        score = modifier.adjust_score(60, MarketPhase.BEAR)
        assert score < 60

        score = modifier.adjust_score(60, MarketPhase.CONSOLIDATION)
        assert score == 60

    def test_get_adaptive_threshold(self):
        modifier = MarketAdaptiveModifier()
        base = 60

        bull_threshold = modifier.get_adaptive_threshold(MarketPhase.BULL, base)
        assert bull_threshold < base

        bear_threshold = modifier.get_adaptive_threshold(MarketPhase.BEAR, base)
        assert bear_threshold > base


class TestThreeStagePipeline:
    def test_pipeline_initialization(self):
        pipeline = ThreeStagePipeline()
        assert pipeline.scoring_model is not None
        assert pipeline.veto_checker is not None
        assert pipeline.market_modifier is not None

    def test_stage1_scoring(self):
        pipeline = ThreeStagePipeline()
        klines = [
            {"close": 100, "volume": 1000000},
            {"close": 101, "volume": 1100000},
            {"close": 102, "volume": 1200000},
        ] * 20

        with patch.object(pipeline.scoring_model, "calculate_technical_score", return_value=70.0):
            with patch.object(pipeline.scoring_model, "calculate_fundamental_score", return_value=65.0):
                with patch.object(pipeline.scoring_model, "calculate_sentiment_score", return_value=60.0):
                    with patch.object(pipeline.scoring_model, "calculate_fund_flow_score", return_value=55.0):
                        scores = pipeline._run_stage1_scoring("SH600000", klines)

                        assert scores["technical"] == 70.0
                        assert scores["fundamental"] == 65.0
                        assert scores["sentiment"] == 60.0
                        assert scores["fund_flow"] == 55.0


class TestPerformanceMetrics:
    def test_calculate_total_return(self):
        result = PerformanceMetrics.calculate_total_return(100000, 120000)
        assert result == 20.0

        result = PerformanceMetrics.calculate_total_return(100000, 80000)
        assert result == -20.0

        result = PerformanceMetrics.calculate_total_return(0, 100000)
        assert result == 0.0

    def test_calculate_max_drawdown(self):
        equity = [100000, 110000, 105000, 95000, 100000]
        result = PerformanceMetrics.calculate_max_drawdown(equity)
        assert result > 0

        equity_flat = [100000, 100000, 100000]
        result = PerformanceMetrics.calculate_max_drawdown(equity_flat)
        assert result == 0.0

    def test_calculate_win_rate(self):
        trades = [
            {"pnl": 1000},
            {"pnl": -500},
            {"pnl": 2000},
            {"pnl": -300},
            {"pnl": 500},
        ]
        result = PerformanceMetrics.calculate_win_rate(trades)
        assert result == 60.0

        trades_empty = []
        result = PerformanceMetrics.calculate_win_rate(trades_empty)
        assert result == 0.0

    def test_calculate_profit_loss_ratio(self):
        trades = [
            {"pnl": 1000},
            {"pnl": 2000},
            {"pnl": -500},
            {"pnl": -250},
        ]
        result = PerformanceMetrics.calculate_profit_loss_ratio(trades)
        assert result == 4.0

    def test_generate_report(self):
        trades = [
            {"pnl": 1000, "date": "2024-01-01", "type": "sell"},
            {"pnl": 500, "date": "2024-01-02", "type": "sell"},
            {"pnl": -300, "date": "2024-01-03", "type": "sell"},
        ]

        report = PerformanceMetrics.generate_report(
            initial_cash=100000,
            final_cash=101200,
            trades=trades,
            days=365
        )

        assert "total_return" in report
        assert "sharpe_ratio" in report
        assert "win_rate" in report
        assert report["total_trades"] == 3
        assert report["winning_trades"] == 2
        assert report["losing_trades"] == 1


class TestBacktestEngineRiskConfig:
    def test_default_risk_config(self):
        engine = BacktestEngine()
        config = engine.default_risk_config

        assert config["stop_loss"] == 0.05
        assert config["take_profit"] == 0.10
        assert config["slippage"] == 0.001
        assert config["max_position"] == 0.20

    def test_run_with_risk_params(self):
        engine = BacktestEngine()

        with patch.object(engine, "_backtest_single", return_value=None):
            result = engine.run(
                strategy="ma_cross",
                codes=["SH600000"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                stop_loss=0.08,
                take_profit=0.15,
                slippage=0.002,
                max_position=0.15
            )

            assert "error" in result or "strategy" in result


class TestABTestFramework:
    def test_create_test(self):
        from modules.strategies.strategy_manager import ABTestFramework

        framework = ABTestFramework()
        result = framework.create_test(
            test_id="test_001",
            name="策略A/B对比测试",
            description="测试三段式流水线与传统策略"
        )

        assert result is True
        assert "test_001" in framework._active_tests

    def test_set_variants(self):
        from modules.strategies.strategy_manager import ABTestFramework

        framework = ABTestFramework()
        framework.create_test(test_id="test_002", name="Test")

        result_a = framework.set_variant_a(
            "test_002",
            {"type": "three_stage", "threshold": 60}
        )
        assert result_a is True

        result_b = framework.set_variant_b(
            "test_002",
            {"type": "fund_flow", "threshold": 65}
        )
        assert result_b is True

    def test_compare_results(self):
        from modules.strategies.strategy_manager import ABTestFramework

        framework = ABTestFramework()

        variant_a = {"selected_count": 10, "avg_score": 72.5}
        variant_b = {"selected_count": 8, "avg_score": 68.0}

        comparison = framework._compare_results(variant_a, variant_b)

        assert comparison["winner"] == "variant_a"
        assert comparison["variant_a_selected"] == 10
        assert comparison["variant_b_selected"] == 8


class TestMultiPeriodAnalyzer:
    def test_analyze_single_period(self):
        from modules.strategies.strategy_manager import MultiPeriodAnalyzer

        analyzer = MultiPeriodAnalyzer()

        with patch.object(analyzer, "kline_storage") as mock_storage:
            mock_storage.find_many.return_value = [
                {"close": 100, "volume": 1000000},
                {"close": 101, "volume": 1100000},
                {"close": 102, "volume": 1200000},
                {"close": 103, "volume": 1300000},
                {"close": 104, "volume": 1400000},
            ] * 5

            result = analyzer._analyze_single_period("SH600000", "daily")

            assert "current_price" in result
            assert "trend" in result
            assert "change_pct" in result

    def test_generate_consensus(self):
        from modules.strategies.strategy_manager import MultiPeriodAnalyzer

        analyzer = MultiPeriodAnalyzer()

        results = {
            "daily": {"trend": "上升", "change_pct": 5.0},
            "weekly": {"trend": "上升", "change_pct": 3.0},
            "monthly": {"trend": "震荡", "change_pct": 1.0}
        }

        consensus = analyzer._generate_consensus(results)

        assert "trend_consensus" in consensus
        assert "avg_score" in consensus
        assert "buy_signal" in consensus


class TestDynamicPositionManager:
    def test_calculate_position(self):
        from modules.strategies.strategy_manager import DynamicPositionManager

        manager = DynamicPositionManager()

        position = manager.calculate_position(
            stock_score=80,
            market_volatility=0.2
        )

        assert position > 0
        assert position <= manager.max_position

    def test_adjust_for_market(self):
        from modules.strategies.strategy_manager import DynamicPositionManager

        manager = DynamicPositionManager()

        bull_position = manager.adjust_for_market(0.10, "bull", 0.2)
        bear_position = manager.adjust_for_market(0.10, "bear", 0.2)

        assert bull_position > bear_position

        high_vol_position = manager.adjust_for_market(0.10, "bull", 0.4)
        assert high_vol_position < bull_position

    def test_position_limits(self):
        from modules.strategies.strategy_manager import DynamicPositionManager

        manager = DynamicPositionManager()

        max_pos = manager.calculate_position(
            stock_score=100,
            market_volatility=0.05
        )
        assert max_pos <= manager.max_position

        min_pos = manager.calculate_position(
            stock_score=10,
            market_volatility=0.5
        )
        assert min_pos >= manager.min_position


class TestThreeStageStrategy:
    def test_three_stage_strategy_init(self):
        from modules.strategies.strategy_manager import ThreeStageStrategy

        strategy = ThreeStageStrategy(base_threshold=65)
        assert strategy.name == "三段式标准化选股"
        assert strategy.base_threshold == 65


class TestModelManagerEnhancements:
    def test_model_config_dataclass(self):
        from modules.ai.model_manager import ModelConfig

        config = ModelConfig(
            name="test_model",
            api_key="test_key",
            base_url="https://test.com",
            model_name="test-v1",
            timeout=60,
            max_tokens=4096,
            temperature=0.7,
            priority=1,
            hourly_limit=100,
            daily_limit=1000,
            enabled=True,
            cost_per_token=0.000001
        )

        assert config.name == "test_model"
        assert config.cost_per_token == 0.000001
        assert config.priority == 1

    def test_prompt_template_dataclass(self):
        from modules.ai.model_manager import PromptTemplate

        template = PromptTemplate(
            template_id="test_template",
            name="Test Template",
            prompt_text="Test prompt",
            version=1,
            created_at=datetime.now(),
            description="Test description"
        )

        assert template.template_id == "test_template"
        assert template.version == 1
        assert template.description == "Test description"

    def test_model_call_dataclass(self):
        from modules.ai.model_manager import ModelCall

        call = ModelCall(
            model_name="test_model",
            prompt="test prompt",
            timestamp=datetime.now(),
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            success=True,
            error=None,
            response_time=1.5,
            cost=0.00015
        )

        assert call.model_name == "test_model"
        assert call.total_tokens == 150
        assert call.cost > 0


class TestAsyncCallProcessor:
    def test_async_processor_initialization(self):
        from modules.ai.model_manager import AsyncCallProcessor

        processor = AsyncCallProcessor(max_workers=2)
        assert processor._max_workers == 2
        assert processor._running is False

    def test_submit_and_get_result(self):
        from modules.ai.model_manager import AsyncCallProcessor

        processor = AsyncCallProcessor(max_workers=1)

        def dummy_func():
            return "result"

        call_id = "test_call_1"
        processor.submit(call_id, dummy_func)

        assert call_id in processor._results
        assert processor._results[call_id]["status"] == "pending"


class TestPromptVersionManager:
    def test_register_template(self):
        from modules.ai.model_manager import PromptVersionManager

        manager = PromptVersionManager()

        with patch("modules.ai.model_manager.get_collection") as mock_get_col:
            mock_collection = MagicMock()
            mock_get_col.return_value = mock_collection

            template = manager.register_template(
                template_id="comprehensive_analysis",
                name="Comprehensive Analysis",
                prompt_text="Analyze {code}",
                description="For comprehensive stock analysis"
            )

            assert template.template_id == "comprehensive_analysis"
            assert template.version == 1
            assert template.name == "Comprehensive Analysis"

    def test_rollback(self):
        from modules.ai.model_manager import PromptVersionManager

        manager = PromptVersionManager()

        with patch("modules.ai.model_manager.get_collection") as mock_get_col:
            mock_collection = MagicMock()
            mock_get_col.return_value = mock_collection

            manager.register_template(
                template_id="test_template",
                name="Test V1",
                prompt_text="Version 1"
            )

            manager.register_template(
                template_id="test_template",
                name="Test V2",
                prompt_text="Version 2"
            )

            result = manager.rollback("test_template", 1)
            assert result is True

            active = manager.get_active_template("test_template")
            assert active.version == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])