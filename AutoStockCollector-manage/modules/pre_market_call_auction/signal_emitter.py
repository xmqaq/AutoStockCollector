"""AuctionSignalEmitter — 竞价信号 → auto_trading 的统一出口。

修复：
- bug 1：原 auto_trade_top_stocks 里 `result = _engine.buy(...)` 覆盖入参 RadarResult，
  导致 mark_trade_id(s.symbol, result.date, ...) 抛 AttributeError 被吞成 warning →
  auto_trade_id 永不写 → 仓位不被平仓。现 emit 不再自己 buy，只写信号集合，
  由 auto_trading.DecisionEngine 消费建仓，变量遮蔽 bug 自然消除。

架构：竞价雷达不再自包含建仓/平仓，而是把合格 top_stocks 写入 auction_signals 集合
（source=auction_radar, consumed=False），auto_trading 的 decide_candidate 消费。
14:50 平仓委托 auto_trading 的 eod_close_intraday 分支（force 豁免 T+1）。
"""
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne

from utils.logger import get_logger
from .config import AuctionConfig
from .radar_utils import (
    now_shanghai, today_str, estimate_atr, strip_prefix_from_code,
)
from .schemas import RadarResult, RadarStock
from .tracking_store import TrackingStore

logger = get_logger(__name__)

AUTO_TRADE_SOURCE = "auction_radar"  # auto_trading 消费时识别


