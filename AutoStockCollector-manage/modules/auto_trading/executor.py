"""UnifiedAutoTrader — 自动交易编排层（薄）。

职责：构造依赖 → 拉持仓/候选 → 交 DecisionEngine 产 Decision → 按 priority 执行 → 快照+日志。
买卖均补 account 参数（修复原 bug 1/13）；snapshot 用正确签名（修复 bug 3）；
log_cycle 无条件记录（修复 bug 6）。
"""
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.database import DatabaseConfig
from modules.paper_trading.account import PaperAccount
from modules.paper_trading.snapshot import PortfolioSnapshot
from modules.paper_trading.trade_engine import TradeEngine
from modules.pre_market_call_auction.intraday_tracker import (
    AUTO_TRADE_ENABLED,
    _strip_prefix_from_code,
)
from utils.helpers import beijing_now
from utils.logger import get_logger

from .config import AutoTradingConfig
from .config_store import ConfigStore
from .decision_engine import Decision, DecisionEngine
from .drawdown_strategy import DrawdownChecker
from .risk_manager import RiskManager
from .signal_fusion import SignalFusionEngine

logger = get_logger(__name__)


class UnifiedAutoTrader:
    def __init__(self):
        self._config_store = ConfigStore()
        self._account = PaperAccount()
        self._engine = TradeEngine()
        self._fusion = SignalFusionEngine(self._config_store)
        self._drawdown = DrawdownChecker()
        self._risk = RiskManager(self._engine, self._account, self._config_store)
        self._decision = DecisionEngine(
            self._fusion, self._drawdown, self._risk, self._config_store, self._account
        )
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "last_cycle": None, "total_run": 0, "buys": 0, "sells": 0,
            "adds": 0, "reduces": 0, "drawdown_sells": 0, "drawdown_reduces": 0,
            "errors": 0, "status": "idle",
        }

    # ── 单轮编排 ──────────────────────────────────────────────────
    def run_cycle(self, user_id: str = "default", date: Optional[str] = None) -> Dict[str, Any]:
        if not AUTO_TRADE_ENABLED:
            return {"status": "disabled", "message": "Auto-trade is globally disabled"}
        if not self._lock.acquire(blocking=False):
            return {"status": "locked", "message": "Previous cycle still running"}

        try:
            return self._do_cycle(user_id, date or beijing_now().strftime("%Y-%m-%d"))
        finally:
            self._lock.release()

    def _do_cycle(self, user_id: str, date: str) -> Dict[str, Any]:
        now = beijing_now()
        self._stats["last_cycle"] = now.isoformat()
        self._stats["total_run"] += 1
        self._stats["status"] = "running"
        logger.info(f"[auto-trader] Cycle started at {now.isoformat()} (user={user_id})")

        summary: Dict[str, Any] = {
            "date": date, "cycle_time": now.isoformat(), "user_id": user_id,
            "positions_checked": 0, "candidates_checked": 0,
            "buys": 0, "sells": 0, "adds": 0, "reduces": 0,
            "errors": 0, "details": [],
        }

        try:
            acc_doc = self._ensure_account(user_id)
            if not acc_doc:
                summary["errors"] = 1
                summary["message"] = "Failed to ensure account"
                self._stats["status"] = "error"
                self._log_cycle(summary)
                return summary
            cash = acc_doc.get("cash_balance", 0)

            positions, _ = self._engine.get_positions(user_id)
            held_positions = positions or []
            pos_map = {}
            for p in held_positions:
                code = _strip_prefix_from_code(p.get("code", ""))
                if code:
                    p.setdefault("industry", "")
                    pos_map[code] = p

            # ── 持仓决策 ──
            held_decisions: List[Decision] = []
            for code, pos in pos_map.items():
                try:
                    fused = self._fusion.fuse(code, date, name=pos.get("name", ""))
                    # 回填 industry 到 pos 供 risk 板块检查
                    if fused.industry and not pos.get("industry"):
                        pos["industry"] = fused.industry
                    decision = self._decision.decide_held(pos, fused, cash, user_id, date, held_positions)
                    held_decisions.append(decision)
                except Exception as e:
                    logger.error(f"[auto-trader] Error processing held {code}: {e}")
                    summary["errors"] += 1

            # ── 候选决策 ──
            candidates = self._get_candidates(date, set(pos_map.keys()))
            cand_decisions: List[Decision] = []
            for cand in candidates:
                try:
                    code = _strip_prefix_from_code(cand.get("symbol", cand.get("code", "")))
                    if not code or code in pos_map:
                        continue
                    fused = self._fusion.fuse(code, date, name=cand.get("name", ""))
                    decision = self._decision.decide_candidate(
                        cand, fused, cash, user_id, date, held_positions
                    )
                    if decision.action == "buy":
                        cand_decisions.append(decision)
                except Exception as e:
                    logger.error(f"[auto-trader] Error processing candidate: {e}")
                    summary["errors"] += 1

            summary["positions_checked"] = len(pos_map)
            summary["candidates_checked"] = len(candidates)

            # ── 执行（按 priority 降序：先卖后买，避免现金占用冲突）──
            all_decisions = held_decisions + cand_decisions
            all_decisions.sort(key=lambda d: -d.priority)
            for d in all_decisions:
                self._execute_decision(user_id, d, summary)

            # 清理已平仓持仓的 peak 记录
            try:
                self._drawdown.cleanup_closed(set(pos_map.keys()))
            except Exception as e:
                logger.warning(f"[auto-trader] drawdown cleanup failed: {e}")

            # ── 快照 + 日志（无条件） ──
            self._save_snapshot(user_id)
            self._log_cycle(summary)

            self._stats["buys"] += summary["buys"]
            self._stats["sells"] += summary["sells"]
            self._stats["adds"] += summary["adds"]
            self._stats["reduces"] += summary["reduces"]
            self._stats["errors"] += summary["errors"]
            self._stats["status"] = "idle"

            logger.info(
                f"[auto-trader] Cycle done: {summary['buys']} buys, {summary['sells']} sells, "
                f"{summary['adds']} adds, {summary['reduces']} reduces, {summary['errors']} errors"
            )
            return summary

        except Exception as e:
            logger.error(f"[auto-trader] Cycle failed: {e}", exc_info=True)
            self._stats["status"] = "error"
            self._stats["errors"] += 1
            summary["errors"] += 1
            summary["message"] = str(e)
            self._log_cycle(summary)
            return summary

    # ── 执行单个决策 ──────────────────────────────────────────────
    def _execute_decision(self, user_id: str, d: Decision, summary: Dict):
        if d.action in ("hold",):
            return
        raw_code = RiskManager.normalize_for_trade(d.code)
        ai_signal = {"source": "auto_trader" if d.source == "fusion" else d.source,
                     "reason": d.reason, "score": getattr(d, "_score", None) or 0}

        try:
            if d.action == "sell":
                ok, reason = self._risk.check_sell(d.code, d.price, self._pos_prev_close(d.code))
                if not ok:
                    logger.info(f"[auto-trader] Skip sell {d.code}: {reason}")
                    return
                self._do_trade("sell", user_id, raw_code, d.shares, ai_signal)
                summary["sells"] += 1
                if d.source == "drawdown_stop":
                    self._stats["drawdown_sells"] += 1

            elif d.action == "reduce":
                ok, reason = self._risk.check_sell(d.code, d.price, self._pos_prev_close(d.code))
                if not ok:
                    logger.info(f"[auto-trader] Skip reduce {d.code}: {reason}")
                    return
                self._do_trade("sell", user_id, raw_code, d.shares, ai_signal)
                summary["reduces"] += 1
                if d.source == "drawdown_stop":
                    self._stats["drawdown_reduces"] += 1

            elif d.action == "buy":
                self._do_trade("buy", user_id, raw_code, d.shares, ai_signal,
                               price=d.price, stop_loss=d.stop_loss, take_profit=d.take_profit)
                summary["buys"] += 1

            elif d.action == "add":
                self._do_trade("buy", user_id, raw_code, d.shares, ai_signal,
                               price=d.price, stop_loss=d.stop_loss, take_profit=d.take_profit)
                summary["adds"] += 1

            summary["details"].append({
                "action": d.action, "code": d.code, "name": d.name, "shares": d.shares,
                "price": d.price, "stop_loss": d.stop_loss, "take_profit": d.take_profit,
                "source": d.source, "reason": d.reason,
            })
        except Exception as e:
            logger.warning(f"[auto-trader] Execute {d.action} {d.code} failed: {e}")
            summary["errors"] += 1

    def _do_trade(self, action: str, user_id: str, raw_code: str, shares: int,
                  ai_signal: Dict, price: Optional[float] = None,
                  stop_loss: Optional[float] = None, take_profit: Optional[float] = None):
        """统一执行 buy/sell，适配远程 paper_trading 的 T+1 + 挂单接口。

        - immediate=True：自动交易即时成交，不挂单。
        - 不加 force：遵守 T+1（当日买入不可卖）。T+1 拦截会抛 ValueError，由调用方 try/except 记 error。
        - 返回值 {status, trade?, order?}：pending（非交易时段挂单）视为未成交，仅记日志。
        """
        if action == "buy":
            result = self._engine.buy(
                user_id, raw_code, shares, ai_signal, self._account,
                price=price, stop_loss=stop_loss, take_profit=take_profit, immediate=True,
            )
        else:
            result = self._engine.sell(
                user_id, raw_code, shares, ai_signal, self._account,
                price=price, immediate=True,
            )
        status = result.get("status") if isinstance(result, dict) else None
        if status == "pending":
            logger.info(f"[auto-trader] {raw_code} {action} {shares} 挂单 pending（非交易时段），待撮合")
        elif status != "filled":
            logger.warning(f"[auto-trader] {raw_code} {action} 未成交，status={status}")

    def _pos_prev_close(self, code: str) -> Optional[float]:
        """取持仓的昨收（用于卖出跌停检查）。"""
        try:
            positions, _ = self._engine.get_positions("default")
            for p in positions or []:
                if _strip_prefix_from_code(p.get("code", "")) == code:
                    return p.get("yesterday_close")
        except Exception:
            pass
        return None

    # ── 候选获取 ──────────────────────────────────────────────────
    def _get_candidates(self, date: str, held_codes: set) -> List[Dict[str, Any]]:
        cfg = self._config_store.load()
        try:
            db = DatabaseConfig.get_database()
            result = db["auction_results"].find_one({"date": date}, sort=[("created_at", -1)])
            if not result:
                return []
            candidates = []
            for s in (result.get("top_stocks", []) or []):
                code = _strip_prefix_from_code(s.get("symbol", ""))
                if not code or code in held_codes:
                    continue
                trap = s.get("trap_warning", {}) or {}
                if trap.get("is_trap"):
                    continue
                gap = s.get("gap_pct", 0.0) or 0.0
                score = s.get("strength_score", 0) or 0
                if score >= cfg.MIN_AUCTION_SCORE and gap >= cfg.MIN_AUCTION_GAP:
                    candidates.append({
                        "symbol": code, "name": s.get("name", ""),
                        "industry": s.get("industry", ""),
                        "strength_score": score, "gap_pct": gap,
                        "prev_close": s.get("prev_close"),
                    })
            return candidates[:20]
        except Exception as e:
            logger.warning(f"[auto-trader] Get candidates failed: {e}")
            return []

    # ── 账户 / 快照 / 日志 ───────────────────────────────────────
    def _ensure_account(self, user_id: str) -> Optional[Dict]:
        try:
            doc = self._account.get(user_id)
            if not doc:
                self._account.init(100000, user_id)
                doc = self._account.get(user_id)
            return doc
        except Exception as e:
            logger.error(f"[auto-trader] Ensure account failed: {e}")
            return None

    def _save_snapshot(self, user_id: str):
        try:
            PortfolioSnapshot().record(user_id, self._account, self._engine)
        except Exception as e:
            logger.warning(f"[auto-trader] Snapshot failed: {e}")

    def _log_cycle(self, summary: Dict):
        """无条件记录每轮（含空轮询和错误轮），便于排障。"""
        try:
            cfg = self._config_store.load()
            db = DatabaseConfig.get_database()
            db[cfg.LOG_COLLECTION].insert_one({
                "date": summary.get("date"),
                "cycle_time": summary.get("cycle_time"),
                "user_id": summary.get("user_id", "default"),
                "buys": summary.get("buys", 0),
                "sells": summary.get("sells", 0),
                "adds": summary.get("adds", 0),
                "reduces": summary.get("reduces", 0),
                "errors": summary.get("errors", 0),
                "message": summary.get("message", ""),
                "details": summary.get("details", []),
            })
        except Exception as e:
            logger.warning(f"[auto-trader] Log cycle failed: {e}")

    # ── 状态 / 信号查询（供 API） ────────────────────────────────
    def get_stats(self, user_id: str = "default") -> Dict[str, Any]:
        try:
            acc = self._account.get(user_id) or {"cash_balance": 0, "initial_capital": 0}
            positions, _ = self._engine.get_positions(user_id)
            pos_list = []
            for p in (positions or []):
                pos_list.append({
                    "code": p.get("code", ""),
                    "name": p.get("name", ""),
                    "shares": p.get("shares", 0),
                    "avg_cost": p.get("avg_cost", 0),
                    "current_price": p.get("current_price", 0),
                    "market_value": p.get("market_value", 0),
                    "pnl": p.get("pnl", 0),
                    "pnl_percent": p.get("pnl_percent", 0),
                    "stop_loss": p.get("stop_loss"),
                    "take_profit": p.get("take_profit"),
                    "sl_hit": p.get("sl_hit", False),
                    "tp_hit": p.get("tp_hit", False),
                })
            total_mv = sum(p["market_value"] for p in pos_list)
            total_cost = sum(p["avg_cost"] * p["shares"] for p in pos_list)
            total_pnl = sum(p["pnl"] for p in pos_list)
            cash = acc.get("cash_balance", 0)
            total_assets = total_mv + cash
            cfg = self._config_store.load()
            return {
                "enabled": AUTO_TRADE_ENABLED,
                "account_cash": round(cash, 2),
                "initial_capital": round(acc.get("initial_capital", 0), 2),
                "total_market_value": round(total_mv, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
                "position_count": len(pos_list),
                "max_positions": cfg.MAX_POSITIONS,
                "exposure_pct": round(total_mv / total_assets * 100, 2) if total_assets > 0 else 0,
                "positions": pos_list,
                "stats": self._stats,
            }
        except Exception as e:
            return {"enabled": AUTO_TRADE_ENABLED, "error": str(e)}

    def get_signals(self, date: str, user_id: str = "default") -> List[Dict]:
        try:
            held = set()
            positions, _ = self._engine.get_positions(user_id)
            for p in (positions or []):
                held.add(_strip_prefix_from_code(p.get("code", "")))
            candidates = self._get_candidates(date, set())
            codes = [{"code": c.get("symbol", ""), "name": c.get("name", "")} for c in candidates]
            for p in (positions or []):
                raw = _strip_prefix_from_code(p.get("code", ""))
                if raw:
                    codes.append({"code": raw, "name": p.get("name", "")})
            seen, unique = set(), []
            for c in codes:
                if c["code"] and c["code"] not in seen:
                    seen.add(c["code"])
                    unique.append(c)
            fused_list = self._fusion.batch_fuse(unique, date)
            return [
                {
                    "code": f.code, "name": f.name,
                    "overall_score": f.overall_score, "signal": f.signal,
                    "reasons": f.reasons, "held": f.code in held,
                    "breakdown": {
                        "auction_score": f.auction_score,
                        "auction_gap": f.auction_gap,
                        "auction_trap": f.auction_trap,
                        "pa_signal": f.pa_signal,
                        "pa_confidence": f.pa_confidence,
                        "ai_score": f.ai_score,
                        "ai_signal": f.ai_signal,
                        "industry": f.industry,
                    },
                }
                for f in fused_list
            ]
        except Exception as e:
            logger.error(f"[auto-trader] Get signals failed: {e}")
            return []

    def close_all(self, user_id: str = "default") -> Dict[str, Any]:
        """一键平仓（从 API 下沉）。走 immediate 成交，遵守 T+1。"""
        try:
            positions, _ = self._engine.get_positions(user_id)
            closed = 0
            skipped = 0
            for p in (positions or []):
                try:
                    code = p.get("code", "")
                    shares = p.get("shares", 0)
                    if code and shares > 0:
                        self._do_trade("sell", user_id, code, shares,
                                       {"source": "auto_trader", "reason": "手动平仓"})
                        closed += 1
                except Exception as e:
                    skipped += 1
                    logger.warning(f"[auto-trader] Close {p.get('code')} failed: {e}")
            return {"closed": closed, "skipped": skipped, "total": len(positions or [])}
        except Exception as e:
            return {"closed": 0, "total": 0, "error": str(e)}
