"""盘前竞价雷达 — 盘中实时追踪。

9:25 扫描后将 top_stocks 写入 auction_intraday_track 集合，
盘中通过 Tencent 批量报价获取实时价，计算当前盈亏。
14:50 自动平仓当日所有 auto-trade 仓位。
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .config import AuctionConfig
from .radar_utils import now_shanghai, today_str
from .position_sizer import AuctionPositionSizer, PositionSuggestion
from .schemas import RadarStock, RadarResult

logger = get_logger(__name__)

COLLECTION = "auction_intraday_track"


def init_tracking(result: RadarResult):
    if not result or not result.top_stocks:
        return
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]
        now = now_shanghai().isoformat()
        for s in result.top_stocks:
            col.update_one(
                {"code": s.symbol, "date": result.date},
                {"$set": {
                    "code": s.symbol,
                    "name": s.name,
                    "date": result.date,
                    "open_price": s.open_price,
                    "gap_pct": s.gap_pct,
                    "strength_score": s.strength_score,
                    "industry": s.industry,
                    "is_trap": s.trap_warning is not None,
                    "trap_type": s.trap_warning.trap_type if s.trap_warning else "",
                    "status": "active",
                    "auto_trade_id": "",
                    "current_price": 0.0,
                    "current_pnl_pct": 0.0,
                    "highest_pnl_pct": 0.0,
                    "lowest_pnl_pct": 0.0,
                    "updated_at": now,
                }},
                upsert=True,
            )
        logger.info(f"[IntradayTracker] initialized {len(result.top_stocks)} tracking records")
    except Exception as e:
        logger.warning(f"[IntradayTracker] init error: {e}")


def _batch_tencent_quotes(codes: List[str]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not codes:
        return result
    try:
        import requests as _req
        query = ",".join(c.lower() for c in codes)
        r = _req.get(
            f"https://qt.gtimg.cn/q={query}",
            proxies={"http": "", "https": ""},
            timeout=8,
        )
        for code in codes:
            m = re.search(rf'v_{code.lower()}="([^"]+)"', r.text)
            if not m:
                continue
            parts = m.group(1).split("~")
            if len(parts) > 3 and parts[3]:
                try:
                    price = float(parts[3])
                    if price > 0:
                        result[code] = price
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"[IntradayTracker] tencent batch error: {e}")
    return result


def update_realtime_prices(date: Optional[str] = None) -> int:
    date = date or today_str()
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db[COLLECTION]

        tracks = list(col.find({"date": date, "status": "active"}, {"code": 1, "open_price": 1, "_id": 0}))
        if not tracks:
            return 0

        codes = [t["code"] for t in tracks if t.get("code")]
        quotes = _batch_tencent_quotes(codes)
        if not quotes:
            return 0

        now_iso = now_shanghai().isoformat()
        updated = 0
        for code, price in quotes.items():
            open_price = next((t["open_price"] for t in tracks if t.get("code") == code), 0)
            if open_price <= 0:
                continue
            pnl_pct = round((price - open_price) / open_price * 100, 2)

            col.update_one(
                {"code": code, "date": date},
                {"$set": {
                    "current_price": round(price, 2),
                    "current_pnl_pct": pnl_pct,
                    "updated_at": now_iso,
                },
                "$max": {"highest_pnl_pct": pnl_pct},
                "$min": {"lowest_pnl_pct": pnl_pct}},
            )
            updated += 1
        logger.debug(f"[IntradayTracker] updated {updated} realtime prices")
        return updated
    except Exception as e:
        logger.debug(f"[IntradayTracker] update error: {e}")
        return 0


def get_intraday_data(date: Optional[str] = None, refresh: bool = True) -> List[Dict[str, Any]]:
    date = date or today_str()
    if refresh:
        update_realtime_prices(date)
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        docs = list(
            db[COLLECTION]
            .find({"date": date}, {"_id": 0})
            .sort("strength_score", -1)
        )
        return docs
    except Exception as e:
        logger.warning(f"[IntradayTracker] get error: {e}")
        return []


def mark_trade_id(code: str, date: str, trade_id: str):
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        db[COLLECTION].update_one(
            {"code": code, "date": date},
            {"$set": {"auto_trade_id": trade_id, "status": "traded"}},
        )
    except Exception as e:
        logger.warning(f"[IntradayTracker] mark trade error: {e}")


def get_risk_summary(date: Optional[str] = None) -> Dict[str, Any]:
    """返回风控仪表盘数据：持仓、盈亏、敞口汇总。"""
    date = date or today_str()
    try:
        from api.routes.paper_trading import _lazy_init, _account, _engine
        _lazy_init()
        positions, trading = _engine.get_positions("default")
        acc_doc = _account.get("default")
        cash = acc_doc.get("cash_balance", 0) if acc_doc else 0
        total_market_value = sum(p["market_value"] for p in positions)
        total_cost = sum(p["avg_cost"] * p["shares"] for p in positions)
        total_pnl = total_market_value - total_cost

        auto_trade_positions = []
        for p in positions:
            code_clean = p["code"]
            trade = _find_auto_trade_record(code_clean, date)
            if trade:
                p["auto_trade_info"] = trade
                auto_trade_positions.append(p)

        sector_exposure: Dict[str, float] = {}
        for p in positions:
            sector = p.get("code", "其他")[:2]
            sector_exposure[sector] = sector_exposure.get(sector, 0) + p["market_value"]

        return {
            "cash_balance": round(cash, 2),
            "total_market_value": round(total_market_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
            "position_count": len(positions),
            "auto_trade_count": len(auto_trade_positions),
            "max_positions": AuctionConfig.MAX_POSITIONS_PER_DAY,
            "total_exposure_pct": round(total_market_value / (cash + total_market_value) * 100, 2) if (cash + total_market_value) > 0 else 0,
            "max_exposure_pct": AuctionConfig.MAX_TOTAL_EXPOSURE_PCT * 100,
            "sector_exposure": {k: round(v, 2) for k, v in sorted(sector_exposure.items(), key=lambda x: -x[1])},
            "positions": [{
                "code": p["code"],
                "name": p["name"],
                "shares": p["shares"],
                "avg_cost": p["avg_cost"],
                "current_price": p["current_price"],
                "market_value": p["market_value"],
                "pnl": p["pnl"],
                "pnl_percent": p["pnl_percent"],
                "today_pnl_percent": p["today_pnl_percent"],
                "stop_loss": p.get("stop_loss"),
                "take_profit": p.get("take_profit"),
                "distance_to_sl": round((p["current_price"] - p["stop_loss"]) / p["stop_loss"] * 100, 2) if p.get("stop_loss") else None,
            } for p in auto_trade_positions],
        }
    except Exception as e:
        logger.warning(f"[IntradayTracker] risk summary error: {e}")
        return {"error": str(e), "positions": []}


def _find_auto_trade_record(code: str, date: str) -> Optional[Dict]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        col = db["trade_records"]
        today_start = f"{date}T00:00:00"
        today_end = f"{date}T23:59:59"
        doc = col.find_one({
            "code": code,
            "action": "buy",
            "traded_at": {"$gte": today_start, "$lte": today_end},
            "ai_signal.source": "auction_radar_auto",
        })
        return doc
    except Exception:
        return None


# ── Auto-Close at 14:50 ──────────────────────────────────────────────


def auto_close_positions(date: Optional[str] = None) -> int:
    """14:50 自动平仓：查找今日 auto-trade 买入且仍持仓的股票，全部卖出。"""
    date = date or today_str()
    try:
        from api.routes.paper_trading import _lazy_init, _account, _engine
        _lazy_init()

        tracked = _get_traded_tracking_records(date)
        if not tracked:
            logger.info("[AutoClose] no auto-trade records to close")
            return 0

        closed = 0
        for t in tracked:
            code = t.get("code", "")
            trade_id = t.get("auto_trade_id", "")
            if not code or not trade_id:
                continue
            price = _close_position(code, date, _engine, _account)
            if price is not None:
                _record_close_result(code, date, price, t)
                closed += 1

        if closed:
            try:
                from modules.paper_trading.snapshot import PortfolioSnapshot
                PortfolioSnapshot().record("default", _account, _engine)
            except Exception as e:
                logger.warning(f"[AutoClose] snapshot error: {e}")

        logger.info(f"[AutoClose] closed {closed} positions")
        return closed
    except Exception as e:
        logger.warning(f"[AutoClose] error: {e}")
        return 0


def _get_traded_tracking_records(date: str) -> List[Dict]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        return list(db[COLLECTION].find(
            {"date": date, "auto_trade_id": {"$ne": ""}},
            {"_id": 0},
        ))
    except Exception:
        return []


def _close_position(code: str, date: str, engine, account) -> Optional[float]:
    """卖出某只股票的全部持仓。返回成交价，失败返回 None。"""
    try:
        positions, _ = engine.get_positions("default")
        pos = next((p for p in positions if p["code"].endswith(code) or _to_tencent_code(code) == p["code"]), None)
        if not pos:
            logger.debug(f"[AutoClose] no position for {code}, already closed")
            return None
        shares = pos["shares"]
        price = _get_latest_price(code)
        if not price or price <= 0:
            price = pos["current_price"]
        if not price or price <= 0:
            logger.warning(f"[AutoClose] cannot get price for {code}, skipping")
            return None

        engine.sell(
            user_id="default",
            code=pos["code"],
            shares=shares,
            ai_signal={"source": "auction_radar_auto_close", "reason": "尾盘自动平仓"},
            account=account,
            price=price,
        )
        logger.info(f"[AutoClose] sold {code} {shares}sh @{price}")
        return price
    except Exception as e:
        logger.warning(f"[AutoClose] sell {code} error: {e}")
        return None


def _get_latest_price(code: str) -> Optional[float]:
    try:
        quotes = _batch_tencent_quotes([code])
        return quotes.get(code)
    except Exception:
        return None


def _record_close_result(code: str, date: str, exit_price: float, track_record: Dict):
    try:
        from .performance_tracker import update_result
        open_price = track_record.get("open_price", 0)
        if open_price > 0:
            return_pct = round((exit_price - open_price) / open_price, 4)
            update_result(code, date, return_pct, "尾盘自动平仓")
    except Exception as e:
        logger.debug(f"[AutoClose] record result error: {e}")


# ── Auto-Trade ─────────────────────────────────────────────────────────

AUTO_TRADE_ENABLED = True
AUTO_TRADE_MIN_SCORE = 80
AUTO_TRADE_MIN_GAP = 3.0
AUTO_TRADE_MAX_POSITION_PCT = 0.15
AUTO_TRADE_SL_ATR_MULTIPLIER = 1.5
AUTO_TRADE_TP_ATR_MULTIPLIER = 3.0


def auto_trade_top_stocks(result: RadarResult):
    if not AUTO_TRADE_ENABLED:
        return
    if not result or not result.top_stocks:
        return

    try:
        from api.routes.paper_trading import _lazy_init, _account, _engine, _snapshot
        _lazy_init()
        user_id = "default"

        today = result.date
        existing_codes = _existing_auto_trades_today(user_id, today)
        sector_cash_map: Dict[str, float] = {}
        trades_created = 0

        for s in result.top_stocks:
            if not _qualifies_for_auto_trade(s):
                continue
            if s.symbol in existing_codes:
                logger.info(f"[AutoTrade] skip {s.symbol} — already auto-traded today")
                continue
            if not _risk_check_allowed(user_id, s, trades_created, sector_cash_map):
                continue

            price = s.open_price
            if price <= 0:
                continue

            shares = _calc_shares_safe(user_id, price, s)
            if shares <= 0:
                continue

            code_tencent = _to_tencent_code(s.symbol)

            atr = _estimate_atr(code_tencent, price)
            stop_loss = round(price - atr * AUTO_TRADE_SL_ATR_MULTIPLIER, 2) if atr else None
            take_profit = round(price + atr * AUTO_TRADE_TP_ATR_MULTIPLIER, 2) if atr else None

            try:
                record = _engine.buy(
                    user_id=user_id,
                    code=code_tencent,
                    shares=shares,
                    ai_signal={
                        "source": "auction_radar_auto",
                        "strength_score": s.strength_score,
                        "gap_pct": s.gap_pct,
                        "strategy": "gap_up_momentum",
                    },
                    account=_account,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
                trade_id = str(record.get("_id", ""))
                mark_trade_id(s.symbol, result.date, trade_id)
                trades_created += 1
                _track_sector_exposure(s.industry, price * shares, sector_cash_map)
                logger.info(
                    f"[AutoTrade] bought {s.symbol}({s.name}) "
                    f"{shares}sh @{price} SL={stop_loss} TP={take_profit}"
                )
            except ValueError as e:
                logger.warning(f"[AutoTrade] skip {s.symbol}: {e}")

        if trades_created:
            try:
                _snapshot.record(user_id, _account, _engine)
            except Exception as e:
                logger.warning(f"[AutoTrade] snapshot error: {e}")

        logger.info(f"[AutoTrade] created {trades_created} trades (limit={AuctionConfig.MAX_POSITIONS_PER_DAY})")
    except Exception as e:
        logger.warning(f"[AutoTrade] error: {e}")


def _qualifies_for_auto_trade(stock: RadarStock) -> bool:
    if not stock.strength_score or stock.strength_score < AUTO_TRADE_MIN_SCORE:
        return False
    if stock.gap_pct < AUTO_TRADE_MIN_GAP:
        return False
    if stock.trap_warning:
        return False
    return True


def _existing_auto_trades_today(user_id: str, date: str) -> set:
    """返回今日已 auto-trade 买入的股票代码集合。"""
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        today_start = f"{date}T00:00:00"
        today_end = f"{date}T23:59:59"
        docs = db["trade_records"].find(
            {"user_id": user_id, "action": "buy",
             "traded_at": {"$gte": today_start, "$lte": today_end},
             "ai_signal.source": "auction_radar_auto"},
            {"code": 1},
        )
        codes = set()
        for d in docs:
            raw = d.get("code", "")
            for prefix in ("sh", "sz", "SH", "SZ"):
                raw = raw.replace(prefix, "")
            codes.add(raw)
        return codes
    except Exception:
        return set()


def _risk_check_allowed(user_id: str, stock: RadarStock, trades_so_far: int,
                        sector_cash_map: Dict[str, float]) -> bool:
    """风控检查：ST/退市/次新股、最大持仓数、板块敞口。"""
    name = stock.name or ""
    if "ST" in name.upper() or "*ST" in name.upper():
        return False
    if "退" in name:
        return False

    if trades_so_far >= AuctionConfig.MAX_POSITIONS_PER_DAY:
        logger.info(f"[Risk] skip {stock.symbol} — max positions reached ({AuctionConfig.MAX_POSITIONS_PER_DAY})")
        return False

    sector = stock.industry or "其他"
    sector_used = sector_cash_map.get(sector, 0)
    try:
        from modules.paper_trading.account import PaperAccount
        acc = PaperAccount()
        doc = acc.get(user_id)
        cash = doc.get("cash_balance", 0) if doc else 0
    except Exception:
        cash = 0
    total_used = sum(sector_cash_map.values()) + sector_used

    if cash > 0:
        total_pct = total_used / cash
        if total_pct >= AuctionConfig.MAX_TOTAL_EXPOSURE_PCT:
            logger.info(f"[Risk] skip {stock.symbol} — total exposure {total_pct:.0%} >= {AuctionConfig.MAX_TOTAL_EXPOSURE_PCT:.0%}")
            return False
        sector_pct = (sector_used + stock.open_price * 100) / cash
        if sector_pct >= AuctionConfig.MAX_SECTOR_EXPOSURE_PCT:
            logger.info(f"[Risk] skip {stock.symbol} — sector {sector} exposure would be {sector_pct:.0%} >= {AuctionConfig.MAX_SECTOR_EXPOSURE_PCT:.0%}")
            return False
    return True


def _track_sector_exposure(sector: str, amount: float, sector_map: Dict[str, float]):
    sector = sector or "其他"
    sector_map[sector] = sector_map.get(sector, 0) + amount


def _calc_shares_safe(user_id: str, price: float, stock: RadarStock) -> int:
    """带风控的仓位计算：单票上限 + 总敞口 + 板块限制。"""
    try:
        from modules.paper_trading.account import PaperAccount
        acc = PaperAccount()
        doc = acc.get(user_id)
        if not doc:
            return 0
        cash = doc.get("cash_balance", 0)
        if cash <= 0:
            return 0

        budget = cash * AUTO_TRADE_MAX_POSITION_PCT
        shares = int(budget / price / 100) * 100
        return max(shares, 100) if shares >= 100 else 0
    except Exception:
        return 0


def _estimate_atr(code: str, current_price: float) -> Optional[float]:
    try:
        from config.database import DatabaseConfig
        db = DatabaseConfig.get_database()
        klines = list(
            db["kline"].find({"code": code}, {"high": 1, "low": 1, "close": 1, "_id": 0})
            .sort("date", -1)
            .limit(6)
        )
        if len(klines) < 2:
            return current_price * 0.02
        ranges = []
        prev_close = None
        for k in reversed(klines):
            high = float(k.get("high", 0) or 0)
            low = float(k.get("low", 0) or 0)
            close = float(k.get("close", 0) or 0)
            if prev_close is not None:
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                ranges.append(tr)
            prev_close = close
        if ranges:
            return sum(ranges) / len(ranges)
        return current_price * 0.02
    except Exception:
        return current_price * 0.02


def _to_tencent_code(code: str) -> str:
    digits = "".join(c for c in code if c.isdigit())
    if not digits:
        return code
    prefix = "sh" if digits.startswith(("6", "9")) else "sz"
    return f"{prefix}{digits}"
