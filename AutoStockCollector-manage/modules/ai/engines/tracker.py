"""选股效果跟踪。对历史 ai_pick_results 计算每只 pick 的后续 N 日收益与胜率，
并与同窗口等权全市场基准对比（超额收益/跑赢率），是后续调整评分权重的依据。
loader 注入便于测试。

入场口径：选股时间戳当日（含）之后的第一根 K 线收盘价。
盘后选股即当日收盘价，选股后停牌则顺延到复牌首日。
基准口径：入场日→目标交易日，全市场两日均有收盘价的股票等权平均收益。
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


def _default_trading_dates_loader() -> List[str]:
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    return sorted({str(d)[:10] for d in db["kline"].distinct("date")})


def _default_market_loader(dates: List[str]) -> Dict[str, Dict[str, float]]:
    """按日期批量取全市场收盘价。返回 {date_str: {code: close}}。"""
    from datetime import datetime
    from config.database import DatabaseConfig
    db = DatabaseConfig.get_database()
    dts = []
    for d in dates:
        try:
            dts.append(datetime.fromisoformat(d))
        except ValueError:
            continue
    out: Dict[str, Dict[str, float]] = {}
    if not dts:
        return out
    cursor = db["kline"].find(
        {"date": {"$in": dts}},
        {"_id": 0, "code": 1, "date": 1, "close": 1},
    )
    for r in cursor:
        c = r.get("code")
        cl = r.get("close")
        if c and cl:
            out.setdefault(str(r["date"])[:10], {})[c] = float(cl)
    return out


def _agg(vals: List[float], excesses: List[float],
         baselines: List[float]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": 0, "avg": None, "win_rate": None,
                           "baseline": None, "excess": None, "beat_rate": None}
    if vals:
        out["n"] = len(vals)
        out["avg"] = round(sum(vals) / len(vals), 2)
        out["win_rate"] = round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1)
    if baselines:
        out["baseline"] = round(sum(baselines) / len(baselines), 2)
    if excesses:
        out["excess"] = round(sum(excesses) / len(excesses), 2)
        out["beat_rate"] = round(sum(1 for v in excesses if v > 0) / len(excesses) * 100, 1)
    return out


class PickTracker:
    def __init__(
        self,
        results_loader: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
        kline_loader: Optional[Callable[[str, str, int], List[KlineRow]]] = None,
        trading_dates_loader: Optional[Callable[[], List[str]]] = None,
        market_loader: Optional[Callable[[List[str]], Dict[str, Dict[str, float]]]] = None,
    ):
        self.results_loader = results_loader or _default_results_loader
        self.kline_loader = kline_loader or _default_kline_loader
        self.trading_dates_loader = trading_dates_loader or _default_trading_dates_loader
        self.market_loader = market_loader or _default_market_loader

    def _compute_baselines(
        self, pairs: set,
    ) -> Dict[Tuple[str, int], Optional[float]]:
        """pairs: {(entry_date, horizon)} → {(entry_date, horizon): 等权基准收益% 或 None}"""
        baselines: Dict[Tuple[str, int], Optional[float]] = {}
        if not pairs:
            return baselines
        tdates = self.trading_dates_loader()
        tindex = {d: i for i, d in enumerate(tdates)}

        targets: Dict[Tuple[str, int], str] = {}
        needed_dates: set = set()
        for d, h in pairs:
            i = tindex.get(d)
            if i is not None and i + h < len(tdates):
                targets[(d, h)] = tdates[i + h]
                needed_dates.update((d, tdates[i + h]))
            else:
                baselines[(d, h)] = None

        closes = self.market_loader(sorted(needed_dates)) if needed_dates else {}
        for (d, h), t in targets.items():
            base_map = closes.get(d) or {}
            tgt_map = closes.get(t) or {}
            rets = [
                (tgt_map[c] / base_map[c] - 1) * 100
                for c in base_map
                if c in tgt_map and base_map[c] > 0
            ]
            baselines[(d, h)] = round(sum(rets) / len(rets), 2) if rets else None
        return baselines

    def evaluate(self, horizons: Sequence[int] = (1, 3, 5, 10),
                 limit: int = 20) -> Dict[str, Any]:
        hs = sorted({int(h) for h in horizons if int(h) > 0}) or [1]
        max_h = hs[-1]

        # ── 第一遍：算每只 pick 的收益，收集需要基准的 (入场日, horizon) ──
        runs_raw: List[Dict[str, Any]] = []
        baseline_pairs: set = set()
        for run in self.results_loader(limit):
            pick_date = str(run.get("timestamp", ""))[:10]
            if not pick_date:
                continue
            picks_out: List[Dict[str, Any]] = []
            evaluated = 0
            for p in run.get("picks", []):
                code = p.get("code", "")
                if not code:
                    continue
                klines = self.kline_loader(code, pick_date, max_h + 1)
                entry_close = klines[0][1] if klines else 0.0
                entry_date = klines[0][0] if klines else None
                rets: Dict[str, float] = {}
                if entry_close > 0:
                    evaluated += 1
                    for h in hs:
                        if len(klines) > h:
                            rets[str(h)] = round(
                                (klines[h][1] / entry_close - 1) * 100, 2)
                            baseline_pairs.add((entry_date, h))
                picks_out.append({
                    "code": code,
                    "name": p.get("name", ""),
                    "composite": p.get("composite"),
                    "entry_date": entry_date,
                    "entry_close": entry_close if entry_close > 0 else None,
                    "returns": rets,
                })
            runs_raw.append({
                "timestamp": run.get("timestamp", ""),
                "strategy": run.get("strategy", ""),
                "picks_count": len(run.get("picks", [])),
                "evaluated": evaluated,
                "picks": picks_out,
            })

        # ── 第二遍：批量算等权基准，补每只 pick 的超额收益并聚合 ──
        baselines = self._compute_baselines(baseline_pairs)

        runs_out: List[Dict[str, Any]] = []
        overall: Dict[int, Dict[str, List[float]]] = {
            h: {"rets": [], "exc": [], "base": []} for h in hs}
        for run in runs_raw:
            agg: Dict[int, Dict[str, List[float]]] = {
                h: {"rets": [], "exc": [], "base": []} for h in hs}
            for p in run["picks"]:
                excess: Dict[str, float] = {}
                for h in hs:
                    r = p["returns"].get(str(h))
                    if r is None:
                        continue
                    agg[h]["rets"].append(r)
                    overall[h]["rets"].append(r)
                    b = baselines.get((p["entry_date"], h))
                    if b is not None:
                        excess[str(h)] = round(r - b, 2)
                        for bucket in (agg[h], overall[h]):
                            bucket["exc"].append(r - b)
                            bucket["base"].append(b)
                p["excess"] = excess
            run["returns"] = {
                str(h): _agg(agg[h]["rets"], agg[h]["exc"], agg[h]["base"])
                for h in hs
            }
            runs_out.append(run)

        return {
            "runs_count": len(runs_out),
            "horizons": hs,
            "overall": {
                str(h): _agg(overall[h]["rets"], overall[h]["exc"], overall[h]["base"])
                for h in hs
            },
            "runs": runs_out,
        }
