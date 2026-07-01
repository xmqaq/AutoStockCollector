import os
from dataclasses import dataclass, field


@dataclass
class AutoTradingConfig:
    # ── Signal weights ──
    # 四路融合：竞价 / PA / AI监控 / AI Agent(辩论verdict)。默认和=1.00。
    # PA/AI Monitor 盘中持续刷新权重最高；auction 盘前一次性、agent 每日两次刷新权重较低。
    # env 可覆盖（注意四路和需≈1.0±0.05，否则 ConfigStore 校验报 400）。
    AUCTION_WEIGHT: float = float(os.environ.get("AT_AUCTION_WEIGHT", "0.20"))
    PA_WEIGHT: float = float(os.environ.get("AT_PA_WEIGHT", "0.30"))
    AI_MONITOR_WEIGHT: float = float(os.environ.get("AT_AI_WEIGHT", "0.30"))
    AGENT_WEIGHT: float = float(os.environ.get("AT_AGENT_WEIGHT", "0.20"))

    # ── Decision thresholds (combined score 0-100) ──
    BUY_THRESHOLD: float = float(os.environ.get("AT_BUY_THRESHOLD", "70"))
    ADD_THRESHOLD: float = float(os.environ.get("AT_ADD_THRESHOLD", "75"))
    REDUCE_THRESHOLD: float = float(os.environ.get("AT_REDUCE_THRESHOLD", "40"))
    SELL_THRESHOLD: float = float(os.environ.get("AT_SELL_THRESHOLD", "25"))

    # ── Risk limits ──
    MAX_POSITIONS: int = int(os.environ.get("AT_MAX_POSITIONS", "8"))
    MAX_EXPOSURE_PCT: float = float(os.environ.get("AT_MAX_EXPOSURE", "0.80"))
    MAX_SINGLE_POSITION_PCT: float = float(os.environ.get("AT_MAX_SINGLE", "0.20"))
    MAX_SECTOR_EXPOSURE_PCT: float = float(os.environ.get("AT_MAX_SECTOR", "0.30"))

    # ── Universe filters (买入候选过滤) ──
    EXCLUDE_ST: bool = os.environ.get("AT_EXCLUDE_ST", "1") not in ("0", "false", "False")
    EXCLUDE_NEW_LISTING_DAYS: int = int(os.environ.get("AT_EXCLUDE_NEW_DAYS", "30"))
    LIMIT_UP_BLOCK: bool = os.environ.get("AT_BLOCK_LIMIT_UP", "1") not in ("0", "false", "False")
    LIMIT_DOWN_BLOCK: bool = os.environ.get("AT_BLOCK_LIMIT_DOWN", "1") not in ("0", "false", "False")

    # ── SL/TP multipliers ──
    SL_ATR_MULTIPLIER: float = float(os.environ.get("AT_SL_ATR", "1.5"))
    TP_ATR_MULTIPLIER: float = float(os.environ.get("AT_TP_ATR", "3.0"))

    # ── Timing ──
    SCAN_INTERVAL_MINUTES: int = int(os.environ.get("AT_SCAN_INTERVAL", "30"))
    AUTO_CLOSE_TIME: str = "14:50"
    MARKET_OPEN: str = "09:30"
    MARKET_CLOSE: str = "15:00"

    # ── Collection names ──
    SIGNAL_CACHE_COLLECTION: str = "auto_trading_signal_cache"
    LOG_COLLECTION: str = "auto_trading_log"
    CONFIG_COLLECTION: str = "auto_trading_config"

    # ── Signal fusion cache ──
    SIGNAL_CACHE_TTL_SECONDS: int = int(os.environ.get("AT_SIGNAL_CACHE_TTL", "120"))
    FUSION_WORKERS: int = int(os.environ.get("AT_FUSION_WORKERS", "4"))

    # ── Auction qualification ──
    MIN_AUCTION_SCORE: int = int(os.environ.get("AT_MIN_AUCTION_SCORE", "70"))
    MIN_AUCTION_GAP: float = float(os.environ.get("AT_MIN_GAP", "2.0"))

    # ── Agent signal qualification (候选池 agent 段过滤) ──
    MIN_AGENT_SCORE: int = int(os.environ.get("AT_MIN_AGENT_SCORE", "65"))

    # ── Loss-adjusted sell (亏损股卖出阈值上浮) ──
    LOSS_ADJ_SELL_BUMP: float = float(os.environ.get("AT_LOSS_ADJ_BUMP", "10"))
    LOSS_ADJ_TRIGGER_PCT: float = float(os.environ.get("AT_LOSS_ADJ_TRIGGER", "-8"))
