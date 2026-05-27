"""
辅助函数工具库
"""
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
import pandas as pd
import re


def format_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def get_trading_days(start_date: str, end_date: str) -> List[str]:
    start = parse_date(start_date)
    end = parse_date(end_date)

    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(format_date(current))
        current += timedelta(days=1)

    return days


def is_trading_day(date: datetime) -> bool:
    return date.weekday() < 5


def get_latest_trading_day(before_date: Optional[datetime] = None) -> datetime:
    if before_date is None:
        before_date = datetime.now()

    current = before_date
    days_checked = 0
    while days_checked < 10:
        if is_trading_day(current):
            return current
        current -= timedelta(days=1)
        days_checked += 1

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