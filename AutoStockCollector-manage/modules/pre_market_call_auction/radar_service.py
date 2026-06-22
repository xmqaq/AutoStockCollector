"""盘前竞价雷达 — 编排器：采集 → 打分 → 诱骗识别 → 联动 → 存储。"""
from datetime import datetime, time as dttime
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .schemas import RadarResult, RadarStock, TrapWarning
from .snapshot_collector import collect_auction_data, get_snapshots_from_db
from .strength_calculator import compute_strength, compute_sector_gaps
from .trap_detector import detect_trap

logger = get_logger(__name__)

_W = AuctionConfig

_SCAN_STATUS: Dict[str, Any] = {
    "status": "idle",
    "scan_time": "",
    "date": "",
}


def get_status() -> dict:
    return dict(_SCAN_STATUS)


def run_auction_scan(symbols: Optional[List[str]] = None) -> RadarResult:
    """执行盘前竞价全流程。"""
    _SCAN_STATUS["status"] = "running"
    _SCAN_STATUS["scan_time"] = datetime.now().isoformat()

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # 1. 采集竞价快照
        logger.info(f"[AuctionRadar] starting scan for {len(symbols) if symbols else 'all'} stocks")
        snapshots = collect_auction_data(symbols)
        if not snapshots:
            _SCAN_STATUS["status"] = "done"
            return RadarResult(date=today, status="done", total_scanned=0, summary="无数据")

        # 2. 计算板块平均跳空
        sector_gaps = compute_sector_gaps(snapshots)

        # 3. 全市场金额列表（排名用）
        all_amounts = [s.get("amount", 0) for s in snapshots if s.get("amount", 0) > 0]

        # 4. 逐只分析
        radar_stocks: List[RadarStock] = []
        sector_amounts: Dict[str, float] = {}

        for snap in snapshots:
            strength = compute_strength(snap, all_amounts, sector_gaps)
            trap = detect_trap(snap)

            code = snap.get("code", "")
            industry = _get_industry(code)

            stock = RadarStock(
                symbol=code,
                name=snap.get("name", ""),
                open_price=snap.get("open_price", 0.0),
                gap_pct=snap.get("gap_pct", 0.0),
                auction_amount=snap.get("amount", 0.0),
                strength_score=strength.score,
                strength_detail=strength,
                trap_warning=trap if trap.is_trap else None,
                sector_rank=0,
                industry=industry,
            )
            radar_stocks.append(stock)

            if industry:
                sector_amounts[industry] = sector_amounts.get(industry, 0) + snap.get("amount", 0)

        # 5. 排序 & 截取 TOP N
        radar_stocks.sort(key=lambda s: s.strength_score, reverse=True)
        top_stocks = radar_stocks[:_W.TOP_N]

        # 6. 板块龙头: 每个板块内 strength_score 最高的股票
        sector_leaders = _compute_sector_leaders(radar_stocks)

        # 7. 联动: 研报标记 + PA 推送
        highlight_codes = _get_research_highlights()
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
            # 推送到 PA 监控池
            if s.strength_score >= _W.STRENGTH_SCORE_HIGH and not s.trap_warning:
                _push_to_pa_watchlist(s.symbol, s.name, s.strength_score)

        # 8. 整体情绪摘要
        summary = _generate_summary(top_stocks, trap_stocks, sector_leaders)

        result = RadarResult(
            date=today,
            scan_time=datetime.now().strftime("%H:%M:%S"),
            status="done",
            total_scanned=len(snapshots),
            top_stocks=top_stocks,
            sector_leaders=sector_leaders,
            trap_warnings=trap_stocks,
            summary=summary,
            created_at=datetime.now().isoformat(),
        )

        # 9. 保存结果到 MongoDB
        _save_result(result)

        _SCAN_STATUS["status"] = "done"
        _SCAN_STATUS["date"] = today

        logger.info(f"[AuctionRadar] scan done: {len(snapshots)} stocks, {len(top_stocks)} top")
        return result

    except Exception as e:
        logger.error(f"[AuctionRadar] scan failed: {e}")
        _SCAN_STATUS["status"] = "failed"
        return RadarResult(date=today, status="failed", summary=str(e))


def _get_industry(code: str) -> str:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        doc = db["stock_info"].find_one({"code": code}, {"所属行业": 1})
        if doc:
            return doc.get("所属行业", "")
    except Exception:
        pass
    return ""


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


def _get_research_highlights() -> set:
    """查询当日研报分析中标记为看好的股票。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        today = datetime.now().strftime("%Y-%m-%d")
        docs = list(db["research_analysis_results"].find(
            {"created_at": {"$regex": f"^{today}"}},
            {"candidates": 1},
        ).limit(1))
        if not docs:
            return set()
        codes = set()
        for doc in docs:
            for c in (doc.get("candidates") or []):
                code = c.get("code", "")
                if code:
                    codes.add(code)
        return codes
    except Exception as e:
        logger.debug(f"[AuctionRadar] research highlights error: {e}")
        return set()


def _push_to_pa_watchlist(symbol: str, name: str, score: int):
    """将强势股推送到 PA 盘中监控池。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        today = datetime.now().strftime("%Y-%m-%d")
        db["pa_watchlist"].update_one(
            {"symbol": symbol, "date": today},
            {"$set": {
                "symbol": symbol,
                "name": name,
                "strength_score": score,
                "source": "auction_radar",
                "date": today,
                "updated_at": datetime.now(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[AuctionRadar] PA push error: {e}")


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
        parts.append(f"⚠ 检测到{trap_count}只诱多/诱空信号")
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
