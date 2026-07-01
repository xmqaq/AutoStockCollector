"""盘前竞价雷达 — 配置。"""
import os


def _load_dotenv():
    dotenv_path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


class AuctionConfig:
    SCAN_TIME = os.getenv("AUCTION_SCAN_TIME", "09:25")
    TOP_N = int(os.getenv("AUCTION_TOP_N", "30"))
    SYMBOL_SOURCE = os.getenv("AUCTION_SYMBOL_SOURCE", "all")

    COLLECTION = "auction_snapshots"
    RESULT_COLLECTION = "auction_results"
    SIGNAL_COLLECTION = "auction_signals"  # 竞价信号 → auto_trading 消费

    FETCH_CONCURRENCY = int(os.getenv("AUCTION_FETCH_CONCURRENCY", "8"))
    FETCH_TIMEOUT = int(os.getenv("AUCTION_FETCH_TIMEOUT", "30"))

    # ── 8 维强度权重（和=1.0）──
    STRENGTH_WEIGHT_GAP = float(os.getenv("AUCTION_WEIGHT_GAP", "0.20"))
    STRENGTH_WEIGHT_VOLUME = float(os.getenv("AUCTION_WEIGHT_VOLUME", "0.15"))
    STRENGTH_WEIGHT_SECTOR = float(os.getenv("AUCTION_WEIGHT_SECTOR", "0.15"))
    STRENGTH_WEIGHT_DEVIATION = float(os.getenv("AUCTION_WEIGHT_DEVIATION", "0.10"))
    STRENGTH_WEIGHT_VOL_RATIO = float(os.getenv("AUCTION_WEIGHT_VOL_RATIO", "0.15"))
    STRENGTH_WEIGHT_ORDER_IMBALANCE = float(os.getenv("AUCTION_WEIGHT_IMBALANCE", "0.10"))
    STRENGTH_WEIGHT_AUCTION_TURNOVER = float(os.getenv("AUCTION_WEIGHT_TURNOVER", "0.10"))
    STRENGTH_WEIGHT_AMOUNT_PCTILE = float(os.getenv("AUCTION_WEIGHT_AMOUNT_PCT", "0.05"))

    STRENGTH_SCORE_HIGH = int(os.getenv("AUCTION_STRENGTH_HIGH", "80"))
    STRENGTH_SCORE_MEDIUM = int(os.getenv("AUCTION_STRENGTH_MEDIUM", "60"))

    # ── 诱骗检测 ──
    TRAP_FALLBACK_THRESHOLD = float(os.getenv("AUCTION_TRAP_FALLBACK", "0.03"))
    TRAP_VOLUME_RATIO_MIN = float(os.getenv("AUCTION_TRAP_VOL_MIN", "0.3"))
    TRAP_CANCEL_RATE_THRESHOLD = float(os.getenv("AUCTION_TRAP_CANCEL", "0.4"))   # 9:20 撤单率阈值
    TRAP_VOL_CONCENTRATION_TAIL = float(os.getenv("AUCTION_TRAP_VOL_TAIL", "0.3"))  # 尾段量集中度
    TRAP_SECTOR_RATE_THRESHOLD = float(os.getenv("AUCTION_TRAP_SECTOR", "0.4"))  # 板块诱多率阈值

    # ── Risk controls ──
    MAX_POSITIONS_PER_DAY = int(os.getenv("AUCTION_MAX_POSITIONS", "5"))       # 单日最多自动建仓数
    MAX_TOTAL_EXPOSURE_PCT = float(os.getenv("AUCTION_MAX_EXPOSURE", "0.80"))  # 总仓位上限（占现金%）
    MAX_SECTOR_EXPOSURE_PCT = float(os.getenv("AUCTION_MAX_SECTOR", "0.30"))   # 单板块上限（占现金%）

    # ── 日内自动交易参数（原 intraday_tracker 硬编码 → env 化，bug5）──
    AUTO_TRADE_ENABLED = os.getenv("AUCTION_AUTO_TRADE_ENABLED", "true").lower() not in ("0", "false", "False")
    AUTO_TRADE_MIN_SCORE = int(os.getenv("AUCTION_AUTO_TRADE_MIN_SCORE", "80"))
    AUTO_TRADE_MIN_GAP = float(os.getenv("AUCTION_AUTO_TRADE_MIN_GAP", "3.0"))
    AUTO_TRADE_MAX_POSITION_PCT = float(os.getenv("AUCTION_AUTO_TRADE_MAX_POS", "0.15"))
    AUTO_TRADE_SL_ATR = float(os.getenv("AUCTION_AUTO_TRADE_SL_ATR", "1.5"))
    AUTO_TRADE_TP_ATR = float(os.getenv("AUCTION_AUTO_TRADE_TP_ATR", "3.0"))

    # ── 盘中刷新 ──
    INTRADAY_REFRESH_INTERVAL_MIN = int(os.getenv("AUCTION_INTRADAY_REFRESH_MIN", "3"))

    # ── 二次采集（9:20 预筛，用于撤单率，默认关）──
    ENABLE_DUAL_SNAPSHOT = os.getenv("AUCTION_DUAL_SNAPSHOT", "false").lower() not in ("0", "false")
