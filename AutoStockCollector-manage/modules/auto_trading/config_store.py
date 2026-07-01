"""ConfigStore — auto-trading 配置的 MongoDB 持久化层。

单文档（_id="singleton"）存储全部可调参数；环境变量仅作为「无 DB 文档时」的初始默认。
GET/POST /api/v1/auto-trading/config 通过本类读写，使配置可在运行时修改。
"""
from dataclasses import asdict
from typing import Any, Dict

from config.database import DatabaseConfig
from utils.helpers import beijing_now
from utils.logger import get_logger

from .config import AutoTradingConfig

logger = get_logger(__name__)

_DOC_ID = "singleton"


class ConfigStore:
    """加载/保存 AutoTradingConfig，DB 文档优先于环境变量默认值。"""

    def _col(self):
        return DatabaseConfig.get_database()[AutoTradingConfig.CONFIG_COLLECTION]

    # ── 加载 ──────────────────────────────────────────────────────
    def load(self) -> AutoTradingConfig:
        """返回一个独立 AutoTradingConfig 实例：DB 文档覆盖 env 默认值。无文档时返回 env 默认。"""
        cfg = AutoTradingConfig()  # 读环境变量作为默认
        try:
            doc = self._col().find_one({"_id": _DOC_ID})
            if doc:
                self._merge_doc_into_cfg(doc, cfg)
        except Exception as e:
            logger.warning(f"[config-store] load failed, using env defaults: {e}")
        return cfg

    @staticmethod
    def _merge_doc_into_cfg(doc: Dict[str, Any], cfg: AutoTradingConfig):
        """把 DB 文档的各 section 合并进 cfg 实例（字段名映射）。"""
        w = doc.get("weights", {}) or {}
        if "auction" in w:
            cfg.AUCTION_WEIGHT = float(w["auction"])
        if "pa" in w:
            cfg.PA_WEIGHT = float(w["pa"])
        if "ai_monitor" in w:
            cfg.AI_MONITOR_WEIGHT = float(w["ai_monitor"])
        if "agent" in w:
            cfg.AGENT_WEIGHT = float(w["agent"])

        t = doc.get("thresholds", {}) or {}
        for k, attr in (("buy", "BUY_THRESHOLD"), ("add", "ADD_THRESHOLD"),
                        ("reduce", "REDUCE_THRESHOLD"), ("sell", "SELL_THRESHOLD")):
            if k in t:
                setattr(cfg, attr, float(t[k]))

        r = doc.get("risk", {}) or {}
        for k, attr in (("max_positions", "MAX_POSITIONS"), ("max_exposure_pct", "MAX_EXPOSURE_PCT"),
                        ("max_single_pct", "MAX_SINGLE_POSITION_PCT"),
                        ("max_sector_pct", "MAX_SECTOR_EXPOSURE_PCT")):
            if k in r:
                setattr(cfg, attr, float(r[k]) if attr != "MAX_POSITIONS" else int(r[k]))
        if "exclude_st" in r:
            cfg.EXCLUDE_ST = bool(r["exclude_st"])
        if "exclude_new_listing_days" in r:
            cfg.EXCLUDE_NEW_LISTING_DAYS = int(r["exclude_new_listing_days"])
        if "limit_up_block" in r:
            cfg.LIMIT_UP_BLOCK = bool(r["limit_up_block"])
        if "limit_down_block" in r:
            cfg.LIMIT_DOWN_BLOCK = bool(r["limit_down_block"])

        s = doc.get("sl_tp", {}) or {}
        if "sl_atr_multiplier" in s:
            cfg.SL_ATR_MULTIPLIER = float(s["sl_atr_multiplier"])
        if "tp_atr_multiplier" in s:
            cfg.TP_ATR_MULTIPLIER = float(s["tp_atr_multiplier"])

        tm = doc.get("timing", {}) or {}
        if "scan_interval_minutes" in tm:
            cfg.SCAN_INTERVAL_MINUTES = int(tm["scan_interval_minutes"])
        if "auto_close_time" in tm:
            cfg.AUTO_CLOSE_TIME = str(tm["auto_close_time"])

        aq = doc.get("auction_qual", {}) or {}
        if "min_auction_score" in aq:
            cfg.MIN_AUCTION_SCORE = int(aq["min_auction_score"])
        if "min_auction_gap" in aq:
            cfg.MIN_AUCTION_GAP = float(aq["min_auction_gap"])

        gq = doc.get("agent_qual", {}) or {}
        if "min_agent_score" in gq:
            cfg.MIN_AGENT_SCORE = int(gq["min_agent_score"])

        cc = doc.get("cache", {}) or {}
        if "signal_cache_ttl_seconds" in cc:
            cfg.SIGNAL_CACHE_TTL_SECONDS = int(cc["signal_cache_ttl_seconds"])
        if "fusion_workers" in cc:
            cfg.FUSION_WORKERS = int(cc["fusion_workers"])

    # ── 序列化 ────────────────────────────────────────────────────
    def to_dict(self, cfg: AutoTradingConfig) -> Dict[str, Any]:
        return {
            "_id": _DOC_ID,
            "weights": {
                "auction": cfg.AUCTION_WEIGHT,
                "pa": cfg.PA_WEIGHT,
                "ai_monitor": cfg.AI_MONITOR_WEIGHT,
                "agent": cfg.AGENT_WEIGHT,
            },
            "thresholds": {
                "buy": cfg.BUY_THRESHOLD,
                "add": cfg.ADD_THRESHOLD,
                "reduce": cfg.REDUCE_THRESHOLD,
                "sell": cfg.SELL_THRESHOLD,
            },
            "risk": {
                "max_positions": cfg.MAX_POSITIONS,
                "max_exposure_pct": cfg.MAX_EXPOSURE_PCT,
                "max_single_pct": cfg.MAX_SINGLE_POSITION_PCT,
                "max_sector_pct": cfg.MAX_SECTOR_EXPOSURE_PCT,
                "exclude_st": cfg.EXCLUDE_ST,
                "exclude_new_listing_days": cfg.EXCLUDE_NEW_LISTING_DAYS,
                "limit_up_block": cfg.LIMIT_UP_BLOCK,
                "limit_down_block": cfg.LIMIT_DOWN_BLOCK,
            },
            "sl_tp": {
                "sl_atr_multiplier": cfg.SL_ATR_MULTIPLIER,
                "tp_atr_multiplier": cfg.TP_ATR_MULTIPLIER,
            },
            "timing": {
                "scan_interval_minutes": cfg.SCAN_INTERVAL_MINUTES,
                "auto_close_time": cfg.AUTO_CLOSE_TIME,
            },
            "auction_qual": {
                "min_auction_score": cfg.MIN_AUCTION_SCORE,
                "min_auction_gap": cfg.MIN_AUCTION_GAP,
            },
            "agent_qual": {
                "min_agent_score": cfg.MIN_AGENT_SCORE,
            },
            "cache": {
                "signal_cache_ttl_seconds": cfg.SIGNAL_CACHE_TTL_SECONDS,
                "fusion_workers": cfg.FUSION_WORKERS,
            },
            "updated_at": beijing_now().isoformat(),
        }

    def from_dict(self, d: Dict[str, Any]) -> AutoTradingConfig:
        """从部分 dict 构造 cfg（用于 POST 校验）；缺失字段用 env 默认补齐。"""
        cfg = AutoTradingConfig()
        merged = self.to_dict(cfg)  # 完整默认
        # 逐 section 浅合并用户输入
        for section in ("weights", "thresholds", "risk", "sl_tp", "timing",
                        "auction_qual", "agent_qual", "cache"):
            if isinstance(d.get(section), dict):
                merged[section] = {**merged[section], **d[section]}
        cfg2 = AutoTradingConfig()
        self._merge_doc_into_cfg(merged, cfg2)
        return cfg2

    # ── 保存 ──────────────────────────────────────────────────────
    def save(self, updates: Dict[str, Any]) -> AutoTradingConfig:
        """部分更新：load 当前 → merge updates → 校验 → 整体 upsert。返回更新后的 cfg。"""
        cfg = self.from_dict(updates)  # 已含校验（from_dict 走 float/int 转换，非法抛 ValueError）
        self._validate(cfg)
        doc = self.to_dict(cfg)
        try:
            self._col().replace_one({"_id": _DOC_ID}, doc, upsert=True)
            logger.info(f"[config-store] saved config: weights={doc['weights']} risk={doc['risk']}")
        except Exception as e:
            logger.error(f"[config-store] save failed: {e}")
            raise
        return cfg

    @staticmethod
    def _validate(cfg: AutoTradingConfig):
        """业务范围校验；不合法抛 ValueError，由 API 层转 400。"""
        if not (1 <= cfg.MAX_POSITIONS <= 50):
            raise ValueError(f"max_positions 必须在 1-50 之间（当前 {cfg.MAX_POSITIONS}）")
        wsum = cfg.AUCTION_WEIGHT + cfg.PA_WEIGHT + cfg.AI_MONITOR_WEIGHT + cfg.AGENT_WEIGHT
        if abs(wsum - 1.0) > 0.05:
            raise ValueError(f"四路权重之和应≈1.0（当前 {wsum:.3f}）")
        for name, val in (("BUY_THRESHOLD", cfg.BUY_THRESHOLD), ("ADD_THRESHOLD", cfg.ADD_THRESHOLD),
                          ("REDUCE_THRESHOLD", cfg.REDUCE_THRESHOLD), ("SELL_THRESHOLD", cfg.SELL_THRESHOLD)):
            if not (0 <= val <= 100):
                raise ValueError(f"{name} 必须在 0-100 之间（当前 {val}）")
        if not (0 < cfg.MAX_EXPOSURE_PCT <= 1.0):
            raise ValueError(f"max_exposure_pct 必须在 (0,1] 之间（当前 {cfg.MAX_EXPOSURE_PCT}）")
        if not (0 < cfg.MAX_SINGLE_POSITION_PCT <= 1.0):
            raise ValueError(f"max_single_pct 必须在 (0,1] 之间（当前 {cfg.MAX_SINGLE_POSITION_PCT}）")
        if not (0 < cfg.MAX_SECTOR_EXPOSURE_PCT <= 1.0):
            raise ValueError(f"max_sector_pct 必须在 (0,1] 之间（当前 {cfg.MAX_SECTOR_EXPOSURE_PCT}）")

    def reset(self) -> AutoTradingConfig:
        """删除 DB 文档，回到环境变量默认。"""
        try:
            self._col().delete_one({"_id": _DOC_ID})
            logger.info("[config-store] config reset to env defaults")
        except Exception as e:
            logger.warning(f"[config-store] reset failed: {e}")
        return AutoTradingConfig()
