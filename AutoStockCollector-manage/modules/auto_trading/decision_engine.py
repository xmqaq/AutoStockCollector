"""DecisionEngine — 统一决策层，消除原「主决策 + drawdown」双卖出冲突。

对每只持仓产出唯一 Decision（按优先级取首条命中规则）；对候选产出 buy/hold。
executor 拿 Decision 列表后按 priority 降序执行（先卖后买）。
"""
from dataclasses import dataclass, field
from typing import List, Optional

from utils.helpers import beijing_now
from utils.logger import get_logger

from .config import AutoTradingConfig
from .config_store import ConfigStore
from .risk_manager import RiskManager

logger = get_logger(__name__)


@dataclass
class Decision:
    action: str          # buy|add|reduce|sell|hold
    code: str            # 裸代码（不带前缀）
    name: str = ""
    shares: int = 0      # buy/add 目标股数；sell/reduce 卖出股数
    price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    source: str = "fusion"   # fusion|drawdown_stop|sl_tp|eod_close|eod_close_intraday|auction_radar
    priority: int = 0        # 大优先；sell/reduce 在前，buy/add 在后
    force: bool = False      # 卖出时是否豁免 T+1（仅 eod_close_intraday=True）


class DecisionEngine:
    def __init__(self, fusion, drawdown, risk: RiskManager, config_store: ConfigStore, account):
        self._fusion = fusion
        self._drawdown = drawdown
        self._risk = risk
        self._config_store = config_store
        self._account = account

    def _cfg(self) -> AutoTradingConfig:
        return self._config_store.load()

    # ── 持仓决策（单一优先级） ────────────────────────────────────
    def decide_held(self, pos: dict, fused, cash: float, user_id: str, date: str,
                    held_positions: List[dict]) -> Decision:
        cfg = self._cfg()
        code = pos.get("code", "")
        name = pos.get("name", "") or fused.name
        shares = pos.get("shares", 0)
        price = fused.current_price or pos.get("current_price", 0) or 0
        pnl_pct = pos.get("pnl_percent", 0) or 0

        # 100: SL/TP 命中（get_positions 内部 _auto_exit_sl_tp 已自动平仓，此处兜底标记）
        if pos.get("sl_hit") or pos.get("tp_hit"):
            return Decision("sell", code, name, shares, price,
                            reason="SL/TP 触发自动平仓", source="sl_tp", priority=100)

        # 90 / 70: 回撤规则（drawdown enabled 时）
        verdict = self._drawdown.evaluate_one(pos)
        if verdict and verdict.hit:
            return Decision(verdict.action, code, name, verdict.shares, price,
                            reason=verdict.reason, source="drawdown_stop",
                            priority=verdict.priority)

        # 85: 日内竞价策略尾盘平仓（source=auction_radar 持仓，force 豁免 T+1）
        if self._is_eod_close_time(cfg) and pos.get("_is_intraday"):
            return Decision("sell", code, name, shares, price,
                            reason="竞价日内策略尾盘平仓", source="eod_close_intraday",
                            priority=85, force=True)

        # 80: 尾盘清仓
        if self._is_eod_close_time(cfg):
            return Decision("sell", code, name, shares, price,
                            reason="尾盘自动清仓", source="eod_close", priority=80)

        # 60: 融合分强卖（亏损股阈值上浮）
        adj_sell = cfg.SELL_THRESHOLD
        if pnl_pct < cfg.LOSS_ADJ_TRIGGER_PCT:
            adj_sell += cfg.LOSS_ADJ_SELL_BUMP
        if fused.overall_score < adj_sell:
            return Decision("sell", code, name, shares, price,
                            reason=f"融合分 {fused.overall_score} < 卖出阈值 {adj_sell}",
                            source="fusion", priority=60)

        # 50: 融合分减仓（当日已减仓过则跳过，避免每轮减半直到清仓）
        if fused.overall_score < cfg.REDUCE_THRESHOLD:
            reduce_qty = max((shares // 2 // 100) * 100, 100) if shares >= 200 else 0
            if reduce_qty > 0:
                ok, _ = self._risk.check_not_reduced_today(user_id, code, date)
                if not ok:
                    return Decision("hold", code, name, 0, price,
                                    reason="今日已减仓，本轮跳过", source="fusion", priority=0)
                return Decision("reduce", code, name, reduce_qty, price,
                                reason=f"融合分 {fused.overall_score} < 减仓阈值 {cfg.REDUCE_THRESHOLD}",
                                source="fusion", priority=50)

        # 40: 融合分加仓
        if (fused.overall_score >= cfg.ADD_THRESHOLD and pos.get("stop_loss")
                and shares > 0):
            max_val = cash * cfg.MAX_SINGLE_POSITION_PCT
            if pos.get("market_value", 0) < max_val * 0.8:
                add_shares = self._calc_add_shares(cash, cfg.MAX_SINGLE_POSITION_PCT, price)
                if add_shares >= 100:
                    ok, reason = self._risk.check_add(user_id, code, fused, add_shares, price,
                                                       date, held_positions,
                                                       prev_close=pos.get("yesterday_close"))
                    if ok:
                        sl, tp = self._compute_sl_tp(code, price, cfg)
                        return Decision("add", code, name, add_shares, price,
                                        stop_loss=sl, take_profit=tp,
                                        reason=f"融合分 {fused.overall_score} ≥ 加仓阈值 {cfg.ADD_THRESHOLD}",
                                        source="fusion", priority=40)
        return Decision("hold", code, name, 0, price, source="fusion", priority=0)

    # ── 候选决策 ──────────────────────────────────────────────────
    def decide_candidate(self, cand: dict, fused, cash: float, user_id: str, date: str,
                         held_positions: List[dict]) -> Decision:
        cfg = self._cfg()
        code = cand.get("symbol", cand.get("code", ""))
        name = cand.get("name", "") or fused.name

        # 竞价信号分支：source=auction_radar 走竞价专用阈值（MIN_AUCTION_SCORE/MIN_GAP）
        if cand.get("source") == "auction_radar":
            return self._decide_auction_candidate(cand, fused, cash, user_id, date, held_positions)

        price = fused.current_price or 0
        if price <= 0:
            return Decision("hold", code, name, 0, price, source="fusion", priority=0)
        if fused.overall_score < cfg.BUY_THRESHOLD:
            return Decision("hold", code, name, 0, price, source="fusion", priority=0)

        shares = self._calc_buy_shares(cash, cfg.MAX_SINGLE_POSITION_PCT, price)
        if shares < 100:
            return Decision("hold", code, name, 0, price,
                            reason="单票预算不足 100 股", source="fusion", priority=0)

        prev_close = cand.get("prev_close") or cand.get("yesterday_close")
        ok, reason = self._risk.check_buy(user_id, code, fused, shares, price, date,
                                          held_positions, prev_close=prev_close)
        if not ok:
            return Decision("hold", code, name, 0, price, reason=f"风控拦截: {reason}",
                            source="fusion", priority=0)

        sl, tp = self._compute_sl_tp(code, price, cfg)
        return Decision("buy", code, name, shares, price, stop_loss=sl, take_profit=tp,
                        reason=fused.reasons or [f"融合分 {fused.overall_score}"],
                        source="fusion", priority=30)

    def _decide_auction_candidate(self, cand: dict, fused, cash: float, user_id: str,
                                  date: str, held_positions: List[dict]) -> Decision:
        """竞价信号建仓：用竞价专用阈值，price 用 open_price（竞价价），source=auction_radar。"""
        from modules.pre_market_call_auction.config import AuctionConfig
        cfg = self._cfg()
        code = cand.get("code", cand.get("symbol", ""))
        name = cand.get("name", "") or fused.name
        price = cand.get("open_price") or fused.current_price or 0
        if price <= 0:
            return Decision("hold", code, name, 0, price, source="auction_radar", priority=0)

        score = cand.get("strength_score", 0) or fused.overall_score
        gap = cand.get("gap_pct", 0) or 0
        if score < AuctionConfig.AUTO_TRADE_MIN_SCORE or gap < AuctionConfig.AUTO_TRADE_MIN_GAP:
            return Decision("hold", code, name, 0, price,
                            reason=f"竞价信号未达标({score}/{gap}%)", source="auction_radar", priority=0)
        if cand.get("trap_warning"):
            return Decision("hold", code, name, 0, price, reason="竞价诱骗预警",
                            source="auction_radar", priority=0)

        shares = self._calc_buy_shares(cash, cfg.MAX_SINGLE_POSITION_PCT, price)
        if shares < 100:
            return Decision("hold", code, name, 0, price, reason="单票预算不足 100 股",
                            source="auction_radar", priority=0)

        prev_close = cand.get("prev_close")
        ok, reason = self._risk.check_buy(user_id, code, fused, shares, price, date,
                                          held_positions, prev_close=prev_close)
        if not ok:
            return Decision("hold", code, name, 0, price, reason=f"风控拦截: {reason}",
                            source="auction_radar", priority=0)

        # ATR SL/TP 用竞价专用倍数（日内策略）
        from modules.pre_market_call_auction.radar_utils import estimate_atr
        try:
            atr = estimate_atr(code, price)
        except Exception:
            atr = None
        if atr:
            sl = round(price - atr * AuctionConfig.AUTO_TRADE_SL_ATR, 2)
            tp = round(price + atr * AuctionConfig.AUTO_TRADE_TP_ATR, 2)
        else:
            sl = round(price * 0.98, 2)
            tp = round(price * 1.04, 2)
        return Decision("buy", code, name, shares, price, stop_loss=sl, take_profit=tp,
                        reason=cand.get("strategy", "gap_up_momentum"),
                        source="auction_radar", priority=30)

    # ── 辅助 ──────────────────────────────────────────────────────
    @staticmethod
    def _is_eod_close_time(cfg: AutoTradingConfig) -> bool:
        try:
            now = beijing_now()
            hh, mm = cfg.AUTO_CLOSE_TIME.split(":")
            close_h, close_m = int(hh), int(mm)
            return now.hour > close_h or (now.hour == close_h and now.minute >= close_m)
        except Exception:
            return False

    @staticmethod
    def _calc_buy_shares(cash: float, max_pct: float, price: float) -> int:
        if price <= 0:
            return 0
        qty = int(cash * max_pct / price)
        return max((qty // 100) * 100, 0)

    @staticmethod
    def _calc_add_shares(cash: float, max_pct: float, price: float) -> int:
        return DecisionEngine._calc_buy_shares(cash, max_pct, price)

    @staticmethod
    def _compute_sl_tp(code, price: float, cfg: AutoTradingConfig):
        """ATR 动态 SL/TP；取不到 ATR 时回退到固定百分比。"""
        try:
            from modules.pre_market_call_auction.radar_utils import estimate_atr
            atr = estimate_atr(code, price)
        except Exception:
            atr = None
        if atr:
            sl = round(price - atr * cfg.SL_ATR_MULTIPLIER, 2)
            tp = round(price + atr * cfg.TP_ATR_MULTIPLIER, 2)
        else:
            sl = round(price * (1 - 0.02), 2)
            tp = round(price * (1 + 0.04), 2)
        return sl, tp
