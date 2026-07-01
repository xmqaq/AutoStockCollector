"""SignalFusionEngine — 融合「盘前竞价雷达 + 价格行为学(PA) + AI 实时监控」三路信号。

修复点：
- 分母归一化：缺失数据源不参与分母，等价于在「有数据的源」之间按权重加权平均。
- 缓存：同一 code+date 的 fuse 结果 TTL 缓存，避免 run_cycle 中持仓/候选阶段重复算 PA。
- batch_fuse 并行：ThreadPoolExecutor 并发调 PA（PA 为 I/O 密集，线程安全）。
"""
import copy
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from config.database import DatabaseConfig
from modules.price_action_advisor.price_action_engine import PriceActionEngine
from utils.helpers import beijing_now
from utils.logger import get_logger

from .config import AutoTradingConfig
from .config_store import ConfigStore

logger = get_logger(__name__)


class FusedSignal:
    def __init__(self, code: str, name: str = ""):
        self.code: str = code
        self.name: str = name
        self.overall_score: float = 50.0
        self.signal: str = "hold"
        self.industry: str = ""
        self.current_price: float = 0.0

        self.auction_score: float = 0.0
        self.auction_gap: float = 0.0
        self.auction_trap: bool = False

        self.pa_signal: str = "NO_DATA"
        self.pa_confidence: int = 0
        self.pa_trade_plan: Optional[Dict] = None

        self.ai_score: float = 50.0
        self.ai_signal: str = "hold"

        # 第 4 路：AI Agent（TradingGraph 多空辩论 verdict）
        self.agent_score: float = 0.0
        self.agent_signal: str = "hold"

        self.reasons: List[str] = []


PA_SIGNAL_SCORES = {
    "BUY_SETUP": 95, "WEAK_BUY": 70, "NEUTRAL": 50,
    "WEAK_SELL": 30, "SELL_SETUP": 5, "NO_DATA": 50, "NO_TRADE": 50,
}
PA_CONFIDENCE_MAX = 5


