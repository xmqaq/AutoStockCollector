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


class ResearchConfig:
    CACHE_TTL_DAYS = int(os.getenv("RESEARCH_CACHE_TTL_DAYS", "7"))
    CACHE_MIN_COUNT = int(os.getenv("RESEARCH_CACHE_MIN_COUNT", "15"))
    EASTMONEY_PAGE_SIZE = int(os.getenv("RESEARCH_EASTMONEY_PAGE_SIZE", "50"))
    EASTMONEY_MAX_PAGES = int(os.getenv("RESEARCH_EASTMONEY_MAX_PAGES", "3"))
    FETCH_CONCURRENCY = int(os.getenv("RESEARCH_FETCH_CONCURRENCY", "2"))
    FETCH_INTERVAL = float(os.getenv("RESEARCH_FETCH_INTERVAL", "2.5"))
    FETCH_RETRY_MAX = int(os.getenv("RESEARCH_FETCH_RETRY_MAX", "3"))
    FETCH_TIMEOUT = int(os.getenv("RESEARCH_FETCH_TIMEOUT", "30"))
    CACHE_COLLECTION = "reports_cache"
    RESULTS_COLLECTION = "research_analysis_results"
