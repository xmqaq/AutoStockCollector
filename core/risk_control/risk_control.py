"""
风控模块 - 限流控制、熔断机制、退避重试
"""
import time
import threading
from typing import Optional, Dict, Callable
from datetime import datetime
from collections import defaultdict
from functools import wraps
from config.settings import Settings
from utils.logger import get_logger


logger = get_logger(__name__)


class RateLimiter:
    """
    滑动窗口 burst 限速器。
    burst 个令牌可同时通过，超出后等到最旧的令牌过期才能再发。
    例：burst=5, interval=2.0 → 每 2 秒最多 5 个请求 = 2.5 req/s，
    5 个并发线程均可立即通行，互不阻塞。
    """

    def __init__(self, min_interval: float = 1.0, burst: int = 1):
        self.min_interval = min_interval
        self.burst = burst
        self._timestamps: Dict[str, list] = {}
        self._lock = threading.Lock()

    def wait_if_needed(self, key: str = "default"):
        while True:
            with self._lock:
                now = time.time()
                window_start = now - self.min_interval
                ts = [t for t in self._timestamps.get(key, []) if t > window_start]
                if len(ts) < self.burst:
                    ts.append(now)
                    self._timestamps[key] = ts
                    return
                # 等最旧的令牌过期
                sleep_for = ts[0] + self.min_interval - now
            if sleep_for > 0:
                time.sleep(sleep_for)

    def set_interval(self, interval: float):
        self.min_interval = interval

    def set_burst(self, burst: int):
        self.burst = burst


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN and self._should_attempt_reset():
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
            return self._state

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = self.CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )

    def can_execute(self) -> bool:
        with self._lock:
            if self._state == self.CLOSED:
                return True
            if self._state == self.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            # OPEN: check if recovery timeout elapsed
            if self._should_attempt_reset():
                self._state = self.HALF_OPEN
                self._half_open_calls = 1
                return True
            return False

    def reset(self):
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


class ExponentialBackoff:
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_attempts: int = 3
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts

    def get_delay(self, attempt: int) -> float:
        return min(self.base_delay * (2 ** attempt), self.max_delay)

    def execute_with_retry(self, func: Callable, *args, **kwargs):
        last_exception = None
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = self.get_delay(attempt)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_attempts} attempts failed: {e}")
        raise last_exception


class ConcurrentController:
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._current_concurrent = 0
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrent)

    def acquire(self):
        self._semaphore.acquire()
        with self._lock:
            self._current_concurrent += 1

    def release(self):
        with self._lock:
            self._current_concurrent = max(0, self._current_concurrent - 1)
        self._semaphore.release()

    def get_current_concurrent(self) -> int:
        with self._lock:
            return self._current_concurrent

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class SceneAdapter:
    SCENE_INCREMENTAL = "incremental"
    SCENE_NORMAL = "normal"
    SCENE_BATCH = "batch"

    def __init__(self):
        self._scene = self.SCENE_NORMAL
        self._rate_limiter = RateLimiter(
            Settings.RATE_LIMIT_CONFIG["normal_interval"],
            burst=Settings.get_max_concurrent()
        )

    def set_scene(self, scene: str):
        self._scene = scene
        interval = Settings.get_rate_limit_interval(scene)
        self._rate_limiter.set_interval(interval)

    def get_scene(self) -> str:
        return self._scene

    def wait_if_needed(self, key: str = "default"):
        self._rate_limiter.wait_if_needed(key)


