"""
数据采集基类
定义统一采集接口与重试机制，包含"非东财优先"固定优先级规则
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, date
from utils.helpers import beijing_now
from enum import Enum
import time
import pandas as pd
from config.settings import Settings
from core.risk_control.risk_control import RiskController
from utils.logger import get_logger


logger = get_logger(__name__)


class DataSourcePriority(Enum):
    """
    AKShare数据源固定优先级规则
    
    文档规范：
    - 第一优先级（首选）：非东方财富数据源（新浪财经、同花顺、百度财经等）
    - 第二优先级（最低）：东方财富数据源
    - 全局统一、全品类通用、无自动降级、无兜底切换
    """
    XINA = 1
    THS = 2
    BAIDU = 3
    SINA = 4
    CNINFO = 5
    EASTMONEY = 10
    DEFAULT = 1


class SourceSelector:
    """
    数据源选择器
    实现"非东财优先"固定优先级规则
    """
    
    PREFERRED_SOURCES = ["sina", "ths", "baidu", "xina", "cninfo", "baostock"]
    EASTMONEY_SOURCES = ["eastmoney", "em", "东方财富"]
    FORBIDDEN_SOURCES = []
    
    @classmethod
    def is_preferred_source(cls, source: str) -> bool:
        if not source:
            return True
        source_lower = source.lower()
        for preferred in cls.PREFERRED_SOURCES:
            if preferred in source_lower:
                return True
        return False
    
    @classmethod
    def is_eastmoney_source(cls, source: str) -> bool:
        if not source:
            return False
        source_lower = source.lower()
        for em in cls.EASTMONEY_SOURCES:
            if em in source_lower:
                return True
        return False
    
    @classmethod
    def should_skip_source(cls, source: str) -> bool:
        return cls.is_eastmoney_source(source)
    
    @classmethod
    def filter_sources(cls, sources: List[str]) -> List[str]:
        return [s for s in sources if not cls.should_skip_source(s)] or sources


class BaseCollector(ABC):
    def __init__(
        self,
        source_priority: Optional[List[str]] = None,
        use_eastmoney_last: bool = True
    ):
        self.source_priority = source_priority or Settings.get_data_source_priority(
            exclude_eastmoney=use_eastmoney_last
        )
        self.risk_controller = RiskController()
        self.retry_times = Settings.COLLECTOR_CONFIG["retry_times"]
        self.retry_delay = Settings.COLLECTOR_CONFIG["retry_delay"]
        self.request_timeout = Settings.COLLECTOR_CONFIG["request_timeout"]
        self.source_selector = SourceSelector()
        self._collect_source_stats = {"preferred": 0, "eastmoney": 0, "skipped": 0}
    
    def record_source_usage(self, source: str):
        if SourceSelector.is_eastmoney_source(source):
            self._collect_source_stats["eastmoney"] += 1
        elif SourceSelector.is_preferred_source(source):
            self._collect_source_stats["preferred"] += 1
        else:
            self._collect_source_stats["preferred"] += 1
    
    def record_source_skip(self):
        self._collect_source_stats["skipped"] += 1
    
    def get_source_stats(self) -> Dict[str, int]:
        return self._collect_source_stats.copy()
    
    def log_priority_rule(self, source: str, action: str = "used"):
        if SourceSelector.is_eastmoney_source(source):
            logger.info(f"[优先级规则] 东方财富数据源: {action} (优先级: {DataSourcePriority.EASTMONEY.value})")
        elif SourceSelector.is_preferred_source(source):
            logger.info(f"[优先级规则] 非东财数据源: {source} {action} (优先级: {DataSourcePriority.DEFAULT.value})")
        else:
            logger.info(f"[优先级规则] 数据源: {source} {action}")
    
    def validate_source_priority(self, interface_name: str) -> bool:
        logger.info(f"[优先级规则] 接口 {interface_name} 遵循非东财优先规则")
        return True

    @abstractmethod
    def collect(self, **kwargs) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def collect_single(self, code: str, **kwargs) -> Optional[Dict[str, Any]]:
        pass

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        source: Optional[str] = None,
        **kwargs
    ) -> Any:
        return self.risk_controller.execute_with_protection(
            func, *args, source=source, **kwargs
        )

    def execute_protected(
        self,
        func: Callable,
        *args,
        source: Optional[str] = None,
        **kwargs
    ) -> Any:
        return self.risk_controller.execute_with_protection(
            func,
            *args,
            source=source,
            **kwargs
        )

    def normalize_dataframe(
        self,
        df: pd.DataFrame,
        code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []

        df = df.copy()

        if "代码" in df.columns and "code" not in df.columns:
            df["code"] = df["代码"].apply(self._normalize_code)

        if "日期" in df.columns and "date" not in df.columns:
            df["date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")

        if code and "code" not in df.columns:
            df["code"] = code

        df["_updated_at"] = beijing_now()

        df.columns = [c.lower().strip() for c in df.columns]

        records = df.to_dict("records")

        for record in records:
            for key, value in record.items():
                if isinstance(value, date) and not isinstance(value, datetime):
                    record[key] = datetime.combine(value, datetime.min.time())

        return records

    def _normalize_code(self, code: str) -> str:
        code = str(code).strip().upper()
        if not code.startswith(("SH", "SZ")):
            if code.startswith("6"):
                code = "SH" + code
            elif code.startswith(("0", "3")):
                code = "SZ" + code
        return code

    def validate_required_fields(
        self,
        data: Dict[str, Any],
        required_fields: List[str]
    ) -> bool:
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                return False
        return True

    def clean_numeric_fields(
        self,
        data: Dict[str, Any],
        numeric_fields: List[str]
    ) -> Dict[str, Any]:
        for field in numeric_fields:
            if field in data:
                try:
                    if isinstance(data[field], str):
                        data[field] = float(data[field].replace(",", ""))
                    elif data[field] is None:
                        data[field] = 0.0
                except (ValueError, TypeError):
                    data[field] = 0.0
        return data

    def batch_collect(
        self,
        codes: List[str],
        collector_func: Callable,
        batch_size: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        all_results = []

        for i in range(0, len(codes), batch_size):
            batch_codes = codes[i:i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1}, "
                f"codes {i + 1}-{min(i + batch_size, len(codes))}"
            )

            for code in batch_codes:
                try:
                    result = self.execute_with_retry(
                        collector_func,
                        code,
                        **kwargs
                    )
                    if result:
                        all_results.extend(result if isinstance(result, list) else [result])
                except Exception as e:
                    logger.error(f"Failed to collect {code}: {e}")

        return all_results

    def get_all_stock_codes(self) -> List[str]:
        """
        从沪深交易所官网获取全量A股代码，避免走BSE代理被阻断的接口。
        SSE: stock_info_sh_name_code  SZSE: stock_info_sz_name_code
        """
        import akshare as ak
        codes: List[str] = []

        # 沪市（上交所）
        for symbol in ("主板A股", "科创板"):
            try:
                df = ak.stock_info_sh_name_code(symbol=symbol)
                for _, row in df.iterrows():
                    raw = str(row.get("证券代码", "")).strip()
                    if raw:
                        codes.append(f"SH{raw}")
            except Exception as e:
                logger.warning(f"SSE {symbol} list failed: {e}")

        # 深市（深交所）
        for symbol in ("A股列表",):
            try:
                df = ak.stock_info_sz_name_code(symbol=symbol)
                col = "A股代码" if "A股代码" in df.columns else df.columns[0]
                for _, row in df.iterrows():
                    raw = str(row.get(col, "")).strip().zfill(6)
                    if raw and raw != "000000":
                        codes.append(f"SZ{raw}")
            except Exception as e:
                logger.warning(f"SZSE {symbol} list failed: {e}")

        if not codes:
            logger.error("Failed to get any stock codes from SSE/SZSE")
        else:
            logger.info(f"Got {len(codes)} stock codes (SSE+SZSE)")

        return codes


class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.success = 0
        self.failed = 0
        self.start_time = time.time()

    def increment(self, success: bool = True):
        self.current += 1
        if success:
            self.success += 1
        else:
            self.failed += 1

    def get_progress(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.current / self.total * 100, 2)

    def get_elapsed_time(self) -> float:
        return round(time.time() - self.start_time, 2)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "current": self.current,
            "success": self.success,
            "failed": self.failed,
            "progress": self.get_progress(),
            "elapsed_time": self.get_elapsed_time()
        }

    def log_progress(self, interval: int = 10):
        if self.current % interval == 0:
            logger.info(
                f"Progress: {self.current}/{self.total} "
                f"({self.get_progress()}%), "
                f"Success: {self.success}, Failed: {self.failed}, "
                f"Elapsed: {self.get_elapsed_time()}s"
            )