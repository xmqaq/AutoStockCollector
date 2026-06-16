"""财新采集硬超时回归测试。

根因：akshare stock_news_main_cx() 无超时，外部源不响应时无限阻塞，
拖死整个新闻采集任务（卡满 1 小时后被看门狗强杀为"已取消"）。
本测试验证 _fetch_caixin_df 在底层调用挂起时，能在超时窗口内放弃，而不是无限等待。
"""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from concurrent.futures import TimeoutError as FuturesTimeout
from modules.news.news_manager import NewsManager


class TestCaixinTimeout(unittest.TestCase):
    def setUp(self):
        # akshare 是惰性 import（_fetch_caixin_df 内部 import akshare），
        # 这里直接往 sys.modules 注入一个会挂起的假模块。
        self._real_ak = sys.modules.get("akshare")
        fake = MagicMock()
        fake.stock_news_main_cx.side_effect = lambda: time.sleep(30)  # 模拟无限挂起
        sys.modules["akshare"] = fake

    def tearDown(self):
        if self._real_ak is not None:
            sys.modules["akshare"] = self._real_ak
        else:
            sys.modules.pop("akshare", None)

    def test_hanging_caixin_aborts_within_timeout(self):
        """底层挂起 30s，0.5s 超时应在 ~0.5s 内抛 TimeoutError，绝不等满 30s。"""
        start = time.monotonic()
        with self.assertRaises(FuturesTimeout):
            NewsManager._fetch_caixin_df(timeout=0.5)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5, f"超时未生效，实际等待 {elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
