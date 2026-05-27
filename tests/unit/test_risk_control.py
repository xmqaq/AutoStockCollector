"""
风控模块测试
"""
import unittest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.risk_control.risk_control import (
    RateLimiter,
    CircuitBreaker,
    ExponentialBackoff,
    ConcurrentController,
    SceneAdapter,
    RiskController,
)


class TestRateLimiter(unittest.TestCase):
    def test_rate_limiter_basic(self):
        limiter = RateLimiter(min_interval=0.1)
        start = time.time()

        limiter.wait_if_needed("test")
        limiter.wait_if_needed("test")

        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.1)

    def test_rate_limiter_set_interval(self):
        limiter = RateLimiter(min_interval=0.1)
        limiter.set_interval(0.5)

        self.assertEqual(limiter.min_interval, 0.5)


class TestCircuitBreaker(unittest.TestCase):
    def test_circuit_breaker_initial_state(self):
        breaker = CircuitBreaker(failure_threshold=3)
        self.assertEqual(breaker.state, CircuitBreaker.CLOSED)

    def test_circuit_breaker_open_after_failures(self):
        breaker = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            breaker.record_failure()

        self.assertEqual(breaker.state, CircuitBreaker.OPEN)

    def test_circuit_breaker_reset(self):
        breaker = CircuitBreaker(failure_threshold=2)

        breaker.record_failure()
        breaker.record_failure()

        self.assertEqual(breaker.state, CircuitBreaker.OPEN)

        breaker.reset()

        self.assertEqual(breaker.state, CircuitBreaker.CLOSED)

    def test_circuit_breaker_success_resets(self):
        breaker = CircuitBreaker(failure_threshold=2)

        breaker.record_failure()
        breaker.record_success()

        self.assertEqual(breaker._failure_count, 0)
        self.assertEqual(breaker.state, CircuitBreaker.CLOSED)

    def test_circuit_breaker_can_execute(self):
        breaker = CircuitBreaker(failure_threshold=2)

        self.assertTrue(breaker.can_execute())

        breaker.record_failure()
        breaker.record_failure()

        self.assertEqual(breaker.state, CircuitBreaker.OPEN)
        self.assertFalse(breaker.can_execute())


class TestExponentialBackoff(unittest.TestCase):
    def test_get_delay(self):
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=60.0, max_attempts=5)

        self.assertEqual(backoff.get_delay(0), 1.0)
        self.assertEqual(backoff.get_delay(1), 2.0)
        self.assertEqual(backoff.get_delay(2), 4.0)

    def test_get_delay_max_cap(self):
        backoff = ExponentialBackoff(base_delay=10.0, max_delay=30.0, max_attempts=10)

        self.assertEqual(backoff.get_delay(5), 30.0)
        self.assertEqual(backoff.get_delay(10), 30.0)

    def test_execute_with_retry_success(self):
        backoff = ExponentialBackoff(base_delay=0.1, max_attempts=3)

        def success_func():
            return "success"

        result = backoff.execute_with_retry(success_func)
        self.assertEqual(result, "success")

    def test_execute_with_retry_eventual_success(self):
        backoff = ExponentialBackoff(base_delay=0.01, max_attempts=3)

        attempts = {"count": 0}

        def flaky_func():
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise Exception("Temporary error")
            return "success"

        result = backoff.execute_with_retry(flaky_func)
        self.assertEqual(result, "success")
        self.assertEqual(attempts["count"], 2)


class TestConcurrentController(unittest.TestCase):
    def test_acquire_release(self):
        controller = ConcurrentController(max_concurrent=2)

        controller.acquire()
        self.assertEqual(controller.get_current_concurrent(), 1)

        controller.release()
        self.assertEqual(controller.get_current_concurrent(), 0)

    def test_max_concurrent_limit(self):
        controller = ConcurrentController(max_concurrent=2)

        controller.acquire()
        controller.acquire()

        self.assertEqual(controller.get_current_concurrent(), 2)


class TestSceneAdapter(unittest.TestCase):
    def test_set_scene(self):
        adapter = SceneAdapter()

        adapter.set_scene(SceneAdapter.SCENE_INCREMENTAL)
        self.assertEqual(adapter.get_scene(), SceneAdapter.SCENE_INCREMENTAL)

        adapter.set_scene(SceneAdapter.SCENE_BATCH)
        self.assertEqual(adapter.get_scene(), SceneAdapter.SCENE_BATCH)


class TestRiskController(unittest.TestCase):
    def test_singleton(self):
        rc1 = RiskController()
        rc2 = RiskController()

        self.assertIs(rc1, rc2)

    def test_set_scene(self):
        rc = RiskController()
        rc.set_scene("incremental")

    def test_record_success_failure(self):
        rc = RiskController()
        rc.record_success()
        rc.record_failure()


if __name__ == "__main__":
    unittest.main()