"""回测回放器 — 回放历史 auction_snapshots，用 8 维因子重新打分，模拟建仓/平仓。"""
from typing import Any, Dict, Iterator, List, Optional

from config.database import DatabaseConfig
from utils.logger import get_logger

from ..config import AuctionConfig
from ..radar_utils import (
    batch_get_industries, compute_sector_gaps, compute_auction_thresholds,
    strip_prefix_from_code,
)
from ..strength_calculator import compute_strength
from ..trap_detector import detect_trap, compute_sector_trap_rate
from .metrics import compute_metrics
from .schemas import BacktestConfig, BacktestResult

logger = get_logger(__name__)


class AuctionBacktestReplayer:
    """回放历史竞价快照，用当前因子体系重新打分，模拟建仓/平仓。"""

    def run(self, config: BacktestConfig) -> BacktestResult:
        """主回放循环：按日期遍历历史快照 → 打分 → TOP N → 模拟建仓 → 取 exit_price → 落 trades。"""
        trades: List[Dict[str, Any]] = []
        days_scanned = 0
        # 可选权重覆盖（回测时临时覆盖 AuctionConfig 类属性）
        if config.weight_overrides:
            self._apply_weight_overrides(config.weight_overrides)
        try:
            for date, day_snapshots in self._iter_snapshots_by_date(config.start_date, config.end_date):
                days_scanned += 1
                day_trades = self._process_day(date, day_snapshots, config)
                trades.extend(day_trades)
        finally:
            if config.weight_overrides:
                self._restore_weights()

        metrics = compute_metrics(trades)
        return BacktestResult(
            trades=trades, config=config.model_dump(),
            metrics=metrics, days_scanned=days_scanned,
        )

    def _iter_snapshots_by_date(self, start: str, end: str) -> Iterator:
        """流式按日期分组加载历史快照。"""
        db = DatabaseConfig.get_database()
        cursor = db[AuctionConfig.COLLECTION].find(
            {"date": {"$gte": start, "$lte": end}},
            {"_id": 0, "_key": 0},
        ).sort("date", 1)
        current_date = None
        bucket: List[Dict] = []
        for snap in cursor:
            d = snap.get("date", "")
            if d != current_date:
                if bucket and current_date:
                    yield current_date, bucket
                current_date = d
                bucket = []
            bucket.append(snap)
        if bucket and current_date:
            yield current_date, bucket

    def _process_day(self, date: str, snapshots: List[Dict], config: BacktestConfig) -> List[Dict]:
        """处理单日：打分 → TOP N → 模拟建仓 → 取 exit_price。"""
        if not snapshots:
            return []
        codes = [s.get("code", "") for s in snapshots if s.get("code")]
        industry_map = batch_get_industries(codes)
        sector_gap_map = compute_sector_gaps(snapshots, industry_map)
        all_amounts = [s.get("amount", 0) for s in snapshots]
        all_turnovers = [s.get("turnover", 0) for s in snapshots]
        sorted_desc, neg_sorted, amount_thresholds = compute_auction_thresholds(all_amounts)
        sorted_turnover_desc = sorted(all_turnovers, reverse=True)
        sector_trap_rate = compute_sector_trap_rate(snapshots, industry_map, amount_thresholds)

        scored: List[Dict[str, Any]] = []
        for snap in snapshots:
            strength = compute_strength(snap, sorted_desc, neg_sorted, industry_map,
                                        sector_gap_map, sorted_turnover_desc)
            if strength.score < config.min_score:
                continue
            trap = detect_trap(snap, sorted_desc, amount_thresholds, sector_trap_rate=sector_trap_rate)
            scored.append({"snap": snap, "strength": strength, "trap": trap})
        scored.sort(key=lambda x: x["strength"].score, reverse=True)
        top = scored[:config.top_n]

        trades: List[Dict] = []
        for item in top:
            snap = item["snap"]
            strength = item["strength"]
            trap = item["trap"]
            if trap.is_trap:
                continue  # 诱骗股跳过
            open_price = snap.get("open_price", 0)
            if open_price <= 0:
                continue
            exit_price = self._get_exit_price(snap.get("code", ""), date, config.exit_strategy)
            if not exit_price or exit_price <= 0:
                continue
            return_pct = round((exit_price - open_price) / open_price, 4)
            trades.append({
                "date": date, "code": snap.get("code", ""), "name": snap.get("name", ""),
                "strength_score": strength.score, "gap_pct": snap.get("gap_pct", 0),
                "open_price": open_price, "exit_price": exit_price, "return_pct": return_pct,
                "strength_detail": strength.model_dump(),
                "trap_warning": trap.model_dump() if trap.is_trap else None,
            })
        return trades

    def _get_exit_price(self, code: str, date: str, strategy: str) -> Optional[float]:
        """从 kline 取退出价：close(当日收盘) | next_open(次日开盘) | eod_1450(近似当日14:50)。
        kline 的 code 可能是带前缀(SZ000042)或裸代码，date 可能是字符串或 datetime，都兼容。"""
        try:
            db = DatabaseConfig.get_database()
            bare = strip_prefix_from_code(code).upper()
            from ..radar_utils import to_tencent_code
            tencent = to_tencent_code(code).upper()  # SH600000
            codes = [tencent, bare]
            # kline.date 可能是 datetime 或字符串，构造两种 query
            from datetime import datetime as _dt
            dt = None
            try:
                dt = _dt.strptime(date, "%Y-%m-%d")
            except Exception:
                pass
            date_queries = [{"$gt": date}, {"$gt": dt}] if dt else [{"$gt": date}]
            if strategy == "next_open":
                for c in codes:
                    for dq in date_queries:
                        doc = db["kline"].find_one(
                            {"code": c, "date": dq},
                            {"open": 1, "_id": 0}, sort=[("date", 1)],
                        )
                        if doc and doc.get("open"):
                            return float(doc["open"])
                return None
            # close / eod_1450 用当日收盘
            eq_queries = [date, dt] if dt else [date]
            for c in codes:
                for dq in eq_queries:
                    doc = db["kline"].find_one({"code": c, "date": dq}, {"close": 1, "_id": 0})
                    if doc and doc.get("close"):
                        return float(doc["close"])
            return None
        except Exception as e:
            logger.debug(f"[Backtest] exit price {code} {date}: {e}")
            return None

    _saved_weights: Dict[str, float] = {}

    def _apply_weight_overrides(self, overrides: Dict[str, float]):
        """临时覆盖 AuctionConfig 的权重字段（用于参数寻优）。"""
        attr_map = {
            "gap": "STRENGTH_WEIGHT_GAP", "volume": "STRENGTH_WEIGHT_VOLUME",
            "sector": "STRENGTH_WEIGHT_SECTOR", "deviation": "STRENGTH_WEIGHT_DEVIATION",
            "vol_ratio": "STRENGTH_WEIGHT_VOL_RATIO", "order_imbalance": "STRENGTH_WEIGHT_ORDER_IMBALANCE",
            "auction_turnover": "STRENGTH_WEIGHT_AUCTION_TURNOVER",
            "amount_percentile": "STRENGTH_WEIGHT_AMOUNT_PCTILE",
        }
        for k, v in overrides.items():
            attr = attr_map.get(k)
            if attr and hasattr(AuctionConfig, attr):
                self._saved_weights[attr] = getattr(AuctionConfig, attr)
                setattr(AuctionConfig, attr, float(v))

    def _restore_weights(self):
        for attr, v in self._saved_weights.items():
            setattr(AuctionConfig, attr, v)
        self._saved_weights.clear()
