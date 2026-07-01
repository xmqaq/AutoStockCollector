"""实时数据刷新 — 盘中定时拉取池中股票的实时行情 + 即时资金流，写入 monitor_realtime。

复用 price_action_advisor/fetcher.get_spot（东财全市场快照，60s 双层缓存）取现价/
涨跌/量比/换手；复用 fund_flow_collector.collect_individual_snapshot 取即时主力
资金流。关键约束：实时数据只写 monitor_realtime 独立集合，绝不写 fund_flow
（fund_flow 存日级数据，collect_individual_snapshot 的 upsert key 是 [code,date]，
会覆盖今日日级文档，破坏 fund_flow 分析器）。
"""
from datetime import datetime
from typing import Any, Dict, List

from config.database import DatabaseConfig
from utils.logger import get_logger

from .storage import MonitorStorage

logger = get_logger(__name__)


class RealtimeRefresher:
    """盘中实时数据刷新器。"""

    def __init__(self):
        self._storage = MonitorStorage()
        self._db = DatabaseConfig.get_database()

    def refresh(self, user_id: str = "default") -> Dict[str, Any]:
        """刷新池中股票的实时行情 + 资金流，写 monitor_realtime + patch monitor_signals 价格指针。"""
        from modules.monitor.engine import MonitorEngine

        stocks = MonitorEngine()._collect_stocks(user_id)
        if not stocks:
            return {"refreshed": 0, "reason": "empty_pool"}
        codes = [s["code"] for s in stocks if s.get("code")]
        codes_set = set(codes)

        spot_map = self._fetch_spot(codes)
        flow_map = self._fetch_realtime_flow(codes_set)

        refreshed = 0
        for code in codes:
            spot = spot_map.get(code) or {}
            flow = flow_map.get(code) or {}
            if not spot and not flow:
                continue
            doc = {
                "price": float(spot.get("price") or 0),
                "change_rate": float(spot.get("change_pct") or 0),
                "volume_ratio": float(spot.get("volume_ratio") or 0),
                "turnover": float(spot.get("turnover") or 0),
                "main_net_inflow": float(flow.get("main_net_inflow") or 0),
                "main_inflow": float(flow.get("main_inflow") or 0),
                "main_outflow": float(flow.get("main_outflow") or 0),
                "total_amount": float(flow.get("total_amount") or 0),
            }
            self._storage.upsert_realtime(code, doc)
            # 同时 patch monitor_signals 的价格指针字段（不碰 analysis 结构）
            patch = {k: v for k, v in doc.items() if k in ("price", "change_rate")}
            if patch:
                self._db[MonitorStorage.SIGNALS_COL].update_one(
                    {"code": code}, {"$set": patch},
                )
            refreshed += 1

        logger.info(f"[Realtime] refreshed {refreshed}/{len(codes)} stocks (user={user_id})")
        return {"refreshed": refreshed, "total": len(codes)}

    def get_realtime_map(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """供 API/前端取池中股票实时快照。"""
        return self._storage.get_realtime_many(codes)

    def _fetch_spot(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """东财全市场快照（60s 缓存），过滤池中 codes。"""
        try:
            from modules.price_action_advisor.fetcher import get_spot
            # 传 symbols 让 get_spot 只解析池中股票（命中缓存更快）
            spot = get_spot(codes)
            if spot:
                return spot
            # 传 symbols 未命中则全量拉一次再过滤
            all_spot = get_spot()
            return {c: all_spot[c] for c in codes if c in all_spot}
        except Exception as e:
            logger.warning(f"[Realtime] get_spot failed: {e}")
            return {}

    def _fetch_realtime_flow(self, codes_set: set) -> Dict[str, Dict[str, Any]]:
        """即时资金流快照（全市场），过滤池中 codes。"""
        try:
            from core.collector.fund_flow_collector import FundFlowCollector
            rows = FundFlowCollector().collect_individual_snapshot()
            out: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                code = r.get("code")
                if code in codes_set:
                    out[code] = r
            return out
        except Exception as e:
            logger.warning(f"[Realtime] collect_individual_snapshot failed: {e}")
            return {}
