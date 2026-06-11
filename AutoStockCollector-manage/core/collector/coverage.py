"""数据完整性体检：各数据源对全市场的覆盖率。

以 fund_flow（单次批量接口，最稳）当日记录为"在交易股票"基准，
交叉检查逐只采集的源（kline 等）是否有缺口。
2026-06-10/11 K线采集中途被部署重启打断导致缺口 2000+ 只，
此模块让缺口在前端可见，配合 17:30/21:45 缺口回补定时任务自愈。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.helpers import beijing_now
from utils.logger import get_logger

logger = get_logger(__name__)

# 覆盖率状态阈值
_OK_RATIO = 0.98
_WARN_RATIO = 0.80


def _status(covered: int, expected: int) -> str:
    if expected <= 0:
        return "unknown"
    ratio = covered / expected
    if ratio >= _OK_RATIO:
        return "ok"
    if ratio >= _WARN_RATIO:
        return "warn"
    return "bad"


def compute_data_coverage(db=None) -> Dict[str, Any]:
    """计算各数据源最近交易日的覆盖率。返回前端可直接渲染的结构。"""
    if db is None:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()

    universe = [c for c in db["kline"].distinct("code") if c]
    n_universe = len(universe)

    # 基准日：fund_flow 最近有数据的日期（今日未采集/节假日时回退）
    ff_dates = sorted((str(d) for d in db["fund_flow"].distinct("date") if d), reverse=True)
    ref_date = ff_dates[0] if ff_dates else beijing_now().strftime("%Y-%m-%d")
    trading = set(db["fund_flow"].distinct("code", {"date": ref_date}))
    n_trading = len(trading)

    sources: List[Dict[str, Any]] = []

    # ── kline：逐只采集，最易出缺口，按"在交易"基准比对并给出缺口示例 ──
    try:
        ref_dt = datetime.strptime(ref_date, "%Y-%m-%d")
        kline_codes = set(db["kline"].distinct("code", {"date": ref_dt}))
        missing = sorted(trading - kline_codes)
        sources.append({
            "name": "kline", "label": f"K线（{ref_date}）",
            "covered": len(trading & kline_codes), "expected": n_trading,
            "missing_count": len(missing), "missing_sample": missing[:10],
            "status": _status(len(trading & kline_codes), n_trading),
        })
    except Exception as e:
        logger.warning(f"coverage kline failed: {e}")

    # ── fund_flow：与全市场比（它本身就是基准，给出绝对覆盖） ──
    sources.append({
        "name": "fund_flow", "label": f"资金流向（{ref_date}）",
        "covered": n_trading, "expected": n_universe,
        "missing_count": n_universe - n_trading, "missing_sample": [],
        "status": _status(n_trading, n_universe),
    })

    # ── 估值缓存：今日刷新的条数 ──
    try:
        today_start = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 兼容 naive datetime 存储
        fresh = db["stock_valuation"].count_documents(
            {"_updated_at": {"$gte": today_start.replace(tzinfo=None)}})
        total_val = db["stock_valuation"].count_documents({})
        covered = fresh if fresh > 0 else total_val
        label = "估值缓存（今日刷新）" if fresh > 0 else "估值缓存（总量）"
        sources.append({
            "name": "stock_valuation", "label": label,
            "covered": covered, "expected": n_universe,
            "missing_count": max(0, n_universe - covered), "missing_sample": [],
            "status": _status(covered, n_universe),
        })
    except Exception as e:
        logger.warning(f"coverage valuation failed: {e}")

    # ── 股票信息 / 财务（最新报告期） ──
    try:
        si = len(db["stock_info"].distinct("code"))
        sources.append({
            "name": "stock_info", "label": "股票信息",
            "covered": si, "expected": n_universe,
            "missing_count": max(0, n_universe - si), "missing_sample": [],
            "status": _status(si, n_universe),
        })
    except Exception as e:
        logger.warning(f"coverage stock_info failed: {e}")

    try:
        # 最新报告期 = 库内最大 report_date 的年月（同季度），统计覆盖该报告期的股票数
        latest = db["financial"].find_one({}, {"report_date": 1}, sort=[("report_date", -1)])
        if latest and latest.get("report_date"):
            period = str(latest["report_date"])[:7]  # 如 "2026-03"
            fin = len(db["financial"].distinct("code", {"report_date": {"$regex": f"^{period}"}}))
            sources.append({
                "name": "financial", "label": f"财务（{period} 报告期）",
                "covered": fin, "expected": n_universe,
                "missing_count": max(0, n_universe - fin), "missing_sample": [],
                "status": _status(fin, n_universe),
            })
    except Exception as e:
        logger.warning(f"coverage financial failed: {e}")

    overall = "ok"
    if any(s["status"] == "bad" for s in sources):
        overall = "bad"
    elif any(s["status"] == "warn" for s in sources):
        overall = "warn"

    return {
        "ref_date": ref_date,
        "universe_count": n_universe,
        "trading_count": n_trading,
        "overall": overall,
        "sources": sources,
        "checked_at": beijing_now().isoformat(),
    }
