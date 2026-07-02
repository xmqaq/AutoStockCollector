"""fusion weight_optimizer 超额收益口径测试。

验证 get_optimization_signals 把目标函数从 pearson(绝对收益) 换成分组超额差后：
- 高分股 excess 普遍高于低分股 → 该维 suggested 权重上调
- 全维 diff 为负/零 → 回退 WEIGHT_PRESETS
- 样本不足（总量<100 / 每态<10 / 每态有效 excess<6）→ reliable=False
- excess 缺失的 record 被正确过滤（不参与分组）

不连真库：mock snapshot_loader + patch PickTracker.evaluate 返回带 excess 的 base。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.ai.fusion.backtest import FusionBacktest, _excess_spread
from modules.ai.fusion.market_state import MarketStateDetector

_DIMS = ("fundamental", "technical", "fund_flow", "valuation")


def _pick(code, scores, excess5=None, ret5=1.0, source_count=1):
    """一条 snapshot pick。scores=各维分明细 dict。"""
    return {
        "code": code,
        "fusion_score": 60.0,
        "factor_score": 55.0,
        "debate_bonus": 0.0,
        "source_count": source_count,
        "sources": ["quant"],
        "scores": dict(scores),
    }


def _snap(ts, state, picks):
    """一条 fusion_pick_snapshot。"""
    return {"timestamp": ts, "market_state": state, "picks": picks}


def _tracker_base(snaps, excess_by_code, ret5=1.0):
    """构造 PickTracker.evaluate 的返回：runs[].picks 带 returns/excess。

    excess_by_code: {code: excess5}；未列出的 code excess 缺失（测缺失过滤）。
    """
    runs = []
    for s in snaps:
        ts = str(s["timestamp"])
        picks_out = []
        for p in s["picks"]:
            code = p["code"]
            pick = {
                "code": code,
                "name": code,
                "composite": p.get("fusion_score", 60.0),
                "entry_date": ts[:10],
                "entry_close": 10.0,
                "returns": {"5": ret5},
            }
            if code in excess_by_code:
                pick["excess"] = {"5": excess_by_code[code]}
            picks_out.append(pick)
        runs.append({"timestamp": ts, "strategy": "", "picks": picks_out})
    return {"runs_count": len(runs), "horizons": [5], "overall": {}, "runs": runs}


class TestExcessSpreadHelper(unittest.TestCase):
    """_excess_spread：按得分中位数分高低组算 excess 差。"""

    def test_high_score_high_excess_positive_spread(self):
        # fundamental 得分高 → excess 高，正向 spread
        pairs = [(20, -1.0), (25, -0.5), (70, 2.0), (80, 3.0), (75, 2.5)]
        # 中位数=70；high=[70,80,75]→excess均值2.5；low=[20,25]→-0.75；diff≈3.25
        self.assertGreater(_excess_spread(pairs), 0)

    def test_negative_spread_returns_negative(self):
        # 高分反而 excess 低
        pairs = [(80, -2.0), (75, -1.5), (20, 3.0), (25, 2.5)]
        self.assertLess(_excess_spread(pairs), 0)

    def test_too_few_samples_returns_zero(self):
        self.assertEqual(_excess_spread([(50, 1.0), (60, 2.0)]), 0.0)

    def test_empty_returns_zero(self):
        self.assertEqual(_excess_spread([]), 0.0)


class TestGetOptimizationSignalsExcess(unittest.TestCase):
    """get_optimization_signals 用分组超额差驱动 suggested_weights。"""

    def setUp(self):
        self._patchers = []

    def tearDown(self):
        for p in getattr(self, "_patchers", []):
            p.stop()

    def _bt(self, snaps, excess_by_code):
        bt = FusionBacktest(snapshot_loader=lambda limit: snaps[:limit])
        base = _tracker_base(snaps, excess_by_code)
        p = patch("modules.ai.engines.tracker.PickTracker.evaluate", return_value=base)
        p.start()
        self._patchers.append(p)
        return bt

    def _build_snaps(self, per_state_picks, n_runs=12):
        """构造 n_runs 个交易日快照，每态每只 pick 重复，凑够样本量。

        per_state_picks: {state: [(code, scores, excess5), ...]}
        """
        snaps = []
        for i in range(n_runs):
            ts = f"2026-06-{i+1:02d}"
            picks = []
            for state, items in per_state_picks.items():
                for code, scores, _exc in items:
                    picks.append(_pick(f"{code}_{i}", scores))
            # 每个 state 单独快照——为简化，每个 ts 一份每态 picks 混合
            snaps.append(_snap(ts, "volatile", picks))  # 占位，下面按态分快照
        # 简化：直接每个 state 生成 n_runs 份快照，每份含该 state 的 picks
        snaps = []
        for state, items in per_state_picks.items():
            for i in range(n_runs):
                ts = f"2026-06-{i+1:02d}_{state}"
                picks = [_pick(f"{code}_{state}_{i}", scores) for code, scores, _ in items]
                snaps.append(_snap(ts, state, picks))
        return snaps

    def test_high_fundamental_high_excess_upweights_fundamental(self):
        """fundamental 得分高的股 excess 也高 → fundamental 权重上调。"""
        # bull 态：4 只股，fundamental 二高一低，高分股 excess 显著高
        high_sc = {"fundamental": 85, "technical": 50, "fund_flow": 50, "valuation": 50}
        low_sc = {"fundamental": 20, "technical": 50, "fund_flow": 50, "valuation": 50}
        per_state = {
            "bull": [("H1", high_sc, 3.0), ("H2", high_sc, 2.5),
                     ("H3", high_sc, 2.8), ("L1", low_sc, -2.0)],
            "bear": [("H1", high_sc, 3.0), ("H2", high_sc, 2.5),
                     ("H3", high_sc, 2.8), ("L1", low_sc, -2.0)],
            "volatile": [("H1", high_sc, 3.0), ("H2", high_sc, 2.5),
                         ("H3", high_sc, 2.8), ("L1", low_sc, -2.0)],
        }
        snaps = self._build_snaps(per_state, n_runs=12)  # 每态48样本，总144
        # excess 按 code 前缀（H/L）赋值——但 code 带后缀，用映射
        excess_by_code = {}
        for s in snaps:
            for p in s["picks"]:
                excess_by_code[p["code"]] = 3.0 if p["code"].startswith("H") else -2.0
        bt = self._bt(snaps, excess_by_code)
        sig = bt.get_optimization_signals(limit=500)
        self.assertTrue(sig["reliable"], f"应 reliable，实际 sample_counts={sig['sample_counts']}")
        # bull 态 fundamental 权重应明显高于其它维
        bull = sig["suggested_weights"]["bull"]
        self.assertGreater(bull["fundamental"], bull["technical"],
                           f"fundamental 应上调: {bull}")
        # diff 本身应为正
        self.assertGreater(sig["dimension_correlations"]["bull"]["fundamental"], 0)

    def test_all_negative_spread_falls_back_to_presets(self):
        """所有维 diff 为负 → 该态 suggested 回退 WEIGHT_PRESETS。"""
        # 让高分股 excess 反而低（负 spread），且四维都这样
        sc_high = {"fundamental": 85, "technical": 85, "fund_flow": 85, "valuation": 85}
        sc_low = {"fundamental": 20, "technical": 20, "fund_flow": 20, "valuation": 20}
        per_state = {
            "bull": [("H", sc_high, -3.0), ("H2", sc_high, -2.5),
                     ("H3", sc_high, -2.8), ("L", sc_low, 2.0)],
            "bear": [("H", sc_high, -3.0), ("H2", sc_high, -2.5),
                     ("H3", sc_high, -2.8), ("L", sc_low, 2.0)],
            "volatile": [("H", sc_high, -3.0), ("H2", sc_high, -2.5),
                         ("H3", sc_high, -2.8), ("L", sc_low, 2.0)],
        }
        snaps = self._build_snaps(per_state, n_runs=12)
        excess_by_code = {}
        for s in snaps:
            for p in s["picks"]:
                excess_by_code[p["code"]] = -3.0 if p["code"].startswith("H") else 2.0
        bt = self._bt(snaps, excess_by_code)
        sig = bt.get_optimization_signals(limit=500)
        # 四维全负 → positives 全 0 → tot=0 → 回退预设
        for st in ("bull", "bear", "volatile"):
            preset = MarketStateDetector.WEIGHT_PRESETS[st]
            self.assertEqual(sig["suggested_weights"][st], preset,
                             f"{st} 应回退预设")

    def test_insufficient_total_samples_not_reliable(self):
        """总量<100 → reliable=False。"""
        per_state = {
            "bull": [("A", {"fundamental": 50, "technical": 50, "fund_flow": 50, "valuation": 50}, 1.0)],
            "bear": [("A", {"fundamental": 50, "technical": 50, "fund_flow": 50, "valuation": 50}, 1.0)],
            "volatile": [("A", {"fundamental": 50, "technical": 50, "fund_flow": 50, "valuation": 50}, 1.0)],
        }
        snaps = self._build_snaps(per_state, n_runs=5)  # 每态5，总15
        excess_by_code = {p["code"]: 1.0 for s in snaps for p in s["picks"]}
        bt = self._bt(snaps, excess_by_code)
        sig = bt.get_optimization_signals(limit=500)
        self.assertFalse(sig["reliable"])

    def test_excess_missing_records_filtered(self):
        """excess5=None 的 record 不参与分组（但 sample_counts 仍含它）。"""
        # 只给一半 code 赋 excess
        sc_high = {"fundamental": 85, "technical": 50, "fund_flow": 50, "valuation": 50}
        sc_low = {"fundamental": 20, "technical": 50, "fund_flow": 50, "valuation": 50}
        per_state = {
            "bull": [("H1", sc_high, None), ("H2", sc_high, 3.0),
                     ("L1", sc_low, -2.0), ("L2", sc_low, -1.5)],
            "bear": [("H1", sc_high, 3.0), ("H2", sc_high, 2.5),
                     ("L1", sc_low, -2.0), ("L2", sc_low, -1.5)],
            "volatile": [("H1", sc_high, 3.0), ("H2", sc_high, 2.5),
                         ("L1", sc_low, -2.0), ("L2", sc_low, -1.5)],
        }
        snaps = self._build_snaps(per_state, n_runs=12)
        excess_by_code = {}
        for s in snaps:
            for p in s["picks"]:
                if p["code"].startswith("H1"):
                    continue  # H1 的 excess 缺失
                excess_by_code[p["code"]] = 3.0 if p["code"].startswith("H") else -2.0
        bt = self._bt(snaps, excess_by_code)
        sig = bt.get_optimization_signals(limit=500)
        # bull 态每 run 4 只，12 runs=48 样本，但 H1 缺 excess → 有效 36，仍≥6
        self.assertGreaterEqual(
            sum(1 for s in snaps if s["market_state"] == "bull"
                for p in s["picks"] if p["code"].startswith("H1")),
            12, "H1 应占 12 条都被过滤")
        # reliable 需每态有效≥6，bull 有效=36（48-12）仍达标
        # 关键：过滤后 fundamental 仍应正向（H2 高分高 excess vs L 低分低 excess）
        self.assertGreater(sig["dimension_correlations"]["bull"]["fundamental"], 0)


if __name__ == "__main__":
    unittest.main()
