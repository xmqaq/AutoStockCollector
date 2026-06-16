"""call_with_timeout 共享硬超时工具测试。

给无 timeout 支持的阻塞调用（akshare 接口）兜底，外部源挂起时不再无限等待。
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from concurrent.futures import TimeoutError as FuturesTimeout
from utils.helpers import call_with_timeout


class TestCallWithTimeout(unittest.TestCase):
    def test_returns_result_when_fast(self):
        self.assertEqual(call_with_timeout(lambda a, b: a + b, 5, 2, 3), 5)

    def test_passes_kwargs(self):
        self.assertEqual(call_with_timeout(lambda x=0: x * 2, 5, x=21), 42)

    def test_propagates_exception(self):
        def boom():
            raise ValueError("nope")
        with self.assertRaises(ValueError):
            call_with_timeout(boom, 5)

    def test_aborts_on_hang(self):
        """底层挂起 30s，0.5s 超时应在数秒内放弃，绝不等满。"""
        start = time.monotonic()
        with self.assertRaises(FuturesTimeout):
            call_with_timeout(lambda: time.sleep(30), 0.5)
        self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
