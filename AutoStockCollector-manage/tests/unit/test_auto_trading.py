"""auto_trading 模块单元测试：mock MongoDB 与 PA，不依赖真实数据库/行情。

覆盖：
- signal_fusion 分母归一化（5 场景）
- decision_engine 优先级（各命中）
- risk_manager 各 check
- drawdown_strategy _evaluate
- config_store load/save
- risk_manager.normalize_for_trade / decision_engine 计算
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.auto_trading.config import AutoTradingConfig
from modules.auto_trading.signal_fusion import FusedSignal, SignalFusionEngine, PA_SIGNAL_SCORES
from modules.auto_trading.drawdown_strategy import (
    DrawdownChecker, DrawdownStrategyConfig, DrawdownVerdict,
)
from modules.auto_trading.risk_manager import RiskManager, _limit_threshold
from modules.auto_trading.decision_engine import Decision, DecisionEngine
from modules.auto_trading.config_store import ConfigStore


def _cfg() -> AutoTradingConfig:
    return AutoTradingConfig()


# ── signal_fusion 分母归一化 ────────────────────────────────────
class TestFusionDenominator(unittest.TestCase):
    def _engine(self):
        eng = SignalFusionEngine()
        eng._pa_engine = MagicMock()
        eng._pa_engine.analyze.return_value = {"signal": "NO_DATA", "confidence": 0}
        eng._config_store = MagicMock()
        eng._config_store.load.return_value = _cfg()
        return eng

    def _db_mock(self, auction_top=None, monitor_doc=None, agent_doc=None):
        """单一 db mock，保证 __getitem__ 返回同一 collection mock。"""
        db = MagicMock()
        auction_col = MagicMock()
        auction_col.find_one.return_value = (
            {"top_stocks": auction_top} if auction_top is not None else None
        )
        monitor_col = MagicMock()
        monitor_col.find_one.return_value = monitor_doc
        agent_col = MagicMock()
        agent_col.find_one.return_value = agent_doc
        db.__getitem__.side_effect = lambda k: {
            "auction_results": auction_col,
            "monitor_signal_history": monitor_col,
            "agent_signals": agent_col,
        }[k]
        return db

    def test_all_three_sources(self):
        eng = self._engine()
        db = self._db_mock(
            auction_top=[{"symbol": "600000", "strength_score": 90, "gap_pct": 5.0,
                          "trap_warning": {"is_trap": False}, "industry": "银行", "name": "浦发银行"}],
            monitor_doc={"code": "600000", "composite": {"score": 80, "signal": "buy"},
                         "price": 10.0, "name": "浦发银行"},
        )
        eng._pa_engine.analyze.return_value = {"signal": "BUY_SETUP", "confidence": 4,
                                                "current_price": 10.0, "name": "浦发银行"}
        with patch("modules.auto_trading.signal_fusion.DatabaseConfig.get_database", return_value=db):
            fused = eng.fuse("600000", "2026-07-01", use_cache=False)
        # 三源齐全（agent 无当日信号不参与）：auction=90, PA=95*0.8=76(conf=4/5), ai=80
        # 默认权重 0.20/0.30/0.30：norm = 0.20*0.9 + 0.30*0.95*0.8 + 0.30*0.8
        #                      = 0.18 + 0.228 + 0.24 = 0.648; active=0.80 → 81.0
        self.assertAlmostEqual(fused.overall_score, 81.0, places=1)
        self.assertEqual(fused.signal, "strong_buy")

    def test_missing_auction(self):
        """缺 auction：分数应只在 PA+AI 间按权重归一，不被 0.3 权重拉低。"""
        eng = self._engine()
        db = self._db_mock(
            auction_top=None,
            monitor_doc={"code": "600000", "composite": {"score": 80, "signal": "buy"}, "price": 10.0},
        )
        eng._pa_engine.analyze.return_value = {"signal": "BUY_SETUP", "confidence": 4, "current_price": 10.0}
        with patch("modules.auto_trading.signal_fusion.DatabaseConfig.get_database", return_value=db):
            fused = eng.fuse("600000", "2026-07-01", use_cache=False)
        # 缺 auction（agent 无当日信号也不参与）：PA=95*0.8=76(w=0.30), AI=80(w=0.30)
        # norm_p=0.228, norm_m=0.24; active=0.60, numerator=0.468 → 78.0
        self.assertAlmostEqual(fused.overall_score, 78.0, places=1)

    def test_agent_signal_participates_in_fusion(self):
        """第 4 路 agent 信号参与融合：auction=90, PA=BUY_SETUP(76), ai=80, agent=90。
        四源齐全：norm = 0.20*0.9 + 0.30*0.95*0.8 + 0.30*0.8 + 0.20*0.9
                = 0.18 + 0.228 + 0.24 + 0.18 = 0.828; active=1.00 → 82.8
        对比 test_all_three_sources（agent 无数据 81.0），agent 90 分使 overall 上移到 82.8。"""
        eng = self._engine()
        db = self._db_mock(
            auction_top=[{"symbol": "600000", "strength_score": 90, "gap_pct": 5.0,
                          "trap_warning": {"is_trap": False}, "industry": "银行", "name": "浦发银行"}],
            monitor_doc={"code": "600000", "composite": {"score": 80, "signal": "buy"},
                         "price": 10.0, "name": "浦发银行"},
            agent_doc={"code": "600000", "trade_date": "2026-07-01",
                       "agent_score": 90, "agent_signal": "buy", "name": "浦发银行"},
        )
        eng._pa_engine.analyze.return_value = {"signal": "BUY_SETUP", "confidence": 4,
                                                "current_price": 10.0, "name": "浦发银行"}
        with patch("modules.auto_trading.signal_fusion.DatabaseConfig.get_database", return_value=db):
            fused = eng.fuse("600000", "2026-07-01", use_cache=False)
        self.assertAlmostEqual(fused.agent_score, 90.0, places=1)
        self.assertAlmostEqual(fused.overall_score, 82.8, places=1)
        self.assertEqual(fused.signal, "strong_buy")
        self.assertIn("AI Agent 90分", fused.reasons)

    def test_agent_signal_expired_not_used(self):
        """隔夜 agent 信号（trade_date 不匹配当日）不应参与融合——被 date 过滤。"""
        eng = self._engine()
        db = self._db_mock(
            auction_top=None,  # 也无 auction，确保 overall 只由 PA+AI 决定
            monitor_doc={"code": "600000", "composite": {"score": 80, "signal": "buy"}, "price": 10.0},
            # agent 文档存在但 trade_date 是昨天——_merge_agent 用 {code, trade_date:date} 查不到
            agent_doc=None,
        )
        eng._pa_engine.analyze.return_value = {"signal": "BUY_SETUP", "confidence": 4, "current_price": 10.0}
        with patch("modules.auto_trading.signal_fusion.DatabaseConfig.get_database", return_value=db):
            fused = eng.fuse("600000", "2026-07-01", use_cache=False)
        # agent_score 应为 0（被过滤），overall 与 test_missing_auction 同源同分 78.0
        self.assertEqual(fused.agent_score, 0.0)
        self.assertAlmostEqual(fused.overall_score, 78.0, places=1)

    def test_all_missing_returns_neutral(self):
        eng = self._engine()
        db = self._db_mock(auction_top=None, monitor_doc=None)
        eng._pa_engine.analyze.return_value = {"signal": "NO_DATA", "confidence": 0}
        with patch("modules.auto_trading.signal_fusion.DatabaseConfig.get_database", return_value=db):
            fused = eng.fuse("600000", "2026-07-01", use_cache=False)
        self.assertEqual(fused.overall_score, 50.0)
        self.assertEqual(fused.signal, "hold")


# ── drawdown _evaluate ─────────────────────────────────────────
class TestDrawdownEvaluate(unittest.TestCase):
    def setUp(self):
        self.checker = DrawdownChecker()
        self.checker._config_mgr = MagicMock()
        self.checker._peak_tracker = MagicMock()

    def _cfg(self, **kw):
        base = DrawdownStrategyConfig(enabled=True)
        for k, v in kw.items():
            setattr(base, k, v)
        return base

    def test_max_drawdown_hard_stop(self):
        self.checker._config_mgr.load.return_value = self._cfg(max_drawdown_pct=15.0)
        self.checker._peak_tracker.get.return_value = 10.0
        pos = {"code": "600000", "shares": 1000, "current_price": 8.0, "avg_cost": 9.0}
        # max_dd = (10-8)/10 = 20% >= 15% → sell, priority 90
        v = self.checker.evaluate_one(pos)
        self.assertTrue(v.hit)
        self.assertEqual(v.action, "sell")
        self.assertEqual(v.priority, 90)

    def test_trailing_reduce(self):
        self.checker._config_mgr.load.return_value = self._cfg(
            max_drawdown_pct=15.0, trailing_stop_pct=5.0, trailing_action="reduce",
            profit_lock_enabled=True, profit_lock_threshold=3.0,
        )
        self.checker._peak_tracker.get.return_value = 10.0
        pos = {"code": "600000", "shares": 1000, "current_price": 9.4, "avg_cost": 9.0}
        # max_dd = 6% >= 5%, pnl = (9.4-9)/9=4.4% >= 3% profit_lock → reduce
        v = self.checker.evaluate_one(pos)
        self.assertTrue(v.hit)
        self.assertEqual(v.action, "reduce")
        self.assertEqual(v.priority, 70)

    def test_profit_lock_blocks_trailing(self):
        self.checker._config_mgr.load.return_value = self._cfg(
            trailing_stop_pct=5.0, profit_lock_enabled=True, profit_lock_threshold=3.0,
        )
        self.checker._peak_tracker.get.return_value = 10.0
        pos = {"code": "600000", "shares": 1000, "current_price": 9.4, "avg_cost": 9.5}
        # pnl = (9.4-9.5)/9.5 = -1.05% < 3% → profit_lock 未达 → None
        v = self.checker.evaluate_one(pos)
        self.assertIsNone(v)

    def test_disabled_returns_none(self):
        self.checker._config_mgr.load.return_value = self._cfg(enabled=False)
        pos = {"code": "600000", "shares": 1000, "current_price": 8.0, "avg_cost": 9.0}
        self.assertIsNone(self.checker.evaluate_one(pos))


# ── risk_manager 单项 ──────────────────────────────────────────
class TestRiskManager(unittest.TestCase):
    def _rm(self, cash=100000.0):
        engine = MagicMock()
        account = MagicMock()
        account.get.return_value = {"cash_balance": cash}
        store = MagicMock()
        store.load.return_value = _cfg()
        return RiskManager(engine, account, store)

    def test_check_st(self):
        rm = self._rm()
        ok, _ = rm._check_st("浦发银行")
        self.assertTrue(ok)
        ok, reason = rm._check_st("*ST 某某")
        self.assertFalse(ok)
        self.assertIn("ST", reason)

    def test_check_st_delisted(self):
        rm = self._rm()
        # PT 股票：parse_stock_name 的 "pt" 模式正确映射到 is_pt
        ok, _ = rm._check_st("PT 某某")
        self.assertFalse(ok)

    def test_check_sector_over_limit(self):
        rm = self._rm()
        held = [{"industry": "银行", "market_value": 30000}]
        # this_cost=3000, sector_used=30000, cash=100000, cap=0.30*100000=30000
        # total=33000 > 30000 → block
        ok, reason = rm._check_sector("600000", "银行", held, 3000, 100000, _cfg())
        self.assertFalse(ok)
        self.assertIn("板块", reason)

    def test_check_sector_within_limit(self):
        rm = self._rm()
        held = [{"industry": "银行", "market_value": 10000}]
        ok, _ = rm._check_sector("600000", "银行", held, 5000, 100000, _cfg())
        self.assertTrue(ok)

    def test_check_total_exposure_over_limit(self):
        rm = self._rm()
        held = [{"market_value": 75000}]  # cash=100000, held_mv=75000, exposure=75%
        # this_cost=10000 → (75000+10000)/175000=48.5%... but cap=80%; need bigger
        held = [{"market_value": 80000}]
        ok, reason = rm._check_total_exposure(held, 15000, 100000, _cfg())
        # (80000+15000)/(80000+100000)=95000/180000=52.7% < 80% → ok
        self.assertTrue(ok)
        # push over: held_mv=80000, this=100000 → 180000/180000=100% > 80%
        ok, reason = rm._check_total_exposure(held, 100000, 100000, _cfg())
        self.assertFalse(ok)
        self.assertIn("敞口", reason)

    def test_check_limit_up_block(self):
        rm = self._rm()
        # 主板 600000，涨停 +10% ≥ 9.8% → block
        ok, reason = rm._check_limit("600000", 11.0, 10.0, _cfg())
        self.assertFalse(ok)
        self.assertIn("涨停", reason)

    def test_check_limit_normal(self):
        rm = self._rm()
        ok, _ = rm._check_limit("600000", 10.3, 10.0, _cfg())  # +3%
        self.assertTrue(ok)

    def test_limit_threshold(self):
        self.assertEqual(_limit_threshold("600000"), 9.8)
        self.assertEqual(_limit_threshold("300001"), 19.5)
        self.assertEqual(_limit_threshold("688001"), 19.5)
        self.assertEqual(_limit_threshold("830001"), 29.5)

    def test_normalize_for_trade(self):
        self.assertEqual(RiskManager.normalize_for_trade("600000"), "SH600000")
        self.assertEqual(RiskManager.normalize_for_trade("SZ000001"), "SZ000001")
        self.assertEqual(RiskManager.normalize_for_trade("300001"), "SZ300001")
        self.assertEqual(RiskManager.normalize_for_trade("830001"), "BJ830001")

    def test_check_not_traded_today_hit(self):
        rm = self._rm()
        with patch("modules.auto_trading.risk_manager.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find.return_value = [{"code": "SH600000"}]
            m.return_value = {"trade_records": col}
            ok, reason = rm._check_not_traded_today("default", "600000", "2026-07-01")
        self.assertFalse(ok)
        self.assertIn("已自动建仓", reason)

    def test_check_not_traded_today_miss(self):
        rm = self._rm()
        with patch("modules.auto_trading.risk_manager.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find.return_value = [{"code": "SH000001"}]  # 不同票
            m.return_value = {"trade_records": col}
            ok, _ = rm._check_not_traded_today("default", "600000", "2026-07-01")
        self.assertTrue(ok)

    def test_check_not_reduced_today_with_prefix(self):
        """code 带前缀（如 SH688012）也应正确匹配 db 里的 SH688012。"""
        rm = self._rm()
        with patch("modules.auto_trading.risk_manager.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find.return_value = [{"code": "SH688012"}]
            m.return_value = {"trade_records": col}
            ok, reason = rm.check_not_reduced_today("default", "SH688012", "2026-07-01")
        self.assertFalse(ok)

    def test_check_not_reduced_today_miss(self):
        rm = self._rm()
        with patch("modules.auto_trading.risk_manager.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find.return_value = [{"code": "SH000001"}]
            m.return_value = {"trade_records": col}
            ok, _ = rm.check_not_reduced_today("default", "SH688012", "2026-07-01")
        self.assertTrue(ok)


# ── decision_engine 优先级 ─────────────────────────────────────
class TestDecisionEngine(unittest.TestCase):
    def _de(self, drawdown_verdict=None, risk_ok=True):
        fusion = MagicMock()
        drawdown = MagicMock()
        drawdown.evaluate_one.return_value = drawdown_verdict
        risk = MagicMock()
        risk.check_buy.return_value = (risk_ok, "ok")
        risk.check_add.return_value = (risk_ok, "ok")
        risk.check_sell.return_value = (True, "ok")
        risk.check_not_reduced_today.return_value = (True, "ok")
        store = MagicMock()
        store.load.return_value = _cfg()
        account = MagicMock()
        return DecisionEngine(fusion, drawdown, risk, store, account)

    def _fused(self, score=50):
        f = FusedSignal("600000", "浦发银行")
        f.overall_score = score
        f.signal = "hold"
        f.current_price = 10.0
        f.industry = "银行"
        return f

    def test_sl_tp_priority(self):
        de = self._de()
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "sl_hit": True}
        d = de.decide_held(pos, self._fused(80), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "sell")
        self.assertEqual(d.source, "sl_tp")
        self.assertEqual(d.priority, 100)

    def test_drawdown_max_dd_priority(self):
        verdict = DrawdownVerdict(hit=True, action="sell", shares=1000, reason="回撤", priority=90)
        de = self._de(drawdown_verdict=verdict)
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "avg_cost": 9.0, "sl_hit": False, "tp_hit": False}
        d = de.decide_held(pos, self._fused(80), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "sell")
        self.assertEqual(d.source, "drawdown_stop")
        self.assertEqual(d.priority, 90)

    def test_fusion_sell_priority(self):
        de = self._de()
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "sl_hit": False, "tp_hit": False}
        d = de.decide_held(pos, self._fused(10), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "sell")
        self.assertEqual(d.source, "fusion")
        self.assertEqual(d.priority, 60)

    def test_fusion_reduce_priority(self):
        de = self._de()
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "sl_hit": False, "tp_hit": False}
        d = de.decide_held(pos, self._fused(30), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "reduce")
        self.assertEqual(d.priority, 50)

    def test_reduce_blocked_when_already_reduced_today(self):
        """今日已减仓过 → 本轮 hold，不重复减仓（防每轮减半直到清仓）。"""
        de = self._de()
        de._risk.check_not_reduced_today.return_value = (False, "今日已自动减仓/卖出")
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "sl_hit": False, "tp_hit": False}
        d = de.decide_held(pos, self._fused(30), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "hold")

    def test_hold(self):
        de = self._de()
        pos = {"code": "600000", "name": "浦发银行", "shares": 1000, "current_price": 10.0,
               "pnl_percent": 5, "sl_hit": False, "tp_hit": False}
        d = de.decide_held(pos, self._fused(55), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "hold")

    def test_candidate_buy(self):
        de = self._de(risk_ok=True)
        cand = {"symbol": "600000", "name": "浦发银行"}
        d = de.decide_candidate(cand, self._fused(80), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "buy")
        self.assertEqual(d.priority, 30)
        self.assertTrue(d.shares >= 100)

    def test_candidate_below_threshold_hold(self):
        de = self._de(risk_ok=True)
        cand = {"symbol": "600000", "name": "浦发银行"}
        d = de.decide_candidate(cand, self._fused(50), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "hold")

    def test_candidate_risk_blocked(self):
        de = self._de(risk_ok=False)
        cand = {"symbol": "600000", "name": "浦发银行"}
        d = de.decide_candidate(cand, self._fused(80), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "hold")

    def test_auction_radar_candidate_buy(self):
        """竞价信号分支：source=auction_radar 走独立阈值，source=auction_radar。"""
        de = self._de(risk_ok=True)
        cand = {"code": "600000", "name": "浦发银行", "source": "auction_radar",
                "strength_score": 85, "gap_pct": 4.0, "open_price": 10.0}
        d = de.decide_candidate(cand, self._fused(50), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "buy")
        self.assertEqual(d.source, "auction_radar")
        self.assertEqual(d.priority, 30)

    def test_auction_radar_candidate_below_score_hold(self):
        de = self._de(risk_ok=True)
        cand = {"code": "600000", "source": "auction_radar", "strength_score": 60,
                "gap_pct": 4.0, "open_price": 10.0}
        d = de.decide_candidate(cand, self._fused(50), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "hold")

    def test_eod_close_intraday_force(self):
        """14:50 对竞价日内持仓强制平仓，force=True 豁免 T+1。"""
        de = self._de()
        # mock _is_eod_close_time 返回 True
        with patch.object(DecisionEngine, "_is_eod_close_time", return_value=True):
            pos = {"code": "600000", "name": "浦发银行", "shares": 1000,
                   "current_price": 10.0, "pnl_percent": 5, "_is_intraday": True,
                   "sl_hit": False, "tp_hit": False}
            d = de.decide_held(pos, self._fused(80), 100000, "default", "2026-07-01", [])
        self.assertEqual(d.action, "sell")
        self.assertEqual(d.source, "eod_close_intraday")
        self.assertEqual(d.priority, 85)
        self.assertTrue(d.force)


# ── config_store ───────────────────────────────────────────────
class TestConfigStore(unittest.TestCase):
    def test_load_no_doc_returns_defaults(self):
        store = ConfigStore()
        with patch("modules.auto_trading.config_store.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find_one.return_value = None
            m.return_value = MagicMock()
            m.return_value.__getitem__.return_value = col
            cfg = store.load()
        self.assertEqual(cfg.AUCTION_WEIGHT, 0.20)
        self.assertEqual(cfg.AGENT_WEIGHT, 0.20)
        self.assertEqual(cfg.MAX_POSITIONS, 8)

    def test_save_validates_and_persists(self):
        store = ConfigStore()
        with patch("modules.auto_trading.config_store.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find_one.return_value = None
            m.return_value = MagicMock()
            m.return_value.__getitem__.return_value = col
            # 四路和需≈1.0：auction 0.35 + pa 0.20 + ai_monitor 0.25 + agent 默认 0.20 = 1.00
            cfg = store.save({"weights": {"auction": 0.35, "pa": 0.20, "ai_monitor": 0.25}})
        self.assertEqual(cfg.AUCTION_WEIGHT, 0.35)
        col.replace_one.assert_called_once()

    def test_save_rejects_bad_weights(self):
        store = ConfigStore()
        with patch("modules.auto_trading.config_store.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find_one.return_value = None
            m.return_value = MagicMock()
            m.return_value.__getitem__.return_value = col
            with self.assertRaises(ValueError):
                store.save({"weights": {"auction": 0.9, "pa": 0.9, "ai_monitor": 0.9}})

    def test_save_rejects_bad_max_positions(self):
        store = ConfigStore()
        with patch("modules.auto_trading.config_store.DatabaseConfig.get_database") as m:
            col = MagicMock()
            col.find_one.return_value = None
            m.return_value = MagicMock()
            m.return_value.__getitem__.return_value = col
            with self.assertRaises(ValueError):
                store.save({"risk": {"max_positions": 100}})


if __name__ == "__main__":
    unittest.main()
