"""
API客户端模块
提供请求参数校验、签名、超时控制、错误重试机制
"""
import time
import hashlib
import uuid
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from functools import wraps
from utils.logger import get_logger

logger = get_logger(__name__)


class RequestContext:
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.start_time = time.time()
        self.end_time = None
        self.status = "pending"
        self.error = None
        self.response = None

    def mark_success(self, response: Any):
        self.status = "success"
        self.response = response
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

    def mark_failure(self, error: Exception):
        self.status = "failed"
        self.error = error
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration": getattr(self, "duration", None),
            "status": self.status,
            "error": str(self.error) if self.error else None,
        }


class RetryConfig:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retry_on_timeout: bool = True,
        retry_on_connection_error: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_timeout = retry_on_timeout
        self.retry_on_connection_error = retry_on_connection_error


class APIRateLimiter:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._limits: Dict[str, Dict[str, Any]] = {}
            self._requests: Dict[str, list] = {}
            self._mutex = threading.Lock()

    def set_limit(self, api_name: str, calls: int, period: float):
        with self._mutex:
            self._limits[api_name] = {
                "calls": calls,
                "period": period,
                "current": 0,
                "window_start": time.time()
            }
            self._requests[api_name] = []

    def acquire(self, api_name: str) -> bool:
        with self._mutex:
            if api_name not in self._limits:
                return True

            limit = self._limits[api_name]
            now = time.time()
            window_elapsed = now - limit["window_start"]

            if window_elapsed >= limit["period"]:
                limit["current"] = 0
                limit["window_start"] = now
                self._requests[api_name] = []

            if limit["current"] < limit["calls"]:
                limit["current"] += 1
                self._requests[api_name].append(now)
                return True

            sleep_time = limit["period"] - window_elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                limit["current"] = 0
                limit["window_start"] = now
                self._requests[api_name] = []

            limit["current"] = 1
            self._requests[api_name].append(now)
            return True

    def get_wait_time(self, api_name: str) -> float:
        with self._mutex:
            if api_name not in self._limits:
                return 0.0

            limit = self._limits[api_name]
            now = time.time()
            window_elapsed = now - limit["window_start"]

            if window_elapsed >= limit["period"]:
                return 0.0

            if limit["current"] < limit["calls"]:
                return 0.0

            return limit["period"] - window_elapsed


class APIClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.rate_limiter = APIRateLimiter()
            self._retry_configs: Dict[str, RetryConfig] = {}
            self._default_retry = RetryConfig()
            self._timeout_default = 30.0
            self._request_history: list = []
            self._history_mutex = threading.Lock()
            self._setup_default_limits()

    def _setup_default_limits(self):
        self.rate_limiter.set_limit("akshare_stock", calls=100, period=60)
        self.rate_limiter.set_limit("akshare_financial", calls=50, period=60)
        self.rate_limiter.set_limit("akshare_news", calls=30, period=60)

    def set_retry_config(self, api_name: str, config: RetryConfig):
        self._retry_configs[api_name] = config

    def set_default_timeout(self, timeout: float):
        self._timeout_default = timeout

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        return hashlib.md5(param_str.encode()).hexdigest()

    def _record_request(self, context: RequestContext, api_name: str):
        with self._history_mutex:
            record = context.to_dict()
            record["api_name"] = api_name
            self._request_history.append(record)
            if len(self._request_history) > 1000:
                self._request_history = self._request_history[-500:]

    def call_with_retry(
        self,
        func: Callable,
        api_name: str,
        params: Dict[str, Any] = None,
        retry_config: RetryConfig = None,
        timeout: float = None
    ) -> Any:
        ctx = RequestContext()
        config = retry_config or self._retry_configs.get(api_name, self._default_retry)
        timeout = timeout or self._timeout_default
        params = params or {}

        logger.info(f"[{ctx.request_id}] Calling {api_name} with params: {list(params.keys())}")

        last_error = None
        for attempt in range(config.max_retries + 1):
            try:
                self.rate_limiter.acquire(api_name)

                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"API call timeout after {timeout}s")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout))

                try:
                    if params:
                        result = func(**params)
                    else:
                        result = func()
                finally:
                    signal.alarm(0)

                ctx.mark_success(result)
                self._record_request(ctx, api_name)
                logger.info(f"[{ctx.request_id}] Success in {ctx.duration:.2f}s")
                return result

            except TimeoutError as e:
                last_error = e
                logger.warning(f"[{ctx.request_id}] Timeout on attempt {attempt + 1}: {e}")

            except (ConnectionError, ConnectionAbortedError) as e:
                last_error = e
                if config.retry_on_connection_error:
                    logger.warning(f"[{ctx.request_id}] Connection error on attempt {attempt + 1}: {e}")
                else:
                    break

            except Exception as e:
                last_error = e
                logger.warning(f"[{ctx.request_id}] Error on attempt {attempt + 1}: {e}")

            if attempt < config.max_retries:
                delay = min(config.base_delay * (config.exponential_base ** attempt), config.max_delay)
                logger.info(f"[{ctx.request_id}] Retrying in {delay:.2f}s (attempt {attempt + 2}/{config.max_retries + 1})")
                time.sleep(delay)

        ctx.mark_failure(last_error)
        self._record_request(ctx, api_name)
        logger.error(f"[{ctx.request_id}] All retries failed: {last_error}")
        raise last_error

    def get_request_stats(self) -> Dict[str, Any]:
        with self._history_mutex:
            total = len(self._request_history)
            success = sum(1 for r in self._request_history if r["status"] == "success")
            failed = sum(1 for r in self._request_history if r["status"] == "failed")

            durations = [r["duration"] for r in self._request_history if r.get("duration")]
            avg_duration = sum(durations) / len(durations) if durations else 0

            return {
                "total_requests": total,
                "success": success,
                "failed": failed,
                "success_rate": success / total if total > 0 else 0,
                "avg_duration": avg_duration
            }

    def get_api_stats(self, api_name: str) -> Dict[str, Any]:
        with self._history_mutex:
            api_requests = [r for r in self._request_history if r.get("api_name") == api_name]
            total = len(api_requests)
            success = sum(1 for r in api_requests if r["status"] == "success")

            return {
                "api_name": api_name,
                "total_requests": total,
                "success": success,
                "success_rate": success / total if total > 0 else 0
            }


def validate_params(required_params: list, optional_params: list = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            params = kwargs.get("params", {})
            missing = [p for p in required_params if p not in params]
            if missing:
                raise ValueError(f"Missing required parameters: {missing}")

            if optional_params:
                allowed = set(required_params + optional_params)
                unknown = [k for k in params.keys() if k not in allowed]
                if unknown:
                    logger.warning(f"Unknown parameters ignored: {unknown}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


api_client = APIClient()