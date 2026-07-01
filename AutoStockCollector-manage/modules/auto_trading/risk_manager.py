"""RiskManager — 买入/加仓/卖出前的风控检查，集中可单测。

检查项（check_buy 快速失败顺序，便宜→贵）：
  1. ST/退市  2. 次新股  3. 诱骗  4. 今日已交易  5. 涨跌停
  6. 持仓数上限  7. 单票上限  8. 板块集中度  9. 总敞口
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.database import DatabaseConfig
from modules.pre_market_call_auction.intraday_tracker import (
    _strip_prefix_from_code,
    _batch_tencent_quotes,
)
from utils.helpers import beijing_now, parse_stock_name
from utils.logger import get_logger

from .config import AutoTradingConfig
from .config_store import ConfigStore

logger = get_logger(__name__)

# 涨跌停幅度阈值（%）：主板 10%、创业板/科创 20%、北交所 30%（留 0.2% 误差）
_LIMIT_RANGES = {
    "main": 9.8,      # 60/00 开头
    "gem_star": 19.5, # 30/68 开头
    "bj": 29.5,       # 8/4 开头
}

_AUTO_TRADE_SOURCES = ["auto_trader", "auction_radar_auto"]


def _limit_threshold(code: str) -> float:
    bare = _strip_prefix_from_code(code).upper()
    if bare.startswith(("30", "68")):
        return _LIMIT_RANGES["gem_star"]
    if bare.startswith(("8", "4")):
        return _LIMIT_RANGES["bj"]
    return _LIMIT_RANGES["main"]


class RiskManager:
    def __init__(self, engine, account, config_store: ConfigStore):
        self._engine = engine
        self._account = account
        self._config_store = config_store

    def _cfg(self) -> AutoTradingConfig:
        return self._config_store.load()

    # ── 对外检查 ──────────────────────────────────────────────────
    def check_buy(self, user_id: str, code: str, fused, shares: int, price: float,
                  date: str, held_positions: List[Dict], prev_close: Optional[float] = None,
                  ) -> Tuple[bool, str]:
        """买入前综合检查。held_positions 为当前持仓 list（含 industry/market_value）。"""
        cfg = self._cfg()
        bare = _strip_prefix_from_code(code).upper()
        name = fused.name or ""

        # 1. ST / 退市
        if cfg.EXCLUDE_ST:
            ok, reason = self._check_st(name)
            if not ok:
                return False, reason

        # 2. 次新股
        if cfg.EXCLUDE_NEW_LISTING_DAYS > 0:
            ok, reason = self._check_new_listing(bare, cfg.EXCLUDE_NEW_LISTING_DAYS)
            if not ok:
                return False, reason

        # 3. 诱骗
        if fused.auction_trap:
            return False, "竞价诱骗预警"

        # 4. 今日已交易（防同日重复建仓）
        ok, reason = self._check_not_traded_today(user_id, bare, date)
        if not ok:
            return False, reason

        # 5. 涨跌停规避
        if cfg.LIMIT_UP_BLOCK or cfg.LIMIT_DOWN_BLOCK:
            ok, reason = self._check_limit(bare, price, prev_close, cfg)
            if not ok:
                return False, reason

        # 6. 持仓数上限（已持有的票加仓不占新名额）
        if bare not in {_strip_prefix_from_code(p.get("code", "")).upper() for p in held_positions}:
            if len(held_positions) >= cfg.MAX_POSITIONS:
                return False, f"持仓数已达上限 {cfg.MAX_POSITIONS}"

        # 7. 单票上限
        this_cost = shares * price
        cash = self._get_cash(user_id)
        if this_cost > cash * cfg.MAX_SINGLE_POSITION_PCT:
            return False, f"单票金额超上限 {cfg.MAX_SINGLE_POSITION_PCT*100:.0f}%"

        # 8. 板块集中度
        ok, reason = self._check_sector(bare, fused.industry, held_positions, this_cost, cash, cfg)
        if not ok:
            return False, reason

        # 9. 总敞口
        ok, reason = self._check_total_exposure(held_positions, this_cost, cash, cfg)
        if not ok:
            return False, reason

        return True, "ok"

    def check_add(self, user_id: str, code: str, fused, shares: int, price: float,
                  date: str, held_positions: List[Dict], prev_close: Optional[float] = None,
                  ) -> Tuple[bool, str]:
        """加仓检查：与 check_buy 一致，但跳过「今日已交易」（允许加仓）。"""
        cfg = self._cfg()
        bare = _strip_prefix_from_code(code).upper()
        name = fused.name or ""

        if cfg.EXCLUDE_ST:
            ok, reason = self._check_st(name)
            if not ok:
                return False, reason
        if cfg.LIMIT_UP_BLOCK or cfg.LIMIT_DOWN_BLOCK:
            ok, reason = self._check_limit(bare, price, prev_close, cfg)
            if not ok:
                return False, reason

        this_cost = shares * price
        cash = self._get_cash(user_id)

        # 加仓后该票总市值不超过单票上限的 1.5 倍（允许加仓但不无限加）
        pos = next((p for p in held_positions
                    if _strip_prefix_from_code(p.get("code", "")).upper() == bare), None)
        existing_mv = pos.get("market_value", 0) if pos else 0
        cap = cash * cfg.MAX_SINGLE_POSITION_PCT * 1.5
        if existing_mv + this_cost > cap:
            return False, "加仓后单票市值超限"

        ok, reason = self._check_total_exposure(held_positions, this_cost, cash, cfg)
        if not ok:
            return False, reason
        return True, "ok"

    def check_sell(self, code: str, price: float, prev_close: Optional[float]) -> Tuple[bool, str]:
        """卖出前检查：跌停拒卖（卖不掉）。涨停可卖。"""
        cfg = self._cfg()
        if not cfg.LIMIT_DOWN_BLOCK or price <= 0 or not prev_close or prev_close <= 0:
            return True, "ok"
        change_pct = (price - prev_close) / prev_close * 100
        if change_pct <= -_limit_threshold(code):
            return False, "跌停无法卖出"
        return True, "ok"

    # ── 单项检查（可单测） ────────────────────────────────────────
    def _check_st(self, name: str) -> Tuple[bool, str]:
        parsed = parse_stock_name(name or "")
        if parsed.get("is_st"):
            return False, "ST 股票"
        if parsed.get("is_pt"):
            return False, "PT 股票"
        if parsed.get("is_delisted"):
            return False, "退市股票"
        return True, "ok"

    def _check_new_listing(self, bare_code: str, min_days: int) -> Tuple[bool, str]:
        """次新股：kline 最早一条 date 距今不足 min_days 个日历日 → 拒。"""
        try:
            db = DatabaseConfig.get_database()
            doc = db["kline"].find_one(
                {"code": bare_code}, sort=[("date", 1)], projection={"date": 1, "_id": 0},
            )
            if not doc or not doc.get("date"):
                return True, "ok"  # 无 kline 数据不拦（交给上游判断）
            first = str(doc["date"])[:10]
            first_dt = datetime.strptime(first, "%Y-%m-%d")
            if (beijing_now() - first_dt).days < min_days:
                return False, f"次新股（上市不足 {min_days} 天）"
        except Exception as e:
            logger.warning(f"[risk] new-listing check failed {bare_code}: {e}")
        return True, "ok"

    def _check_not_traded_today(self, user_id: str, bare_code: str, date: str) -> Tuple[bool, str]:
        """修复 bug 4：查 source in [auto_trader, auction_radar_auto]，不再只查 auction_radar_auto。
        代码格式不统一（SH600000/600000.SH/600000），故先按 user_id+date+source 拉，再本地比对。"""
        try:
            db = DatabaseConfig.get_database()
            start = f"{date}T00:00:00"
            end = f"{date}T23:59:59"
            docs = db["trade_records"].find(
                {"user_id": user_id, "action": "buy",
                 "traded_at": {"$gte": start, "$lte": end},
                 "ai_signal.source": {"$in": _AUTO_TRADE_SOURCES}},
                {"code": 1, "_id": 0},
            )
            for d in docs:
                if _strip_prefix_from_code(d.get("code", "")).upper() == bare_code:
                    return False, "今日已自动建仓"
        except Exception as e:
            logger.warning(f"[risk] traded-today check failed {bare_code}: {e}")
        return True, "ok"

    def _check_limit(self, bare_code: str, price: float, prev_close: Optional[float],
                     cfg: AutoTradingConfig) -> Tuple[bool, str]:
        if price <= 0:
            return True, "ok"
        # prev_close 由调用方提供；缺失时从行情批量接口取（需带前缀）
        if not prev_close or prev_close <= 0:
            prev_close = self._fetch_prev_close(bare_code)
        if not prev_close or prev_close <= 0:
            return True, "ok"  # 取不到昨收不拦
        change_pct = (price - prev_close) / prev_close * 100
        threshold = _limit_threshold(bare_code)
        if cfg.LIMIT_UP_BLOCK and change_pct >= threshold:
            return False, f"涨停（+{change_pct:.1f}%）无法买入"
        if cfg.LIMIT_DOWN_BLOCK and change_pct <= -threshold:
            return False, f"跌停（{change_pct:.1f}%）不买入"
        return True, "ok"

    def _check_sector(self, bare_code: str, industry: str, held_positions: List[Dict],
                      this_cost: float, cash: float, cfg: AutoTradingConfig) -> Tuple[bool, str]:
        if not industry:
            return True, "ok"
        sector_used = sum(
            p.get("market_value", 0) for p in held_positions
            if p.get("industry") == industry
        )
        total = sector_used + this_cost
        cap = cash * cfg.MAX_SECTOR_EXPOSURE_PCT
        if total > cap:
            return False, f"板块「{industry}」集中度超限 {cfg.MAX_SECTOR_EXPOSURE_PCT*100:.0f}%"
        return True, "ok"

    def _check_total_exposure(self, held_positions: List[Dict], this_cost: float,
                              cash: float, cfg: AutoTradingConfig) -> Tuple[bool, str]:
        held_mv = sum(p.get("market_value", 0) for p in held_positions)
        total_assets = held_mv + cash
        if total_assets <= 0:
            return True, "ok"
        exposure_after = (held_mv + this_cost) / total_assets
        if exposure_after > cfg.MAX_EXPOSURE_PCT:
            return False, f"总敞口超限 {cfg.MAX_EXPOSURE_PCT*100:.0f}%"
        return True, "ok"

    # ── 辅助 ──────────────────────────────────────────────────────
    def _get_cash(self, user_id: str) -> float:
        try:
            doc = self._account.get(user_id)
            return doc.get("cash_balance", 0) if doc else 0
        except Exception:
            return 0.0

    def _fetch_prev_close(self, bare_code: str) -> Optional[float]:
        """从 kline 取最近一条 close 作为昨收。"""
        try:
            db = DatabaseConfig.get_database()
            doc = db["kline"].find_one(
                {"code": bare_code}, sort=[("date", -1)], projection={"close": 1, "_id": 0},
            )
            if doc and doc.get("close"):
                return float(doc["close"])
        except Exception:
            pass
        return None

    def check_not_reduced_today(self, user_id: str, code: str, date: str) -> Tuple[bool, str]:
        """今日是否已对该票做过自动减仓/卖出（防每轮重复减仓直到清仓）。
        code 可带前缀（SH/SZ/BJ）也可裸代码，内部统一 strip。"""
        bare = _strip_prefix_from_code(code).upper()
        try:
            db = DatabaseConfig.get_database()
            start = f"{date}T00:00:00"
            end = f"{date}T23:59:59"
            docs = db["trade_records"].find(
                {"user_id": user_id, "action": "sell",
                 "traded_at": {"$gte": start, "$lte": end},
                 "ai_signal.source": {"$in": _AUTO_TRADE_SOURCES}},
                {"code": 1, "_id": 0},
            )
            for d in docs:
                if _strip_prefix_from_code(d.get("code", "")).upper() == bare:
                    return False, "今日已自动减仓/卖出"
        except Exception as e:
            logger.warning(f"[risk] reduced-today check failed {bare}: {e}")
        return True, "ok"

    @staticmethod
    def normalize_for_trade(code: str) -> str:
        """裸代码 → 带交易所前缀（SH/SZ/BJ）。"""
        stripped = _strip_prefix_from_code(code).upper()
        if stripped.startswith("6"):
            return f"SH{stripped}"
        if stripped.startswith(("0", "3")):
            return f"SZ{stripped}"
        if stripped.startswith(("8", "4")):
            return f"BJ{stripped}"
        return stripped
