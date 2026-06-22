import os
from pathlib import Path


def _load_dotenv():
    dotenv_path = Path(__file__).parent.parent.parent / ".env"
    if dotenv_path.exists():
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


class PAConfig:
    # Cache TTL
    CACHE_TTL_SPOT = int(os.getenv("PA_CACHE_TTL_SPOT", "60"))
    CACHE_TTL_KLINE_DAY = int(os.getenv("PA_CACHE_TTL_KLINE_DAY", "3600"))
    CACHE_TTL_KLINE_MIN = int(os.getenv("PA_CACHE_TTL_KLINE_MIN", "1800"))
    CACHE_COLLECTION = "pa_quotes_cache"
    RESULTS_COLLECTION = "pa_signals"

    # Fetch concurrency & rate limit
    FETCH_CONCURRENCY = int(os.getenv("PA_FETCH_CONCURRENCY", "4"))
    FETCH_INTERVAL = float(os.getenv("PA_FETCH_INTERVAL", "3.0"))
    FETCH_RETRY_MAX = int(os.getenv("PA_FETCH_RETRY_MAX", "2"))
    FETCH_TIMEOUT = int(os.getenv("PA_FETCH_TIMEOUT", "30"))

    # Defaults
    DEFAULT_TIMEFRAME = os.getenv("PA_DEFAULT_TIMEFRAME", "daily")
    DEFAULT_RISK_PCT = float(os.getenv("PA_DEFAULT_RISK_PCT", "0.02"))
    DEFAULT_ACCOUNT_BALANCE = float(os.getenv("PA_DEFAULT_ACCOUNT_BALANCE", "100000"))

    # Kline
    KLINE_DAYS = int(os.getenv("PA_KLINE_DAYS", "120"))
    MIN_KLINE_BARS = int(os.getenv("PA_MIN_KLINE_BARS", "30"))

    # ========== 可调阈值 ==========

    # 风险 (risk_manager.py)
    ATR_STOP_MULTIPLIER = float(os.getenv("PA_ATR_STOP_MULTIPLIER", "1.5"))
    PCT_STOP_MIN = float(os.getenv("PA_PCT_STOP_MIN", "0.015"))
    REWARD_MULTIPLIER = float(os.getenv("PA_REWARD_MULTIPLIER", "2.0"))
    RISK_FALLBACK_PCT = float(os.getenv("PA_RISK_FALLBACK_PCT", "0.02"))

    # 弱信号风控减半 (price_action_engine.py)
    WEAK_SIGNAL_RISK_FACTOR = float(os.getenv("PA_WEAK_SIGNAL_RISK_FACTOR", "0.5"))

    # 市场结构 (market_structure.py)
    PIVOT_LEFT = int(os.getenv("PA_PIVOT_LEFT", "2"))
    PIVOT_RIGHT = int(os.getenv("PA_PIVOT_RIGHT", "2"))
    STRUCTURE_HH_THRESHOLD = float(os.getenv("PA_STRUCTURE_HH_THRESHOLD", "1.005"))
    STRUCTURE_LL_THRESHOLD = float(os.getenv("PA_STRUCTURE_LL_THRESHOLD", "0.995"))
    SMA_BULL_THRESHOLD = float(os.getenv("PA_SMA_BULL_THRESHOLD", "1.02"))
    SMA_BEAR_THRESHOLD = float(os.getenv("PA_SMA_BEAR_THRESHOLD", "0.98"))
    LAST_SWING_WINDOW = int(os.getenv("PA_LAST_SWING_WINDOW", "3"))

    # 供需区 (supply_demand.py)
    ATR_PERIOD = int(os.getenv("PA_ATR_PERIOD", "14"))
    CONSOLIDATION_LOOKBACK = int(os.getenv("PA_CONSOLIDATION_LOOKBACK", "30"))
    CONSOLIDATION_WINDOW = int(os.getenv("PA_CONSOLIDATION_WINDOW", "5"))
    CONSOLIDATION_BODY_RATIO = float(os.getenv("PA_CONSOLIDATION_BODY_RATIO", "0.4"))
    ZONE_MERGE_THRESHOLD = float(os.getenv("PA_ZONE_MERGE_THRESHOLD", "0.02"))
    ZONE_STRENGTH_MULTIPLIER = int(os.getenv("PA_ZONE_STRENGTH_MULTIPLIER", "2"))
    ZONE_TEST_BARS = int(os.getenv("PA_ZONE_TEST_BARS", "10"))
    ZONE_TEST_MIN_COUNT = int(os.getenv("PA_ZONE_TEST_MIN_COUNT", "2"))

    ORDER_BLOCK_LOOKBACK = int(os.getenv("PA_ORDER_BLOCK_LOOKBACK", "30"))
    ORDER_BLOCK_MIN_BODY_ATR = float(os.getenv("PA_ORDER_BLOCK_MIN_BODY_ATR", "0.5"))
    ORDER_BLOCK_MAX_RESULTS = int(os.getenv("PA_ORDER_BLOCK_MAX_RESULTS", "5"))

    SWEEP_LOOKBACK = int(os.getenv("PA_SWEEP_LOOKBACK", "20"))
    SWEEP_THRESHOLD = float(os.getenv("PA_SWEEP_THRESHOLD", "0.01"))

    # 信号生成 (signal_generator.py)
    ZONE_PROXIMITY = float(os.getenv("PA_ZONE_PROXIMITY", "0.02"))
    FIB_PROXIMITY = float(os.getenv("PA_FIB_PROXIMITY", "0.02"))
    OB_PROXIMITY = float(os.getenv("PA_OB_PROXIMITY", "0.01"))

    # AI 分析 (ai_analyzer.py)
    AI_TEMPERATURE = float(os.getenv("PA_AI_TEMPERATURE", "0.5"))
    AI_MAX_TOKENS = int(os.getenv("PA_AI_MAX_TOKENS", "500"))
