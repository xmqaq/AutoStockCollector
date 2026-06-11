"""选股效果跟踪。对历史 ai_pick_results 计算每只 pick 的后续 N 日收益与胜率，
是后续调整评分权重的依据。loader 注入便于测试。

入场口径：选股时间戳当日（含）之后的第一根 K 线收盘价。
盘后选股即当日收盘价，选股后停牌则顺延到复牌首日。
"""
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

KlineRow = Tuple[str, float]  # (date_str, close)


def _default_results_loader(limit: int) -> List[Dict[str, Any]]:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    cursor = db["ai_pick_results"].find(
        {"picks.0": {"$exists": True}},
        {"_id": 0, "timestamp": 1, "strategy": 1,
         "picks.code": 1, "picks.name": 1, "picks.composite": 1},
    ).sort("timestamp", -1).limit(limit)
    return list(cursor)


def _default_kline_loader(code: str, since_date: str, bars: int) -> List[KlineRow]:
    from datetime import datetime
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    try:
        since = datetime.fromisoformat(since_date)
    except ValueError:
        return []
    cursor = db["kline"].find(
        {"code": code, "date": {"$gte": since}},
        {"_id": 0, "date": 1, "close": 1},
    ).sort("date", 1).limit(bars)
    return [(str(r["date"])[:10], float(r.get("close") or 0)) for r in cursor]


def _agg(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"n": 0, "avg": None, "win_rate": None}
    return {
        "n": len(vals),
        "avg": round(sum(vals) / len(vals), 2),
        "win_rate": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
    }


class PickTracker:
    def __init__(
        self,
        results_loader: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
        kline_loader: Optional[Callable[[str, str, int], List[KlineRow]]] = None,
    ):
        self.results_loader = results_loader or _default_results_loader
        self.kline_loader = kline_loader or _default_kline_loader

    def evaluate(self, horizons: Sequence[int] = (1, 3, 5, 10),
                 limit: int = 20) -> Dict[str, Any]:
        hs = sorted({int(h) for h in horizons if int(h) > 0}) or [1]
        max_h = hs[-1]

        runs_out: List[Dict[str, Any]] = []
        overall: Dict[int, List[float]] = {h: [] for h in hs}

        for run in self.results_loader(limit):
            pick_date = str(run.get("timestamp", ""))[:10]
            if not pick_date:
                continue
            picks_out: List[Dict[str, Any]] = []
            run_returns: Dict[int, List[float]] = {h: [] for h in hs}
            evaluated = 0

            for p in run.get("picks", []):
                code = p.get("code", "")
                if not code:
                    continue
                klines = self.kline_loader(code, pick_date, max_h + 1)
                entry_close = klines[0][1] if klines else 0.0
                rets: Dict[str, float] = {}
                if entry_close > 0:
                    evaluated += 1
                    for h in hs:
                        if len(klines) > h:
                            r = round((klines[h][1] / entry_close - 1) * 100, 2)
                            rets[str(h)] = r
                            run_returns[h].append(r)
                            overall[h].append(r)
                picks_out.append({
                    "code": code,
                    "name": p.get("name", ""),
                    "composite": p.get("composite"),
                    "entry_date": klines[0][0] if klines else None,
                    "entry_close": entry_close if entry_close > 0 else None,
                    "returns": rets,
                })

            runs_out.append({
                "timestamp": run.get("timestamp", ""),
                "strategy": run.get("strategy", ""),
                "picks_count": len(run.get("picks", [])),
                "evaluated": evaluated,
                "returns": {str(h): _agg(run_returns[h]) for h in hs},
                "picks": picks_out,
            })

        return {
            "runs_count": len(runs_out),
            "horizons": hs,
            "overall": {str(h): _agg(overall[h]) for h in hs},
            "runs": runs_out,
        }
