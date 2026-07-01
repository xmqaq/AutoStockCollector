"""盘前竞价雷达 — 编排器：采集 → 打分 → 诱骗识别 → 联动 → 存储。"""
import time as _time
import threading
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import RadarResult, RadarStock
from .snapshot_collector import collect_auction_data
from .strength_calculator import compute_strength
from .trap_detector import detect_trap
from .radar_utils import (
    batch_get_industries,
    compute_sector_gaps,
    compute_auction_thresholds,
    now_shanghai,
    today_str,
)
from .performance_tracker import record_scan_result
from .intraday_tracker import init_tracking, auto_trade_top_stocks

logger = get_logger(__name__)

_SCAN_LOCK = threading.Lock()
_SCAN_STATUS: Dict[str, Any] = {
    "status": "idle",
    "scan_time": "",
    "date": "",
    "processed": 0,
    "total": 0,
}


def get_status() -> dict:
    return dict(_SCAN_STATUS)


def run_auction_scan(symbols: Optional[List[str]] = None) -> RadarResult:
    """执行盘前竞价全流程（含去重锁）。"""
    if not _SCAN_LOCK.acquire(blocking=False):
        logger.warning("[AuctionRadar] scan already running, skipping")
        return RadarResult(
            date=today_str(),
            status="running",
            summary="扫描正在执行中，请等待",
        )

    _now = now_shanghai()
    # 时间守卫：确保已过 9:30（A 股开盘后才有有效行情数据）
    market_open = _now.replace(hour=9, minute=30, second=0, microsecond=0)
    if _now < market_open:
        wait = (market_open - _now).total_seconds()
        logger.info(f"[AuctionRadar] waiting {wait:.0f}s for market open")
        _time.sleep(wait + 5)  # 多等 5 秒确保数据就绪
        _now = now_shanghai()

    today = _now.strftime("%Y-%m-%d")
    _SCAN_STATUS["status"] = "running"
    _SCAN_STATUS["scan_time"] = _now.isoformat()
    _SCAN_STATUS["date"] = today
    _SCAN_STATUS["processed"] = 0
    _SCAN_STATUS["total"] = 0

    try:
        logger.info(
            f"[AuctionRadar] starting scan for {len(symbols) if symbols else 'all'} stocks"
        )
        snapshots = collect_auction_data(symbols)
        if not snapshots:
            _SCAN_STATUS["status"] = "done"
            return RadarResult(date=today, status="done", total_scanned=0, summary="无数据")

        _SCAN_STATUS["total"] = len(snapshots)

        # 1. 批量查询行业归属（一次 MongoDB $in，消除 N+1）
        codes = [s.get("code", "") for s in snapshots if s.get("code")]
        industry_map = batch_get_industries(codes)

        # 2. 计算板块平均跳空
        sector_gap_map = compute_sector_gaps(snapshots, industry_map)

        # 3. 全市场金额列表（包含零值，保证百分位准确）
        all_amounts = [s.get("amount", 0) for s in snapshots]
        # 预排序 & 预计算阈值（一次 O(N log N)，而非每只股票一次）
        sorted_amounts_desc, neg_sorted_amounts_desc, amount_thresholds = compute_auction_thresholds(all_amounts)

        # 4. 逐只分析
        radar_stocks: List[RadarStock] = []

        for snap in snapshots:
            code = snap.get("code", "")
            strength = compute_strength(snap, sorted_amounts_desc, neg_sorted_amounts_desc, industry_map, sector_gap_map)
            trap = detect_trap(snap, sorted_amounts_desc, amount_thresholds)

            stock = RadarStock(
                symbol=code,
                name=snap.get("name", ""),
                open_price=snap.get("open_price", 0.0),
                gap_pct=snap.get("gap_pct", 0.0),
                auction_amount=snap.get("amount", 0.0),
                strength_score=strength.score,
                strength_detail=strength,
                trap_warning=trap if trap.is_trap else None,
                industry=industry_map.get(code, ""),
            )
            radar_stocks.append(stock)
            _SCAN_STATUS["processed"] += 1

        # 5. 排序 & 截取 TOP N
        radar_stocks.sort(key=lambda s: s.strength_score, reverse=True)
        top_stocks = radar_stocks[:AuctionConfig.TOP_N]

        # 6. 板块龙头 (仅基于 top_stocks)
        sector_leaders = _compute_sector_leaders(top_stocks)

        # 7. 联动: 研报标记
        highlight_codes = _get_research_highlights(today)
        trap_stocks = []

        for s in top_stocks:
            if s.symbol in highlight_codes and s.strength_score >= 70:
                s.highlight = True
                s.highlight_reason = "研报看好 + 竞价强势"
            if s.trap_warning:
                trap_stocks.append({
                    "symbol": s.symbol,
                    "name": s.name,
                    "trap_type": s.trap_warning.trap_type,
                    "reason": s.trap_warning.reason,
                    "strength_score": s.strength_score,
                })

        # 8. 整体情绪摘要
        summary = _generate_summary(top_stocks, trap_stocks, sector_leaders)

        _now = now_shanghai()
        result = RadarResult(
            date=today,
            scan_time=_now.strftime("%H:%M:%S"),
            status="done",
            total_scanned=len(snapshots),
            top_stocks=top_stocks,
            sector_leaders=sector_leaders,
            trap_warnings=trap_stocks,
            summary=summary,
            created_at=_now.isoformat(),
        )

        # 9. 保存结果到 MongoDB
        _save_result(result)

        # 10. 记录性能追踪
        record_scan_result(result)

        # 11. 初始化盘中追踪
        init_tracking(result)

        # 12. 自动创建模拟交易
        auto_trade_top_stocks(result)

        _SCAN_STATUS["status"] = "done"
        _SCAN_STATUS["date"] = today

        logger.info(
            f"[AuctionRadar] scan done: {len(snapshots)} stocks, {len(top_stocks)} top"
        )
        return result

    except Exception as e:
        logger.error(f"[AuctionRadar] scan failed: {e}")
        _SCAN_STATUS["status"] = "failed"
        return RadarResult(date=today, status="failed", summary=str(e))

    finally:
        _SCAN_LOCK.release()


