"""限速 HTTP 客户端 — Semaphore + 固定间隔节流 + urllib3 重试。

专为东方财富数据中心设计，防止触发 429 限流。
"""
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as UrllibRetry

from utils.logger import get_logger

logger = get_logger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_EASTMONEY_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Referer": "https://data.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class RateLimitedFetcher:
    """限速 HTTP 客户端 — Semaphore + 固定间隔节流 + 指数退避重试。"""

    def __init__(
        self,
        max_concurrent: int = 2,
        min_interval: float = 2.5,
        retry_max: int = 3,
        timeout: int = 30,
    ):
        self._sem = threading.Semaphore(max_concurrent)
        self._min_interval = min_interval
        self._retry_max = retry_max
        self._timeout = timeout
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

        self._session = requests.Session()
        urllib_retry = UrllibRetry(
            total=retry_max,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=urllib_retry, pool_connections=4, pool_maxsize=8)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update(_EASTMONEY_HEADERS)

    def _throttle(self, key: str = "default"):
        now = time.time()
        with self._lock:
            last = self._last_request.get(key, 0)
            elapsed = now - last
            if elapsed < self._min_interval:
                sleep_time = self._min_interval - elapsed
                logger.debug(f"[RateLimitedFetcher] Throttle {sleep_time:.2f}s for {key}")
                time.sleep(sleep_time)
            self._last_request[key] = time.time()

    def _backoff_delay(self, attempt: int) -> float:
        return min(2 ** attempt * 2, 30)

    def fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """带限速的 JSON GET 请求。返回解析后的 dict 或 None。"""
        self._throttle()
        with self._sem:
            last_error = None
            for attempt in range(1, self._retry_max + 2):
                try:
                    logger.info(
                        f"[RateLimitedFetcher] GET {url.split('?')[0]} attempt={attempt}"
                    )
                    resp = self._session.get(
                        url, params=params, timeout=self._timeout
                    )
                    if resp.status_code == 429:
                        delay = self._backoff_delay(attempt)
                        logger.warning(
                            f"[RateLimitedFetcher] 429 {url.split('?')[0]}, "
                            f"retry in {delay:.0f}s"
                        )
                        time.sleep(delay)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data
                except requests.ConnectionError as e:
                    last_error = e
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        f"[RateLimitedFetcher] ConnectionError attempt={attempt}, "
                        f"retry in {delay:.0f}s: {e}"
                    )
                    time.sleep(delay)
                except requests.Timeout as e:
                    last_error = e
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        f"[RateLimitedFetcher] Timeout attempt={attempt}, "
                        f"retry in {delay:.0f}s: {e}"
                    )
                    time.sleep(delay)
                except requests.RequestException as e:
                    last_error = e
                    logger.error(
                        f"[RateLimitedFetcher] HTTP error attempt={attempt}: {e}"
                    )
                    break
            logger.error(
                f"[RateLimitedFetcher] All attempts failed: {last_error}"
            )
            return None

    def close(self):
        self._session.close()


_default_fetcher: Optional[RateLimitedFetcher] = None
_fetcher_lock = threading.Lock()


def get_fetcher() -> RateLimitedFetcher:
    global _default_fetcher
    if _default_fetcher is None:
        with _fetcher_lock:
            if _default_fetcher is None:
                from .config import ResearchConfig
                _default_fetcher = RateLimitedFetcher(
                    max_concurrent=ResearchConfig.FETCH_CONCURRENCY,
                    min_interval=ResearchConfig.FETCH_INTERVAL,
                    retry_max=ResearchConfig.FETCH_RETRY_MAX,
                    timeout=ResearchConfig.FETCH_TIMEOUT,
                )
    return _default_fetcher
