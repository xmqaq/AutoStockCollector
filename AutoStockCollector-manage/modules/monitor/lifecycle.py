"""监控生命周期管理：维护 monitor_signals 中每只股票的 sources 来源
（position / watchlist / fusion_pick）与 AI 智选连续入选追踪。

职责单一：只负责"谁该被监控、来源怎么变"，不做深度分析（那是 MonitorEngine）。
"""
from datetime import datetime, timedelta
from typing import Any, Dict

from config.database import DatabaseConfig
from core.storage.mongo_storage import WatchlistStorage
from utils.helpers import beijing_now, get_trading_days
from utils.logger import get_logger

from .storage import MonitorStorage

logger = get_logger(__name__)

FUSION_RESULTS_COL = "fusion_pick_results"
SIGNALS_COL = MonitorStorage.SIGNALS_COL


class MonitorLifecycle:
    def __init__(self):
        self.storage = MonitorStorage()
        self.watchlist = WatchlistStorage()
        self.db = DatabaseConfig.get_database()

    # ── 内部工具 ──

    @staticmethod
    def _now_iso() -> str:
        return beijing_now().isoformat()

    def _ensure_source(self, code: str, source: str, name: str = "") -> None:
        """给某股票的 monitor_signals 文档追加来源；文档不存在则建占位记录
        （不含分析数据，等下次 refresh_all 统一补全）。"""
        self.db[SIGNALS_COL].update_one(
            {"code": code},
            {"$addToSet": {"sources": source},
             "$setOnInsert": {"code": code, "name": name, "consecutive_days": 0,
                              "placeholder": True, "created_at": self._now_iso()}},
            upsert=True,
        )

    def _latest_fusion_runs(self, n: int = 2):
        # run_id 必须投影出来——sync 用它做幂等去重；漏投会让 cur_run_id 恒为 None、幂等失效。
        return list(self.db[FUSION_RESULTS_COL]
                    .find({}, {"picks": 1, "created_at": 1, "run_id": 1})
                    .sort("created_at", -1).limit(n))

    @staticmethod
    def _pick_codes(run: Dict[str, Any]) -> set:
        return {p.get("code") for p in (run.get("picks") or []) if p.get("code")}

    def _trading_days_since(self, last_iso) -> int:
        """last_selected_at 距今的交易日数（不含当日基准、含今日）。无值视为很久。"""
        if not last_iso:
            return 999
        try:
            last_dt = datetime.fromisoformat(str(last_iso)).replace(tzinfo=None)
        except (ValueError, TypeError):
            return 0
        today = beijing_now().replace(tzinfo=None)
        if last_dt.date() >= today.date():
            return 0
        start = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        return len(get_trading_days(start, end))

    def _current_position_codes(self, user_id: str) -> Dict[str, str]:
        """当前持仓 {code: name}：模拟盘 TradeEngine + 兼容实盘 positions 集合。"""
        out: Dict[str, str] = {}
        try:
            from modules.paper_trading.trade_engine import TradeEngine
            positions, _ = TradeEngine().get_positions(user_id)
            for p in positions:
                if p.get("code") and (p.get("shares", 0) or 0) > 0:
                    out[p["code"]] = p.get("name", "")
        except Exception as e:
            logger.error(f"[lifecycle] get paper positions failed: {e}")
        try:
            for p in self.db["positions"].find(
                {"$or": [{"user_id": user_id}, {"user_id": "default"},
                         {"user_id": {"$exists": False}}]}
            ):
                if p.get("code") and (p.get("shares", 0) or 0) > 0:
                    out.setdefault(p["code"], p.get("name", ""))
        except Exception as e:
            logger.error(f"[lifecycle] get legacy positions failed: {e}")
        return out

    # ── 智选追踪 ──

    def sync_fusion_pick_tracking(self, user_id: str = "default") -> Dict[str, Any]:
        """每轮智选完成后调用，更新 fusion_pick 来源股票的双时间戳 + 连续入选计数。

        幂等关键：用 fusion run 的 run_id 去重。consecutive_days 只在"遇到一个新
        run_id"时 +1，同一轮被重复调用（多用户级联 / 手动刷新 / 数据修复）一律跳过，
        否则会按调用次数累加（曾导致刚上线就显示"连8天"）。
        """
        runs = self._latest_fusion_runs(2)
        if not runs:
            return {"updated": 0, "new": 0, "no_fusion_data": True}
        current, prev = runs[0], (runs[1] if len(runs) > 1 else {})
        cur_run_id = current.get("run_id")
        cur_codes = self._pick_codes(current)
        prev_codes = self._pick_codes(prev)
        name_map = {p.get("code"): p.get("name", "")
                    for p in (current.get("picks") or [])}
        now = self._now_iso()
        new_cnt = upd_cnt = skipped = 0
        for code in cur_codes:
            doc = self.db[SIGNALS_COL].find_one(
                {"code": code},
                {"sources": 1, "consecutive_days": 1, "first_selected_at": 1,
                 "last_fusion_run_id": 1})
            # 本轮已计过这只 → 幂等跳过（防按调用次数累加）
            if doc and cur_run_id is not None and doc.get("last_fusion_run_id") == cur_run_id:
                skipped += 1
                continue
            if not doc:
                self.db[SIGNALS_COL].update_one(
                    {"code": code},
                    {"$set": {"first_selected_at": now, "last_selected_at": now,
                              "consecutive_days": 1, "name": name_map.get(code, ""),
                              "last_fusion_run_id": cur_run_id},
                     "$addToSet": {"sources": "fusion_pick"},
                     "$setOnInsert": {"code": code, "placeholder": True,
                                      "created_at": now}},
                    upsert=True)
                new_cnt += 1
            else:
                consec = ((doc.get("consecutive_days") or 0) + 1
                          if code in prev_codes else 1)
                set_fields = {"last_selected_at": now, "consecutive_days": consec,
                              "last_fusion_run_id": cur_run_id}
                if not doc.get("first_selected_at"):
                    set_fields["first_selected_at"] = now
                self.db[SIGNALS_COL].update_one(
                    {"code": code},
                    {"$set": set_fields, "$addToSet": {"sources": "fusion_pick"}})
                upd_cnt += 1
        return {"updated": upd_cnt, "new": new_cnt, "skipped_same_run": skipped,
                "current_picks": len(cur_codes), "run_id": cur_run_id}

    def cleanup_expired_fusion_picks(self) -> Dict[str, Any]:
        """清理超过 3 个交易日未再入选的纯 fusion_pick 来源股票。"""
        removed = 0
        for d in self.storage.get_signals_by_source("fusion_pick"):
            srcs = set(d.get("sources") or [])
            if srcs - {"fusion_pick"}:        # 同时是持仓/自选 → 保留
                continue
            if self._trading_days_since(d.get("last_selected_at")) > 3:
                self.storage.remove_source(d["code"], "fusion_pick")
                removed += 1
        return {"expired_removed": removed}

    # ── 自选股增删联动 ──

    def on_watchlist_removed(self, user_id: str, code: str) -> Dict[str, Any]:
        res = self.storage.remove_source(code, "watchlist")
        return {"removed_from_monitor": res["removed_doc"],
                "still_monitored_as": res["remaining_sources"]}

    def on_watchlist_added(self, user_id: str, code: str, name: str = "") -> Dict[str, Any]:
        self._ensure_source(code, "watchlist", name)
        doc = self.db[SIGNALS_COL].find_one({"code": code}, {"sources": 1})
        return {"code": code, "sources": (doc or {}).get("sources", [])}

    # ── 持仓强制监控同步 ──

    def sync_positions(self, user_id: str = "default") -> Dict[str, Any]:
        held = self._current_position_codes(user_id)
        added, removed = [], []
        for code, name in held.items():
            doc = self.db[SIGNALS_COL].find_one({"code": code}, {"sources": 1})
            if not doc or "position" not in (doc.get("sources") or []):
                self._ensure_source(code, "position", name)
                added.append(code)
        for d in self.storage.get_signals_by_source("position"):
            if d["code"] not in held:
                self.storage.remove_source(d["code"], "position")
                removed.append(d["code"])
        return {"added": added, "removed": removed}


if __name__ == "__main__":
    # 交易日跨度自检（不连库）：last_selected_at 距今 >3 个交易日才算过期
    lc = MonitorLifecycle.__new__(MonitorLifecycle)
    assert lc._trading_days_since(None) == 999
    assert lc._trading_days_since(beijing_now().isoformat()) == 0
    print("MonitorLifecycle self-check passed")