class AuctionSignalEmitter:
    """竞价信号发射器：把合格 top_stocks 写成 auto_trading 可消费的信号。"""

    def __init__(self, store: Optional[TrackingStore] = None):
        self._store = store or TrackingStore()

    def _db(self):
        from config.database import DatabaseConfig
        return DatabaseConfig.get_database()

    def emit(self, result: RadarResult) -> int:
        """扫描后发射信号：合格 top_stocks → auction_signals 集合（consumed=False）。

        合格条件（沿用原 _qualifies_for_auto_trade）：
          AUTO_TRADE_ENABLED 且 strength_score >= AUTO_TRADE_MIN_SCORE
          且 gap_pct >= AUTO_TRADE_MIN_GAP 且无 trap_warning。
        """
        if not AuctionConfig.AUTO_TRADE_ENABLED:
            logger.info("[SignalEmitter] auto-trade disabled, skip emit")
            return 0
        if not result or not result.top_stocks:
            return 0

        try:
            now_iso = now_shanghai().isoformat()
            ops = []
            emitted = 0
            for s in result.top_stocks:
                if not self._qualifies(s):
                    continue
                strategy = "gap_up_momentum"
                # 诱空反转：bear_trap 命中的低开大资金承接股，独立策略标记
                if s.trap_warning and s.trap_warning.trap_type == "bear_trap":
                    strategy = "bear_trap_reversal"
                ops.append(UpdateOne(
                    {"code": s.symbol, "date": result.date},
                    {"$set": {
                        "code": s.symbol, "name": s.name, "date": result.date,
                        "source": AUTO_TRADE_SOURCE,
                        "strength_score": s.strength_score, "gap_pct": s.gap_pct,
                        "industry": s.industry, "open_price": s.open_price,
                        "auction_amount": s.auction_amount,
                        "strength_detail": s.strength_detail.model_dump() if s.strength_detail else {},
                        "trap_warning": s.trap_warning.model_dump() if s.trap_warning else None,
                        "strategy": strategy,
                        "auto_close": True,            # 日内策略：14:50 强制平仓
                        "force_t1_exempt": True,      # 平仓豁免 T+1
                        "consumed": False,            # auto_trading 消费后置 True
                        "created_at": now_iso,
                    }},
                    upsert=True,
                ))
                emitted += 1
            if ops:
                self._db()[AuctionConfig.SIGNAL_COLLECTION].bulk_write(ops, ordered=False)
            logger.info(f"[SignalEmitter] emitted {emitted} auction signals for {result.date}")
            return emitted
        except Exception as e:
            logger.warning(f"[SignalEmitter] emit error: {e}")
            return 0

    def get_unconsumed(self, date: str) -> List[Dict[str, Any]]:
        """供 auto_trading 消费：取当日未消费的竞价信号。"""
        try:
            return list(self._db()[AuctionConfig.SIGNAL_COLLECTION].find(
                {"date": date, "consumed": False, "source": AUTO_TRADE_SOURCE},
                {"_id": 0},
            ))
        except Exception:
            return []

    def mark_consumed(self, code: str, date: str) -> None:
        """auto_trading 建仓后标记信号已消费。"""
        try:
            self._db()[AuctionConfig.SIGNAL_COLLECTION].update_one(
                {"code": code, "date": date},
                {"$set": {"consumed": True, "consumed_at": now_shanghai().isoformat()}},
            )
        except Exception as e:
            logger.warning(f"[SignalEmitter] mark_consumed error: {e}")

    @staticmethod
    def _qualifies(stock: RadarStock) -> bool:
        """合格条件：强度/跳空达标且无诱空诱多预警。"""
        if not stock.strength_score or stock.strength_score < AuctionConfig.AUTO_TRADE_MIN_SCORE:
            return False
        if stock.gap_pct < AuctionConfig.AUTO_TRADE_MIN_GAP:
            return False
        if stock.trap_warning:
            return False
        return True

    def close_intraday_positions(self, date: Optional[str] = None, engine=None, account=None) -> int:
        """14:50 平仓：卖出当日竞价建仓的仓位（force 豁免 T+1）。

        阶段5后此方法由 auto_trading 的 eod_close_intraday 分支接管，本方法保留为
        独立入口（供 API /auto-close 手动触发，或 auto_trading 不可用时回退）。
        """
        date = date or today_str()
        try:
            if engine is None or account is None:
                from modules.paper_trading.account import PaperAccount
                from modules.paper_trading.trade_engine import TradeEngine
                engine = engine or TradeEngine()
                account = account or PaperAccount()

            tracked = self._store.get_traded_records(date)
            if not tracked:
                logger.info("[SignalEmitter] no traded records to close")
                return 0

            from .radar_utils import batch_tencent_quotes, to_tencent_code
            tencent_codes = [to_tencent_code(t["code"]) for t in tracked if t.get("code")]
            quotes = batch_tencent_quotes(tencent_codes) if tencent_codes else {}

            closed = 0
            for t in tracked:
                code = t.get("code", "")
                if not code:
                    continue
                exit_price = self._sell_position(code, date, engine, account,
                                                  quotes.get(to_tencent_code(code)))
                if exit_price is not None:
                    open_price = t.get("open_price", 0)
                    return_pct = round((exit_price - open_price) / open_price, 4) if open_price > 0 else 0
                    self._store.close_record(code, date, exit_price, return_pct, "尾盘自动平仓")
                    closed += 1

            if closed:
                try:
                    from modules.paper_trading.snapshot import PortfolioSnapshot
                    PortfolioSnapshot().record("default", account, engine)
                except Exception as e:
                    logger.warning(f"[SignalEmitter] snapshot error: {e}")
            logger.info(f"[SignalEmitter] closed {closed} intraday positions")
            return closed
        except Exception as e:
            logger.warning(f"[SignalEmitter] close error: {e}")
            return 0

    def _sell_position(self, code: str, date: str, engine, account,
                       fallback_price: Optional[float]) -> Optional[float]:
        """卖出某只股票的全部持仓，返回成交价。"""
        from .radar_utils import to_tencent_code
        try:
            positions, _ = engine.get_positions("default")
            pos = next((p for p in positions
                        if p.get("code", "").endswith(code) or to_tencent_code(code) == p.get("code", "")), None)
            if not pos:
                return None
            shares = pos["shares"]
            price = fallback_price or pos.get("current_price", 0)
            if not price or price <= 0:
                logger.warning(f"[SignalEmitter] no price for {code}, skip")
                return None
            result = engine.sell(
                user_id="default", code=pos["code"], shares=shares,
                ai_signal={"source": "auction_radar_auto_close", "reason": "尾盘自动平仓"},
                account=account, price=price, immediate=True, force=True,  # 日内策略豁免 T+1
            )
            if isinstance(result, dict) and result.get("status") == "filled":
                logger.info(f"[SignalEmitter] sold {code} {shares}sh @{price}")
                return price
            return None
        except Exception as e:
            logger.warning(f"[SignalEmitter] sell {code} error: {e}")
            return None


# ── 向后兼容：原 intraday_tracker.auto_trade_top_stocks 的 deprecated wrapper ──
def auto_trade_top_stocks(result: RadarResult):
    """deprecated：竞价雷达不再自包含建仓。改为发射信号，由 auto_trading 消费。"""
    emitter = AuctionSignalEmitter()
    emitted = emitter.emit(result)
    # 信号发射后仍需 init_tracking（保持 intraday_track/performance 状态机初始化）
    # 注意：radar_service 已调用 init_tracking，此处不重复
    return emitted


def auto_close_positions(date: Optional[str] = None) -> int:
    """deprecated wrapper：14:50 平仓。阶段5后由 auto_trading.run_cycle 接管。"""
    return AuctionSignalEmitter().close_intraday_positions(date)