class SignalFusionEngine:
    def __init__(self, config_store: Optional[ConfigStore] = None):
        self._config_store = config_store or ConfigStore()
        self._pa_engine = PriceActionEngine()
        self._cache: Dict[str, Tuple[FusedSignal, float]] = {}
        self._cache_lock = __import__("threading").Lock()

    def _cfg(self) -> AutoTradingConfig:
        return self._config_store.load()

    # ── 融合 ──────────────────────────────────────────────────────
    def fuse(self, code: str, date: str, name: str = "", use_cache: bool = True) -> FusedSignal:
        key = f"{code.upper()}:{date}"
        cfg = self._cfg()
        if use_cache:
            cached = self._cache_get(key, cfg.SIGNAL_CACHE_TTL_SECONDS)
            if cached is not None:
                return copy.deepcopy(cached)

        fused = FusedSignal(code, name)
        self._merge_auction(fused, date)
        self._merge_pa(fused)
        self._merge_ai_monitor(fused, date)
        self._merge_agent(fused, date)
        self._compute_overall(fused, cfg)
        self._build_reasons(fused, cfg)

        if use_cache:
            self._cache_set(key, fused)
        return fused

    def _compute_overall(self, fused: FusedSignal, cfg: AutoTradingConfig):
        """分母 = 仅有数据的源的权重之和；分子 = 各源加权得分(0-1)。缺失源不参与。"""
        w_a, w_p, w_m, w_g = (cfg.AUCTION_WEIGHT, cfg.PA_WEIGHT,
                              cfg.AI_MONITOR_WEIGHT, cfg.AGENT_WEIGHT)

        norm_a: Optional[float] = (w_a * fused.auction_score / 100.0) if fused.auction_score > 0 else None
        pa_raw = PA_SIGNAL_SCORES.get(fused.pa_signal, 50)
        pa_conf = fused.pa_confidence / PA_CONFIDENCE_MAX if fused.pa_confidence > 0 else 0.5
        norm_p: Optional[float] = (w_p * pa_raw / 100.0 * pa_conf) if fused.pa_signal != "NO_DATA" else None
        norm_m: Optional[float] = (w_m * fused.ai_score / 100.0) if fused.ai_score > 0 else None
        # agent 信号必须 >0 才参与（0 表示无当日信号/被过期过滤）
        norm_g: Optional[float] = (w_g * fused.agent_score / 100.0) if fused.agent_score > 0 else None

        terms = [(w, v) for w, v in ((w_a, norm_a), (w_p, norm_p), (w_m, norm_m), (w_g, norm_g)) if v is not None]
        active_weights = sum(w for w, _ in terms)
        if active_weights <= 0:
            fused.overall_score = 50.0
            fused.signal = "hold"
            return

        numerator = sum(v for _, v in terms)
        fused.overall_score = round(max(0.0, min(100.0, numerator / active_weights * 100)), 1)
        fused.signal = self._score_to_signal(fused.overall_score, cfg)

    def _score_to_signal(self, score: float, cfg: AutoTradingConfig) -> str:
        if score >= cfg.ADD_THRESHOLD:
            return "strong_buy"
        if score >= cfg.BUY_THRESHOLD:
            return "buy"
        if score >= cfg.REDUCE_THRESHOLD:
            return "hold"
        if score >= cfg.SELL_THRESHOLD:
            return "sell"
        return "strong_sell"

    def _build_reasons(self, fused: FusedSignal, cfg: AutoTradingConfig):
        reasons: List[str] = []
        if fused.auction_score >= cfg.MIN_AUCTION_SCORE:
            reasons.append(f"竞价雷达 {fused.auction_score}分")
        if fused.auction_trap:
            reasons.append("诱骗预警")
        if fused.pa_signal in ("BUY_SETUP", "WEAK_BUY"):
            reasons.append(f"价格行为 {fused.pa_signal}")
        if fused.pa_signal in ("SELL_SETUP", "WEAK_SELL"):
            reasons.append(f"PA看空 {fused.pa_signal}")
        if fused.ai_score >= 72:
            reasons.append(f"AI监控 {fused.ai_score}分")
        if fused.ai_score <= 30:
            reasons.append(f"AI看空 {fused.ai_score}分")
        if fused.agent_score >= 72:
            reasons.append(f"AI Agent {fused.agent_score}分")
        if fused.agent_score <= 30:
            reasons.append(f"Agent看空 {fused.agent_score}分")
        fused.reasons = reasons

    # ── 三路合并 ──────────────────────────────────────────────────
    def _merge_auction(self, fused: FusedSignal, date: str):
        try:
            db = DatabaseConfig.get_database()
            result = db["auction_results"].find_one(
                {"date": date}, sort=[("created_at", -1)]
            )
            if not result:
                return
            top = result.get("top_stocks", []) or []
            symbol = fused.code.upper()
            for s in top:
                s_sym = s.get("symbol", "").upper()
                # 兼容 SH600000 / 600000.SH / 600000 等格式
                s_bare = (s_sym.split(".")[-1]
                          .replace("SH", "").replace("SZ", "").replace("BJ", ""))
                sym_bare = symbol.replace("SH", "").replace("SZ", "").replace("BJ", "")
                if s_bare == sym_bare:
                    fused.auction_score = s.get("strength_score", 0)
                    fused.auction_gap = s.get("gap_pct", 0.0)
                    trap = s.get("trap_warning", {}) or {}
                    fused.auction_trap = trap.get("is_trap", False)
                    fused.industry = s.get("industry", "") or fused.industry
                    if s.get("name"):
                        fused.name = s.get("name")
                    break
        except Exception as e:
            logger.warning(f"[fusion] auction radar fetch failed: {e}")

    def _merge_pa(self, fused: FusedSignal):
        try:
            result = self._pa_engine.analyze(fused.code, timeframe="daily")
            fused.pa_signal = result.get("signal", "NO_DATA")
            fused.pa_confidence = result.get("confidence", 0)
            fused.pa_trade_plan = result.get("trade_plan")
            price = result.get("current_price") or result.get("entry_price", 0)
            if price:
                fused.current_price = price
            if not fused.name:
                fused.name = result.get("name", result.get("symbol", "")) or fused.name
        except Exception as e:
            logger.warning(f"[fusion] PA analysis failed for {fused.code}: {e}")

    def _merge_ai_monitor(self, fused: FusedSignal, date: str):
        try:
            db = DatabaseConfig.get_database()
            # 带 signal_date 过滤：隔夜/缺当日监控分不参与融合（与 _merge_agent 对齐）。
            # ai_monitor 当日未刷新时返回 None，ai_score 保持默认 50 不进分母，避免用旧分。
            doc = db["monitor_signal_history"].find_one(
                {"code": fused.code, "signal_date": date},
                sort=[("updated_at", -1)],
            )
            if not doc:
                return
            comp = doc.get("composite", {}) or {}
            fused.ai_score = comp.get("score", 50)
            fused.ai_signal = comp.get("signal", "hold")
            if not fused.current_price:
                fused.current_price = doc.get("price", 0) or fused.current_price
            if not fused.name:
                fused.name = doc.get("name", "") or fused.name
            if not fused.industry:
                fused.industry = doc.get("industry", "") or fused.industry
        except Exception as e:
            logger.warning(f"[fusion] AI monitor fetch failed: {e}")

    def _merge_agent(self, fused: FusedSignal, date: str):
        """第 4 路：AI Agent 信号（TradingGraph 多空辩论 verdict）。

        带 trade_date 过滤：隔夜/缺当日信号的 code 返回 None，agent_score 保持 0.0，
        不参与融合分母。与 _merge_ai_monitor 的 signal_date 过滤一致，避免用旧信号
        误导盘中决策。
        """
        try:
            db = DatabaseConfig.get_database()
            doc = db["agent_signals"].find_one(
                {"code": fused.code, "trade_date": date},
                sort=[("updated_at", -1)],
            )
            if not doc:
                return
            fused.agent_score = doc.get("agent_score", 0) or 0
            fused.agent_signal = doc.get("agent_signal", "hold")
            if not fused.current_price:
                fused.current_price = doc.get("price", 0) or fused.current_price
            if not fused.name:
                fused.name = doc.get("name", "") or fused.name
            if not fused.industry:
                fused.industry = doc.get("industry", "") or fused.industry
        except Exception as e:
            logger.warning(f"[fusion] Agent signal fetch failed for {fused.code}: {e}")

    # ── 批量（并行） ──────────────────────────────────────────────
    def batch_fuse(self, codes: List[Dict[str, str]], date: str,
                   use_cache: bool = True) -> List[FusedSignal]:
        if not codes:
            return []
        cfg = self._cfg()
        workers = max(1, min(cfg.FUSION_WORKERS, 16))

        def _do(item: Dict[str, str]) -> FusedSignal:
            code = item.get("code", item.get("symbol", ""))
            name = item.get("name", "")
            return self.fuse(code, date, name=name, use_cache=use_cache)

        results: List[FusedSignal] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fused in pool.map(_do, codes):
                if fused is not None:
                    results.append(fused)
        results.sort(key=lambda x: x.overall_score, reverse=True)
        return results

    # ── 缓存 ──────────────────────────────────────────────────────
    def _cache_get(self, key: str, ttl: int) -> Optional[FusedSignal]:
        with self._cache_lock:
            item = self._cache.get(key)
            if item and (time.monotonic() - item[1]) < ttl:
                return item[0]
            if item:
                self._cache.pop(key, None)
            return None

    def _cache_set(self, key: str, fused: FusedSignal):
        with self._cache_lock:
            self._cache[key] = (fused, time.monotonic())

    def clear_cache(self):
        with self._cache_lock:
            self._cache.clear()
