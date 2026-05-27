"""
数据校验模块
实现时序校验、完整性校验、合法性校验
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from core.storage.mongo_storage import (
    KlineStorage, StockInfoStorage, FinancialStorage, NewsStorage, FundFlowStorage
)
from utils.logger import get_logger
from utils.helpers import get_trading_days, parse_date, format_date


logger = get_logger(__name__)


class ValidationResult:
    def __init__(self, code: str, data_type: str):
        self.code = code
        self.data_type = data_type
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.completeness_score = 100.0

    def add_error(self, message: str):
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def set_completeness(self, score: float):
        self.completeness_score = max(0.0, min(100.0, score))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "data_type": self.data_type,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "completeness_score": self.completeness_score
        }


class DataValidator:
    def __init__(self):
        self.kline_storage = KlineStorage()
        self.stock_info_storage = StockInfoStorage()
        self.financial_storage = FinancialStorage()
        self.news_storage = NewsStorage()
        self.fund_flow_storage = FundFlowStorage()

        self._trading_calendar: Optional[List[str]] = None

    def load_trading_calendar(self, start_date: str, end_date: str):
        self._trading_calendar = get_trading_days(start_date, end_date)

    @property
    def trading_calendar(self) -> List[str]:
        if self._trading_calendar is None:
            today = datetime.now()
            past = (today - timedelta(days=365)).strftime("%Y-%m-%d")
            self._trading_calendar = get_trading_days(past, today.strftime("%Y-%m-%d"))
        return self._trading_calendar

    def validate_kline_data(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> ValidationResult:
        result = ValidationResult(code, "kline")

        records = self.kline_storage.find_many({"code": code})

        if not records:
            result.add_error("No data found")
            result.set_completeness(0.0)
            return result

        if start_date and end_date:
            expected_days = get_trading_days(start_date, end_date)
            expected_set = set(expected_days)

            existing_dates = set(r.get("date") for r in records if r.get("date"))
            missing_dates = expected_set - existing_dates

            if missing_dates:
                result.add_warning(f"Missing {len(missing_dates)} trading days")
                completeness = len(existing_dates) / len(expected_set) * 100
                result.set_completeness(completeness)

        for record in records:
            self._validate_kline_record(record, result)

        return result

    def _validate_kline_record(
        self,
        record: Dict[str, Any],
        result: ValidationResult
    ):
        required_fields = ["open", "high", "low", "close", "volume"]

        for field in required_fields:
            if field not in record or record[field] is None:
                result.add_error(f"Missing required field: {field}")

        if "high" in record and "low" in record:
            if record["high"] < record["low"]:
                result.add_error("High price less than low price")

        if "close" in record:
            if record["close"] <= 0:
                result.add_error(f"Invalid close price: {record['close']}")

        if "volume" in record:
            if record["volume"] < 0:
                result.add_error(f"Invalid volume: {record['volume']}")

    def validate_stock_info(self, code: str) -> ValidationResult:
        result = ValidationResult(code, "stock_info")

        info = self.stock_info_storage.get_by_code(code)

        if not info:
            result.add_error("No stock info found")
            result.set_completeness(0.0)
            return result

        required_fields = ["name", "industry"]

        for field in required_fields:
            if field not in info or not info[field]:
                result.add_warning(f"Missing optional field: {field}")

        result.set_completeness(80.0)
        return result

    def validate_financial_data(
        self,
        code: str,
        report_date: Optional[str] = None
    ) -> ValidationResult:
        result = ValidationResult(code, "financial")

        if report_date:
            record = self.financial_storage.get_by_code_and_period(code, report_date)
            records = [record] if record else []
        else:
            records = self.financial_storage.find_many({"code": code})

        if not records:
            result.add_error("No financial data found")
            result.set_completeness(0.0)
            return result

        result.set_completeness(90.0)
        return result

    def validate_news_data(self, code: Optional[str] = None) -> ValidationResult:
        result = ValidationResult(code or "all", "news")

        filter_doc = {"code": code} if code else {}
        records = self.news_storage.find_many(filter_doc, limit=1000)

        if not records:
            result.add_warning("No news data found")
            result.set_completeness(0.0)
            return result

        today = datetime.now().strftime("%Y-%m-%d")
        recent_count = sum(
            1 for r in records
            if r.get("publish_date", "").startswith(today)
        )

        if recent_count == 0:
            result.add_warning("No news for today")

        result.set_completeness(80.0)
        return result

    def validate_fund_flow(self, code: str) -> ValidationResult:
        result = ValidationResult(code, "fund_flow")

        record = self.fund_flow_storage.get_latest_flow(code)

        if not record:
            result.add_error("No fund flow data found")
            result.set_completeness(0.0)
            return result

        required_fields = ["date", "close", "volume"]

        for field in required_fields:
            if field not in record:
                result.add_warning(f"Missing field: {field}")

        result.set_completeness(80.0)
        return result

    def validate_batch(
        self,
        codes: List[str],
        data_type: str = "kline",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[ValidationResult]:
        results = []

        for code in codes:
            if data_type == "kline":
                result = self.validate_kline_data(code, start_date, end_date)
            elif data_type == "stock_info":
                result = self.validate_stock_info(code)
            elif data_type == "financial":
                result = self.validate_financial_data(code)
            elif data_type == "fund_flow":
                result = self.validate_fund_flow(code)
            else:
                result = ValidationResult(code, data_type)
                result.add_error(f"Unknown data type: {data_type}")

            results.append(result)

        return results

    def check_data_gaps(
        self,
        code: str,
        start_date: str,
        end_date: str,
        data_type: str = "kline"
    ) -> List[str]:
        expected_dates = set(get_trading_days(start_date, end_date))

        if data_type == "kline":
            records = self.kline_storage.find_many({"code": code})
        else:
            return list(expected_dates)

        existing_dates = set()
        for record in records:
            date = record.get("date")
            if date and start_date <= date <= end_date:
                existing_dates.add(date)

        missing_dates = expected_dates - existing_dates
        return sorted(list(missing_dates))

    def get_data_completeness_score(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> float:
        expected_dates = set(get_trading_days(start_date, end_date))
        expected_count = len(expected_dates)

        if expected_count == 0:
            return 100.0

        records = self.kline_storage.find_many({"code": code})
        existing_dates = set()
        for record in records:
            date = record.get("date")
            if date and start_date <= date <= end_date:
                existing_dates.add(date)

        return len(existing_dates) / expected_count * 100

    def generate_validation_report(
        self,
        codes: Optional[List[str]] = None,
        data_type: str = "kline"
    ) -> Dict[str, Any]:
        if codes is None:
            codes = self.kline_storage.distinct("code")

        results = self.validate_batch(codes, data_type)

        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid

        completeness_scores = [r.completeness_score for r in results]
        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0

        all_errors = []
        for r in results:
            all_errors.extend(r.errors)

        error_counts = defaultdict(int)
        for error in all_errors:
            error_type = error.split(":")[0] if ":" in error else error
            error_counts[error_type] += 1

        return {
            "total_codes": total,
            "valid_count": valid,
            "invalid_count": invalid,
            "avg_completeness": round(avg_completeness, 2),
            "error_summary": dict(error_counts),
            "results": [r.to_dict() for r in results[:100]]
        }

    def fix_common_issues(self, code: str, data_type: str = "kline"):
        if data_type == "kline":
            self._fix_kline_duplicates(code)
            self._fix_kline_sequences(code)

    def _fix_kline_duplicates(self, code: str):
        records = self.kline_storage.find_many({"code": code})

        date_count = defaultdict(list)
        for record in records:
            date = record.get("date")
            if date:
                date_count[date].append(record.get("_id"))

        for date, record_ids in date_count.items():
            if len(record_ids) > 1:
                keep_id = record_ids[0]
                for record_id in record_ids[1:]:
                    self.kline_storage.delete_one({"_id": record_id})

                logger.info(f"Fixed duplicate records for {code} on {date}")

    def _fix_kline_sequences(self, code: str):
        records = self.kline_storage.find_many(
            {"code": code},
            sort=[("date", 1)]
        )

        prev_record = None
        for record in records:
            if prev_record and "close" in record and "close" in prev_record:
                close_curr = record["close"]
                close_prev = prev_record["close"]

                if close_curr <= 0 and close_prev > 0:
                    record["close"] = close_prev
                    self.kline_storage.update_one(
                        {"_id": record["_id"]},
                        {"close": close_prev}
                    )

            prev_record = record


class DataIntegrityChecker:
    @staticmethod
    def check_price_sequence(klines: List[Dict[str, Any]]) -> List[str]:
        errors = []

        for kline in klines:
            if kline.get("high", 0) < kline.get("low", 0):
                errors.append(f"High < Low on {kline.get('date')}")

        for i in range(1, len(klines)):
            curr = klines[i]
            prev = klines[i - 1]

            if curr["high"] < prev["high"] and curr["high"] < curr["close"]:
                errors.append(f"Abnormal high on {curr.get('date')}")

        return errors

    @staticmethod
    def check_volume_anomaly(klines: List[Dict[str, Any]], threshold: float = 10.0) -> List[str]:
        errors = []

        if len(klines) < 2:
            return errors

        volumes = [k.get("volume", 0) for k in klines]
        avg_volume = sum(volumes) / len(volumes)

        for kline in klines:
            volume = kline.get("volume", 0)
            if avg_volume > 0 and volume > avg_volume * threshold:
                errors.append(f"Volume anomaly on {kline.get('date')}: {volume}")

        return errors

    @staticmethod
    def check_price_jump(
        klines: List[Dict[str, Any]],
        threshold: float = 20.0
    ) -> List[str]:
        errors = []

        for i in range(1, len(klines)):
            curr = klines[i]
            prev = klines[i - 1]

            curr_close = curr.get("close", 0)
            prev_close = prev.get("close", 0)

            if prev_close > 0:
                change_pct = abs(curr_close - prev_close) / prev_close * 100

                if change_pct > threshold:
                    errors.append(
                        f"Price jump on {curr.get('date')}: {change_pct:.2f}%"
                    )

        return errors