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
    CACHE_TTL_SPOT = int(os.getenv("PA_CACHE_TTL_SPOT", "60"))
    CACHE_TTL_KLINE_DAY = int(os.getenv("PA_CACHE_TTL_KLINE_DAY", "3600"))
    CACHE_TTL_KLINE_MIN = int(os.getenv("PA_CACHE_TTL_KLINE_MIN", "1800"))
    CACHE_COLLECTION = "pa_quotes_cache"
    RESULTS_COLLECTION = "pa_signals"

    FETCH_CONCURRENCY = int(os.getenv("PA_FETCH_CONCURRENCY", "1"))
    FETCH_INTERVAL = float(os.getenv("PA_FETCH_INTERVAL", "3.0"))
    FETCH_RETRY_MAX = int(os.getenv("PA_FETCH_RETRY_MAX", "1"))
    FETCH_TIMEOUT = int(os.getenv("PA_FETCH_TIMEOUT", "30"))

    DEFAULT_TIMEFRAME = os.getenv("PA_DEFAULT_TIMEFRAME", "daily")
    DEFAULT_RISK_PCT = float(os.getenv("PA_DEFAULT_RISK_PCT", "0.02"))
    DEFAULT_ACCOUNT_BALANCE = float(os.getenv("PA_DEFAULT_ACCOUNT_BALANCE", "100000"))

    KLINE_DAYS = int(os.getenv("PA_KLINE_DAYS", "120"))
    MIN_KLINE_BARS = int(os.getenv("PA_MIN_KLINE_BARS", "30"))
