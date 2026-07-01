"""IntradayPricer — 盘中实时报价刷新。

从 intraday_tracker 拆出，依赖 TrackingStore 写入峰值，用 radar_utils 的腾讯行情取价。
修复 bug 2：原 update_realtime_prices 无 cron 注册，仅 API 懒触发 → highest/lowest_pnl 全 0。
现由 cron job_auction_intraday_refresh 3min 盘中定时调用。
"""
from typing import Any, Dict, List, Optional

from utils.logger import get_logger
from .radar_utils import (
    now_shanghai, today_str, batch_tencent_quotes, to_tencent_code, strip_prefix_from_code,
)
from .tracking_store import TrackingStore

logger = get_logger(__name__)


class IntradayPricer:
    def __init__(self, store: Optional[TrackingStore] = None):
        self._store = store or TrackingStore()

    def batch_quotes(self, codes: List[str]) -> Dict[str, float]:
        """批量取现价。codes 可为裸代码或带前缀，内部转腾讯代码。"""
        tencent_codes = [to_tencent_code(c) for c in codes if c]
        return batch_tencent_quotes(tencent_codes)

    def update_realtime(self, date: Optional[str] = None) -> int:
        """刷新当日追踪股票的实时盈亏，写回 highest/lowest 峰值。返回刷新条数。"""
        date = date or today_str()
        try:
            tracks = self._store.get_active_or_traded(date)
            if not tracks:
                return 0
            # codes 可能是裸代码（intraday_track 存的是裸代码 symbol）
            codes = [t.get("code", "") for t in tracks if t.get("code")]
            tencent_codes = [to_tencent_code(c) for c in codes]
            quotes = batch_tencent_quotes(tencent_codes)
            if not quotes:
                return 0

            updated = 0
            for t in tracks:
                code = t.get("code", "")
                open_price = t.get("open_price", 0)
                if not code or open_price <= 0:
                    continue
                price = quotes.get(to_tencent_code(code))
                if not price or price <= 0:
                    continue
                pnl_pct = round((price - open_price) / open_price * 100, 2)
                self._store.update_realtime(code, date, price, pnl_pct)
                updated += 1
            logger.debug(f"[IntradayPricer] updated {updated} realtime prices for {date}")
            return updated
        except Exception as e:
            logger.debug(f"[IntradayPricer] update error: {e}")
            return 0

    def get_intraday_data(self, date: Optional[str] = None, refresh: bool = True) -> List[Dict[str, Any]]:
        """获取盘中追踪数据。refresh=True 时先刷新报价。"""
        date = date or today_str()
        if refresh:
            self.update_realtime(date)
        return self._store.get_intraday_data(date)


# ── 向后兼容的模块级函数（原 intraday_tracker.update_realtime_prices / get_intraday_data）──
_default_pricer: Optional[IntradayPricer] = None


def _get_pricer() -> IntradayPricer:
    global _default_pricer
    if _default_pricer is None:
        _default_pricer = IntradayPricer()
    return _default_pricer


def update_realtime_prices(date: Optional[str] = None) -> int:
    return _get_pricer().update_realtime(date)


def get_intraday_data(date: Optional[str] = None, refresh: bool = True) -> List[Dict[str, Any]]:
    return _get_pricer().get_intraday_data(date, refresh)
