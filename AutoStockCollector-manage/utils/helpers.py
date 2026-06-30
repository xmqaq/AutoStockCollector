"""
辅助函数工具库
"""
from datetime import datetime, timedelta, time as dtime
from typing import List, Optional, Any, Dict, Set
from zoneinfo import ZoneInfo
import pandas as pd
import re

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """返回北京时间的 naive datetime，不依赖系统时区设置。"""
    return datetime.now(_BEIJING_TZ).replace(tzinfo=None)


def call_with_timeout(fn, timeout: float, *args, **kwargs):
    """给一个无超时支持的阻塞调用（典型是 akshare 接口）套一层硬超时。

    akshare 内部不暴露 timeout，外部源不响应时会无限阻塞，进而拖死采集任务
    （卡满后被调度器/cron 看门狗强杀为"已取消"）。这里把调用丢到单独线程，
    用 future.result(timeout) 兜底；超时后 **不** 等待该线程结束
    （shutdown(wait=False)）——否则会退化成无超时阻塞——让卡住的线程自生自灭，
    调用方立刻被释放。超时抛 concurrent.futures.TimeoutError（Exception 子类），
    由调用处现有的 try/except 捕获即可。
    """
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ak-timeout")
    future = executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    finally:
        executor.shutdown(wait=False)


def format_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


# ── A 股法定节假日（内置，用于 AKShare 不可用时的兜底） ──────────────────
# 涵盖 2020-2026 年，后续可继续追加
_ASHARE_HOLIDAYS: Set[str] = {
    # 2020
    "2020-01-01","2020-01-24","2020-01-27","2020-01-28","2020-01-29","2020-01-30","2020-01-31",
    "2020-04-06","2020-05-01","2020-05-04","2020-05-05","2020-06-25","2020-06-26",
    "2020-10-01","2020-10-02","2020-10-05","2020-10-06","2020-10-07","2020-10-08",
    # 2021
    "2021-01-01","2021-02-11","2021-02-12","2021-02-15","2021-02-16","2021-02-17",
    "2021-04-05","2021-05-03","2021-05-04","2021-05-05","2021-06-14",
    "2021-09-20","2021-09-21","2021-10-01","2021-10-04","2021-10-05","2021-10-06","2021-10-07",
    # 2022
    "2022-01-03","2022-01-31","2022-02-01","2022-02-02","2022-02-03","2022-02-04",
    "2022-04-04","2022-04-05","2022-05-02","2022-05-03","2022-05-04",
    "2022-06-03","2022-09-12","2022-10-03","2022-10-04","2022-10-05","2022-10-06","2022-10-07",
    # 2023
    "2023-01-02","2023-01-23","2023-01-24","2023-01-25","2023-01-26","2023-01-27",
    "2023-04-05","2023-05-01","2023-05-02","2023-05-03",
    "2023-06-22","2023-06-23","2023-09-29","2023-10-02","2023-10-03","2023-10-04","2023-10-05","2023-10-06",
    # 2024
    "2024-01-01","2024-02-09","2024-02-12","2024-02-13","2024-02-14","2024-02-15",
    "2024-04-04","2024-04-05","2024-05-01","2024-05-02","2024-05-03",
    "2024-06-10","2024-09-16","2024-09-17",
    "2024-10-01","2024-10-02","2024-10-03","2024-10-04","2024-10-07",
    # 2025
    "2025-01-01","2025-01-28","2025-01-29","2025-01-30","2025-01-31","2025-02-03","2025-02-04",
    "2025-04-04","2025-05-01","2025-05-02","2025-05-05",
    "2025-06-02","2025-10-01","2025-10-02","2025-10-03","2025-10-06","2025-10-07","2025-10-08",
    # 2026
    "2026-01-01","2026-02-17","2026-02-18","2026-02-19","2026-02-20","2026-02-23","2026-02-24",
    "2026-04-06","2026-05-01","2026-05-04","2026-05-05",
    "2026-06-19","2026-09-25","2026-10-01","2026-10-02","2026-10-05","2026-10-06","2026-10-07","2026-10-08",
}

# 内存缓存：从 AKShare 获取到的完整交易日集合
_trading_day_cache: Optional[Set[str]] = None


def _load_trading_calendar() -> Set[str]:
    """从 AKShare 获取完整交易日历，失败时返回空集（由调用方回退到兜底逻辑）"""
    global _trading_day_cache
    if _trading_day_cache is not None:
        return _trading_day_cache
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            col = df.columns[0]
            _trading_day_cache = {str(d)[:10] for d in df[col]}
            return _trading_day_cache
    except Exception:
        pass
    _trading_day_cache = set()
    return _trading_day_cache


def is_trading_day(date: datetime) -> bool:
    if date.weekday() >= 5:
        return False
    date_str = format_date(date)
    calendar = _load_trading_calendar()
    if calendar:
        return date_str in calendar
    # 兜底：排除内置节假日
    return date_str not in _ASHARE_HOLIDAYS


