"""融合选股回测。对 fusion_pick_snapshots 历史快照计算后续收益/胜率。

复用 PickTracker 的全部底层逻辑（K线读取、基准计算、收益聚合），
只把数据源换成 fusion_pick_snapshots，并在其结果上做市场状态/来源/相关性的二次聚合。
"""
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

_DIMS = ("fundamental", "technical", "fund_flow", "valuation")
_PRIMARY_HORIZON = 5  # 胜率/相关性统一以 5 日收益为口径


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return 0.0
    return round(cov / ((vx * vy) ** 0.5), 3)


def _win_rate(rets: List[float]) -> Optional[float]:
    if not rets:
        return None
    return round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1)


def _avg(rets: List[float]) -> Optional[float]:
    if not rets:
        return None
    return round(sum(rets) / len(rets), 2)


def _load_snapshots(limit: int) -> List[Dict[str, Any]]:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    cur = db["fusion_pick_snapshots"].find(
        {"picks.0": {"$exists": True}}, {"_id": 0},
    ).sort("created_at", -1).limit(limit)
    return list(cur)


class FusionBacktest:
    def __init__(self, snapshot_loader=None):
        # 注入便于测试；默认读 fusion_pick_snapshots
        self.snapshot_loader = snapshot_loader or _load_snapshots

    # ──────────────────────────────────────────────────────────────
    # 把 PickTracker 的逐 pick 收益与快照元数据（市场状态/来源/各维得分）join 起来
    # ──────────────────────────────────────────────────────────────

    def _records(self, limit: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """返回 (扁平记录列表, PickTracker.evaluate 原始结果)。
        每条记录：{market_state, source_count, sources, fusion_score, factor_score,
                  scores{dim}, ret5}
        """
        from modules.ai.engines.tracker import PickTracker

        runs = self.snapshot_loader(limit)
        # PickTracker.results_loader(limit) → runs；快照已限量，直接切片返回
        tracker = PickTracker(results_loader=lambda lim: runs[:lim])
        base = tracker.evaluate(horizons=(1, 3, 5, 10), limit=limit)

        # (timestamp, code) → 5日收益
        ret_map: Dict[Tuple[str, str], float] = {}
        for run in base.get("runs", []):
            ts = str(run.get("timestamp", ""))
            for p in run.get("picks", []):
                r = (p.get("returns") or {}).get(str(_PRIMARY_HORIZON))
                if r is not None:
                    ret_map[(ts, p.get("code", ""))] = r

        records: List[Dict[str, Any]] = []
        for snap in runs:
            ts = str(snap.get("timestamp", ""))
            state = snap.get("market_state", "volatile")
            for p in snap.get("picks", []):
                code = p.get("code", "")
                ret5 = ret_map.get((ts, code))
                if ret5 is None:
                    continue
                records.append({
                    "market_state": state,
                    "source_count": int(p.get("source_count", 1) or 1),
                    "sources": p.get("sources", []),
                    "fusion_score": float(p.get("fusion_score", p.get("composite", 0)) or 0),
                    "factor_score": float(p.get("factor_score", 0) or 0),
                    "debate_bonus": float(p.get("debate_bonus", 0) or 0),
                    "scores": p.get("scores", {}) or {},
                    "ret5": float(ret5),
                })
        return records, base

    # ──────────────────────────────────────────────────────────────
    # evaluate
    # ──────────────────────────────────────────────────────────────

    def evaluate(self, horizons=(1, 3, 5, 10), limit: int = 30) -> Dict[str, Any]:
        records, base = self._records(limit)

        # 市场状态分组
        by_state: Dict[str, Dict[str, Any]] = {}
        for st in ("bull", "bear", "volatile"):
            rs = [r["ret5"] for r in records if r["market_state"] == st]
            by_state[st] = {"n": len(rs), "win_rate": _win_rate(rs), "avg_return": _avg(rs)}

        # 来源分组：只被量化选中 vs 多来源
        quant_only = [r["ret5"] for r in records if r["source_count"] <= 1]
        multi = [r["ret5"] for r in records if r["source_count"] > 1]
        by_source = {
            "quant_only": {"n": len(quant_only), "win_rate": _win_rate(quant_only)},
            "multi_source": {"n": len(multi), "win_rate": _win_rate(multi)},
        }

        # 相关性
        rets = [r["ret5"] for r in records]
        fusion_corr = _pearson([r["fusion_score"] for r in records], rets)
        factor_corr = _pearson([r["factor_score"] for r in records], rets)

        # debate_bonus 有效性：直接读快照存的 debate_bonus（融合分已非简单相加，不能反推）
        pos, nonpos = [], []
        for r in records:
            (pos if r.get("debate_bonus", 0) > 0 else nonpos).append(r["ret5"])
        wr_pos = _win_rate(pos)
        wr_nonpos = _win_rate(nonpos)
        debate_eff = round((wr_pos - wr_nonpos), 1) if (wr_pos is not None and wr_nonpos is not None) else 0.0

        return {
            "runs_count": base.get("runs_count", 0),
            "horizons": base.get("horizons", list(horizons)),
            "overall": base.get("overall", {}),
            "by_market_state": by_state,
            "by_source": by_source,
            "fusion_score_correlation": fusion_corr,
            "factor_score_correlation": factor_corr,
            "debate_bonus_effectiveness": debate_eff,
            "runs": base.get("runs", []),
        }

    # ──────────────────────────────────────────────────────────────
    # 权重优化建议信号
    # ──────────────────────────────────────────────────────────────

    def get_optimization_signals(self, limit: int = 200) -> Dict[str, Any]:
        records, _ = self._records(limit)

        state_perf: Dict[str, Dict[str, Any]] = {}
        dim_corr: Dict[str, Dict[str, float]] = {}
        suggested: Dict[str, Dict[str, float]] = {}
        sample_counts: Dict[str, int] = {}

        from modules.ai.fusion.market_state import MarketStateDetector
        presets = MarketStateDetector.WEIGHT_PRESETS

        for st in ("bull", "bear", "volatile"):
            srecs = [r for r in records if r["market_state"] == st]
            rets = [r["ret5"] for r in srecs]
            sample_counts[st] = len(srecs)
            state_perf[st] = {"win_rate": _win_rate(rets), "sample_size": len(srecs)}

            corrs: Dict[str, float] = {}
            for dim in _DIMS:
                xs = [float((r["scores"] or {}).get(dim, 0) or 0) for r in srecs]
                corrs[dim] = _pearson(xs, rets)
            dim_corr[st] = corrs

            # 建议权重：正相关归一化；全非正则回退预设
            positives = {d: max(c, 0.0) for d, c in corrs.items()}
            tot = sum(positives.values())
            if tot > 0:
                suggested[st] = {d: round(v / tot, 3) for d, v in positives.items()}
            else:
                suggested[st] = dict(presets[st])

        total = len(records)
        reliable = total >= 100 and all(sample_counts.get(s, 0) >= 10
                                        for s in ("bull", "bear", "volatile"))

        return {
            "state_performance": state_perf,
            "dimension_correlations": dim_corr,
            "suggested_weights": suggested,
            "sample_counts": sample_counts,
            "reliable": reliable,
        }
