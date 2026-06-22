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

    FETCH_CONCURRENCY = int(os.getenv("AUCTION_FETCH_CONCURRENCY", "8"))
    FETCH_TIMEOUT = int(os.getenv("AUCTION_FETCH_TIMEOUT", "30"))

    STRENGTH_WEIGHT_GAP = float(os.getenv("AUCTION_WEIGHT_GAP", "0.40"))
    STRENGTH_WEIGHT_VOLUME = float(os.getenv("AUCTION_WEIGHT_VOLUME", "0.30"))
    STRENGTH_WEIGHT_SECTOR = float(os.getenv("AUCTION_WEIGHT_SECTOR", "0.20"))
    STRENGTH_WEIGHT_DEVIATION = float(os.getenv("AUCTION_WEIGHT_DEVIATION", "0.10"))

    STRENGTH_SCORE_HIGH = int(os.getenv("AUCTION_STRENGTH_HIGH", "80"))
    STRENGTH_SCORE_MEDIUM = int(os.getenv("AUCTION_STRENGTH_MEDIUM", "60"))

    TRAP_FALLBACK_THRESHOLD = float(os.getenv("AUCTION_TRAP_FALLBACK", "0.03"))
    TRAP_VOLUME_RATIO_MIN = float(os.getenv("AUCTION_TRAP_VOL_MIN", "0.3"))

    # ── Risk controls ──
    MAX_POSITIONS_PER_DAY = int(os.getenv("AUCTION_MAX_POSITIONS", "5"))       # 单日最多自动建仓数
    MAX_TOTAL_EXPOSURE_PCT = float(os.getenv("AUCTION_MAX_EXPOSURE", "0.80")) # 总仓位上限（占现金%）
    MAX_SECTOR_EXPOSURE_PCT = float(os.getenv("AUCTION_MAX_SECTOR", "0.30"))  # 单板块上限（占现金%）
