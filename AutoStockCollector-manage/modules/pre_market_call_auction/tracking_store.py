"""TrackingStore — 盘中追踪 + 绩效统计的统一写入点（状态机唯一入口）。

修复：
- bug 7：原 14:50 平仓只更新 auction_performance，intraday_track 的 status 不标 closed，
  长期累积 active/traded。现 close_record 同步更新两集合。
- bug 12：原 record_scan_result 与 init_tracking 重复写每只 top_stock。现 init_tracking
  一次遍历同时写两集合（intraday_track=active + auction_performance=pending）。

状态机：
  auction_intraday_track: active → traded → closed
  auction_performance:    pending → win/loss（由 close_record 同步）
"""
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne

from utils.logger import get_logger
from .config import AuctionConfig
from .radar_utils import now_shanghai
from .schemas import RadarResult

logger = get_logger(__name__)

INTRADAY_COLLECTION = "auction_intraday_track"
PERF_COLLECTION = "auction_performance"


class TrackingStore:
    """盘中追踪 + 绩效统计的统一写入与查询。"""

    def _db(self):
        from config.database import DatabaseConfig
        return DatabaseConfig.get_database()

    # ── 初始化（合并原 init_tracking + record_scan_result，bug12）─────────
    def init_tracking(self, result: RadarResult) -> int:
        """扫描后初始化：一次遍历同时写 intraday_track(active) + auction_performance(pending)。"""
        if not result or not result.top_stocks:
            return 0
        try:
            db = self._db()
            now_iso = now_shanghai().isoformat()
            track_ops = []
            perf_ops = []
            for s in result.top_stocks:
                is_trap = s.trap_warning is not None
                trap_type = s.trap_warning.trap_type if s.trap_warning else ""
                # intraday_track：active
                track_ops.append(UpdateOne(
                    {"code": s.symbol, "date": result.date},
                    {"$set": {
                        "code": s.symbol, "name": s.name, "date": result.date,
                        "open_price": s.open_price, "gap_pct": s.gap_pct,
                        "strength_score": s.strength_score, "industry": s.industry,
                        "is_trap": is_trap, "trap_type": trap_type,
                        "status": "active", "auto_trade_id": "",
                        "current_price": 0.0, "current_pnl_pct": 0.0,
                        "highest_pnl_pct": 0.0, "lowest_pnl_pct": 0.0,
                        "exit_price": None, "return_pct": None, "exit_time": None,
                        "updated_at": now_iso,
                    }},
                    upsert=True,
                ))
                # auction_performance：pending
                perf_ops.append(UpdateOne(
                    {"code": s.symbol, "date": result.date},
                    {"$set": {
                        "code": s.symbol, "name": s.name, "date": result.date,
                        "scan_time": result.scan_time, "strategy": "auction_radar",
                        "strength_score": s.strength_score, "gap_pct": s.gap_pct,
                        "auction_amount": s.auction_amount, "industry": s.industry,
                        "is_trap": is_trap, "trap_type": trap_type,
                        "result": "pending", "return_pct": None, "exit_reason": "",
                        "updated_at": now_iso, "created_at": now_iso,
                    }},
                    upsert=True,
                ))
            if track_ops:
                db[INTRADAY_COLLECTION].bulk_write(track_ops, ordered=False)
            if perf_ops:
                db[PERF_COLLECTION].bulk_write(perf_ops, ordered=False)
            logger.info(f"[TrackingStore] initialized {len(track_ops)} tracking + perf records")
            return len(track_ops)
        except Exception as e:
            logger.warning(f"[TrackingStore] init error: {e}")
            return 0

    # ── 状态流转 ──────────────────────────────────────────────────
    def mark_traded(self, code: str, date: str, trade_id: str) -> None:
        """auto_trading 建仓后回填 trade_id，状态 active→traded。"""
        try:
            self._db()[INTRADAY_COLLECTION].update_one(
                {"code": code, "date": date},
                {"$set": {"auto_trade_id": trade_id, "status": "traded",
                          "updated_at": now_shanghai().isoformat()}},
            )
        except Exception as e:
            logger.warning(f"[TrackingStore] mark_traded error: {e}")

    def update_realtime(self, code: str, date: str, current_price: float, pnl_pct: float) -> None:
        """更新实时价 + 盈亏，$max/$min 累计峰值。"""
        try:
            self._db()[INTRADAY_COLLECTION].update_one(
                {"code": code, "date": date},
                {"$set": {"current_price": round(current_price, 2),
                          "current_pnl_pct": pnl_pct,
                          "updated_at": now_shanghai().isoformat()},
                 "$max": {"highest_pnl_pct": pnl_pct},
                 "$min": {"lowest_pnl_pct": pnl_pct}},
            )
        except Exception as e:
            logger.debug(f"[TrackingStore] update_realtime error: {e}")

    def close_record(self, code: str, date: str, exit_price: float,
                     return_pct: float, exit_reason: str = "尾盘平仓") -> None:
        """平仓：同步更新两集合（bug7 修复）。
        intraday_track → closed（exit_price/return_pct/exit_time）
        auction_performance → win/loss（return_pct/exit_reason）"""
        now_iso = now_shanghai().isoformat()
        try:
            self._db()[INTRADAY_COLLECTION].update_one(
                {"code": code, "date": date},
                {"$set": {"status": "closed", "exit_price": round(exit_price, 2),
                          "return_pct": round(return_pct, 4), "exit_reason": exit_reason,
                          "exit_time": now_iso, "updated_at": now_iso}},
            )
        except Exception as e:
            logger.warning(f"[TrackingStore] close intraday error: {e}")
        try:
            self._db()[PERF_COLLECTION].update_one(
                {"code": code, "date": date},
                {"$set": {"result": "win" if return_pct > 0 else "loss",
                          "return_pct": round(return_pct, 4), "exit_reason": exit_reason,
                          "updated_at": now_iso}},
            )
        except Exception as e:
            logger.warning(f"[TrackingStore] close perf error: {e}")

    # ── 查询 ──────────────────────────────────────────────────────
    def get_traded_records(self, date: str) -> List[Dict]:
        """获取当日已建仓（status=traded，auto_trade_id 非空）的追踪记录，供 14:50 平仓。"""
        try:
            return list(self._db()[INTRADAY_COLLECTION].find(
                {"date": date, "auto_trade_id": {"$ne": ""}},
                {"_id": 0},
            ))
        except Exception:
            return []

    def get_active_or_traded(self, date: str) -> List[Dict]:
        """获取当日未平仓（active 或 traded）的记录，供盘中刷新。"""
        try:
            return list(self._db()[INTRADAY_COLLECTION].find(
                {"date": date, "status": {"$in": ["active", "traded"]}},
                {"code": 1, "open_price": 1, "_id": 0},
            ))
        except Exception:
            return []

    def get_intraday_data(self, date: str) -> List[Dict]:
        """获取当日全部追踪记录（含已平仓），按强度降序。"""
        try:
            return list(self._db()[INTRADAY_COLLECTION]
                        .find({"date": date}, {"_id": 0})
                        .sort("strength_score", -1))
        except Exception as e:
            logger.warning(f"[TrackingStore] get_intraday_data error: {e}")
            return []

    def cleanup_stale(self, date: str) -> int:
        """将历史遗留的 active/traded 记录标记为 closed（status=closed, exit_reason=异常未平）。
        用于修复 bug7 之前累积的脏数据。"""
        try:
            r = self._db()[INTRADAY_COLLECTION].update_many(
                {"date": {"$lt": date}, "status": {"$in": ["active", "traded"]}},
                {"$set": {"status": "closed", "exit_reason": "历史遗留清理",
                          "exit_time": now_shanghai().isoformat()}},
            )
            return r.modified_count
        except Exception as e:
            logger.warning(f"[TrackingStore] cleanup error: {e}")
            return 0