def _compute_sector_leaders(stocks: List[RadarStock]) -> List[Dict[str, str]]:
    sectors: Dict[str, RadarStock] = {}
    for s in stocks:
        ind = s.industry or "其他"
        if ind not in sectors or s.strength_score > sectors[ind].strength_score:
            sectors[ind] = s
    return [
        {"sector": ind, "leader": s.symbol, "name": s.name, "score": str(s.strength_score)}
        for ind, s in sorted(sectors.items(), key=lambda x: x[1].strength_score, reverse=True)
    ]


def _get_research_highlights(today: str) -> set:
    """查询当日研报分析中标记为看好的股票。使用 datetime 对象比较。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        from datetime import time, timedelta, datetime as dt
        today_dt = dt.strptime(today, "%Y-%m-%d").replace(tzinfo=now_shanghai().tzinfo)
        today_start = today_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        docs = list(
            db["research_analysis_results"].find(
                {"created_at": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()}},
                {"candidates": 1},
            )
        )
        if not docs:
            return set()
        codes = set()
        for doc in docs:
            for c in doc.get("candidates") or []:
                code = c.get("code", "")
                if code:
                    codes.add(code)
        return codes
    except Exception as e:
        logger.warning(f"[AuctionRadar] research highlights error: {e}")
        return set()


def _generate_summary(
    top_stocks: List[RadarStock],
    trap_stocks: List[Dict],
    sector_leaders: List[Dict[str, str]],
) -> str:
    high_count = sum(1 for s in top_stocks if s.strength_score >= 80)
    med_count = sum(1 for s in top_stocks if 60 <= s.strength_score < 80)
    trap_count = len(trap_stocks)
    top_sectors = [sl["sector"] for sl in sector_leaders[:3]]

    mood = "偏暖" if high_count > len(top_stocks) * 0.3 else "中性"
    if high_count < len(top_stocks) * 0.1:
        mood = "偏冷"

    parts = [f"今日竞价情绪{mood}，强势股{high_count}只，中等{med_count}只"]
    if top_sectors:
        parts.append(f"活跃板块：{'、'.join(top_sectors)}")
    if trap_count > 0:
        parts.append(f"检测到{trap_count}只诱多/诱空信号")
    return "。".join(parts)


def _save_result(result: RadarResult):
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        db[AuctionConfig.RESULT_COLLECTION].update_one(
            {"date": result.date},
            {"$set": result.model_dump()},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[AuctionRadar] save result error: {e}")