class RiskController:
    _instance: Optional["RiskController"] = None
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

            self.rate_limiter = RateLimiter(
                Settings.RATE_LIMIT_CONFIG["min_interval"],
                burst=Settings.get_max_concurrent()
            )
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=Settings.CIRCUIT_BREAKER_CONFIG["failure_threshold"],
                recovery_timeout=Settings.CIRCUIT_BREAKER_CONFIG["recovery_timeout"],
                half_open_max_calls=Settings.CIRCUIT_BREAKER_CONFIG["half_open_max_calls"],
            )
            self.exponential_backoff = ExponentialBackoff(
                base_delay=Settings.COLLECTOR_CONFIG["retry_delay"],
                max_attempts=Settings.COLLECTOR_CONFIG["retry_times"],
            )
            self.concurrent_controller = ConcurrentController(
                max_concurrent=Settings.get_max_concurrent()
            )
            self.scene_adapter = SceneAdapter()
            self._source_failure_count: Dict[str, int] = defaultdict(int)
            self._source_circuit_breakers: Dict[str, CircuitBreaker] = {}

            logger.info("RiskController initialized successfully")

    def set_scene(self, scene: str):
        self.scene_adapter.set_scene(scene)

    def wait_for_rate_limit(self, key: str = "default"):
        self.scene_adapter.wait_if_needed(key)

    def check_circuit_breaker(self, source: Optional[str] = None) -> bool:
        if source is None:
            return self.circuit_breaker.can_execute()
        if source not in self._source_circuit_breakers:
            self._source_circuit_breakers[source] = CircuitBreaker()
        return self._source_circuit_breakers[source].can_execute()

    def record_success(self, source: Optional[str] = None):
        self.circuit_breaker.record_success()
        if source and source in self._source_circuit_breakers:
            self._source_circuit_breakers[source].record_success()
        self._source_failure_count[source or "default"] = 0

    def record_failure(self, source: Optional[str] = None):
        self.circuit_breaker.record_failure()
        if source:
            if source not in self._source_circuit_breakers:
                self._source_circuit_breakers[source] = CircuitBreaker()
            self._source_circuit_breakers[source].record_failure()
            self._source_failure_count[source] += 1
        logger.warning(f"Data source failure recorded. Source: {source}")

    def execute_with_protection(
        self,
        func: Callable,
        *args,
        source: Optional[str] = None,
        **kwargs
    ):
        """
        执行保护：
        1. 熔断检查
        2. 限速（锁外 sleep）
        3. 获取并发槽 → 执行调用 → 释放槽
        4. 重试 sleep 在信号量外，不占并发槽
        """
        if not self.check_circuit_breaker(source):
            raise Exception(f"Circuit breaker is open for source: {source}")

        last_exc = None
        max_attempts = self.exponential_backoff.max_attempts

        for attempt in range(max_attempts):
            if attempt > 0:
                delay = self.exponential_backoff.get_delay(attempt - 1)
                logger.warning(f"Retry attempt {attempt}/{max_attempts - 1}, waiting {delay}s")
                time.sleep(delay)  # 重试等待在信号量外，不占并发槽

            self.wait_for_rate_limit(source or "default")

            try:
                with self.concurrent_controller:  # 仅在实际 HTTP 调用期间持有槽
                    result = func(*args, **kwargs)
                self.record_success(source)
                return result
            except Exception as e:
                last_exc = e
                self.record_failure(source)

        raise last_exc

    def acquire_concurrent_slot(self):
        return self.concurrent_controller.acquire()

    def release_concurrent_slot(self):
        self.concurrent_controller.release()

    def reset_all(self):
        self.circuit_breaker.reset()
        for cb in self._source_circuit_breakers.values():
            cb.reset()
        self._source_failure_count.clear()
        logger.info("RiskController reset successfully")


def rate_limit(key: str = "default", interval: float = 1.0):
    limiter = RateLimiter(interval)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed(key)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def circuit_protect(failure_threshold: int = 5, recovery_timeout: int = 60):
    breaker = CircuitBreaker(failure_threshold, recovery_timeout)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise Exception("Circuit breaker is open")
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        return wrapper
    return decorator


def retry_with_backoff(
    base_delay: float = 1.0,
    max_attempts: int = 3,
    max_delay: float = 60.0
):
    backoff = ExponentialBackoff(base_delay, max_delay, max_attempts)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return backoff.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


def controlled_concurrent(max_concurrent: int = 5):
    controller = ConcurrentController(max_concurrent)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            controller.acquire()
            try:
                return func(*args, **kwargs)
            finally:
                controller.release()
        return wrapper
    return decorator


risk_controller = RiskController()