def get_market_session(now: Optional[datetime] = None) -> str:
    """返回 A 股当前所处的市场时段，供模拟盘判断"能否即时成交"。

    返回值：
      - closed          非交易日 / 盘前 09:15 前 / 盘后 15:00 后
      - pre_open        09:00-09:15 集合竞价前
      - call_auction    09:15-09:25 开盘集合竞价（撮合价尚未确定，不撮合挂单）
      - pre_open_gap    09:25-09:30 竞价结束到连续竞价之间的空档
      - continuous      09:30-11:30 / 13:00-15:00 连续竞价（可即时成交）
      - lunch           11:30-13:00 午间休市

    集合竞价阶段（call_auction/pre_open_gap）按"开盘即按市价成交"的策略，
    统一不在此时撮合，挂单等 09:30 连续竞价开盘后按实时价成交。
    测试钩子：设置环境变量 PAPER_FORCE_SESSION 可强制返回指定时段。
    """
    import os
    forced = os.environ.get("PAPER_FORCE_SESSION")
    if forced:
        return forced

    now = now or beijing_now()
    if not is_trading_day(now):
        return "closed"
    t = now.time()
    if t < dtime(9, 0):
        return "closed"
    if t < dtime(9, 15):
        return "pre_open"
    if t < dtime(9, 25):
        return "call_auction"
    if t < dtime(9, 30):
        return "pre_open_gap"
    if t <= dtime(11, 30):
        return "continuous"
    if t < dtime(13, 0):
        return "lunch"
    if t <= dtime(15, 0):
        return "continuous"
    return "closed"


def get_trading_days(start_date: str, end_date: str) -> List[str]:
    start = parse_date(start_date)
    end = parse_date(end_date)

    # 优先使用 AKShare 日历做区间过滤
    calendar = _load_trading_calendar()
    if calendar:
        days = []
        current = start
        while current <= end:
            d = format_date(current)
            if d in calendar:
                days.append(d)
            current += timedelta(days=1)
        return days

    # 兜底：周一到周五，排除内置节假日
    days = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(format_date(current))
        current += timedelta(days=1)
    return days


def get_latest_trading_day(before_date: Optional[datetime] = None) -> datetime:
    if before_date is None:
        before_date = beijing_now()

    current = before_date
    for _ in range(10):
        if is_trading_day(current):
            return current
        current -= timedelta(days=1)

    return before_date


def validate_stock_code(code: str) -> bool:
    pattern = r"^(SH|SZ|sh|sz)[0-9]{6}$"
    return bool(re.match(pattern, code))


def normalize_stock_code(code: str) -> str:
    code = code.upper()
    if not code.startswith("SH") and not code.startswith("SZ"):
        if code.startswith("6"):
            code = "SH" + code
        elif code.startswith("0") or code.startswith("3"):
            code = "SZ" + code
    return code


def normalize_stock_code_flexible(code: str) -> str:
    """
    灵活股票代码标准化函数，支持多种输入格式：
    - 纯6位数字 (如 000001 -> SZ000001, 600000 -> SH600000)
    - 已带前缀 (如 SZ000001, SH600000 -> 保持不变)
    - 小写前缀 (如 sz000001 -> SZ000001)
    - 无前缀带点号 (如 000001.SZ -> SZ000001)
    """
    if not code:
        return code

    code = code.strip().upper()

    if code.startswith("SH") or code.startswith("SZ"):
        return code

    if "." in code:
        parts = code.split(".")
        if len(parts) == 2:
            suffix = parts[1].upper()
            digits = parts[0]
            if suffix in ("SH", "SZ"):
                return f"{suffix}{digits}"
            elif suffix in ("SHANGHAI", "S"):
                return f"SH{digits}"
            elif suffix in ("SHENZHEN", "SZ"):
                return f"SZ{digits}"

    digits = "".join(c for c in code if c.isdigit())
    if len(digits) == 6:
        if digits.startswith("6"):
            return f"SH{digits}"
        elif digits.startswith("0") or digits.startswith("3"):
            return f"SZ{digits}"

    return code.upper()


def parse_stock_name(name: str) -> Dict[str, Any]:
    patterns = {
        "st": r"\*?ST",
        "pt": r"PT",
        "退市": r"退市",
    }

    result = {
        "name": name,
        "is_st": False,
        "is_pt": False,
        "is_delisted": False
    }

    for key, pattern in patterns.items():
        if re.search(pattern, name):
            result[f"is_{key}"] = True

    return result


def calculate_change_percent(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round((current - previous) / previous * 100, 2)


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def remove_outliers(data: List[float], threshold: float = 3.0) -> List[float]:
    if len(data) < 3:
        return data

    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    std_dev = variance ** 0.5

    return [x for x in data if abs(x - mean) <= threshold * std_dev]


def fill_missing_dates(
    df: pd.DataFrame,
    date_col: str,
    freq: str = "D"
) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)

    complete_range = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq=freq
    )

    df = df.reindex(complete_range)
    return df.reset_index().rename(columns={"index": date_col})


def retry_on_exception(func, max_attempts: int = 3, delay: float = 1.0):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise e
            import time
            time.sleep(delay * (attempt + 1))


class DateRange:
    def __init__(self, start: str, end: str):
        self.start = parse_date(start)
        self.end = parse_date(end)

    def __iter__(self):
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(days=1)

    def trading_days_only(self) -> List[datetime]:
        return [d for d in self if is_trading_day(d)]


def merge_dicts(*dicts: Dict) -> Dict:
    result = {}
    for d in dicts:
        result.update(d)
    return result


def filter_dict_keys(data: Dict, keys: List[str]) -> Dict:
    return {k: v for k, v in data.items() if k in keys}


def deep_get(dictionary: Dict, *keys, default=None):
    value = dictionary
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, default)
        else:
            return default
    return value