"""
财务报表数据采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import akshare as ak
from .base import BaseCollector
from core.storage.mongo_storage import FinancialStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class FinancialCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = FinancialStorage()

    def collect(
        self,
        codes: Optional[List[str]] = None,
        report_type: str = "annual",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if codes is None:
            codes = self.get_all_stock_codes()

        if end_year is None:
            end_year = datetime.now().year
        if start_year is None:
            start_year = end_year - 5

        all_records = []

        for code in codes:
            try:
                records = self.execute_with_retry(
                    self.collect_single,
                    code,
                    report_type=report_type,
                    start_year=start_year,
                    end_year=end_year
                )
                if records:
                    all_records.extend(records)
                    self.storage.save_financial_batch(records)
            except Exception as e:
                logger.error(f"Failed to collect financial for {code}: {e}")

            if len(all_records) % 500 == 0:
                logger.info(f"Collected {len(all_records)} financial records")

        logger.info(f"Financial collection completed: {len(all_records)} records")
        return all_records

    def collect_single(
        self,
        code: str,
        report_type: str = "annual",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        symbol = code[2:]

        prefix = "sh" if code.startswith("SH") else "sz"
        stock_param = f"{prefix}{symbol}"

        data_sources = [
            ("stock_financial_report_sina", {"stock": stock_param, "symbol": "资产负债表"}),
            ("stock_financial_report_sina", {"stock": stock_param, "symbol": "利润表"}),
            ("stock_financial_report_sina", {"stock": stock_param, "symbol": "现金流量表"}),
            ("stock_yysj_em", {"symbol": symbol}),  # 东财兜底，优先级最低
        ]

        last_error = None
        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for {code}")

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is None or df.empty:
                    continue

                df["code"] = code

                if "报告日" in df.columns:
                    df["report_date"] = pd.to_datetime(df["报告日"]).dt.strftime("%Y-%m-%d")
                elif "报告日期" in df.columns:
                    df["report_date"] = pd.to_datetime(df["报告日期"]).dt.strftime("%Y-%m-%d")

                df["_updated_at"] = datetime.now()
                return self.normalize_dataframe(df, code)

            except Exception as e:
                last_error = e
                logger.warning(f"{source_name} failed for {code}: {e}")
                continue

        logger.error(f"All financial sources failed for {code}, last error: {last_error}")
        return None

    def collect_balance_sheet(self, code: str, symbol: str = "") -> Optional[pd.DataFrame]:
        if not symbol:
            symbol = code[2:]

        try:
            df = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to collect balance sheet for {code}: {e}")
            return None

    def collect_profit_statement(self, code: str, symbol: str = "") -> Optional[pd.DataFrame]:
        if not symbol:
            symbol = code[2:]

        try:
            df = ak.stock_profit_sheet_by_report_em(symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to collect profit statement for {code}: {e}")
            return None

    def collect_cash_flow(self, code: str, symbol: str = "") -> Optional[pd.DataFrame]:
        if not symbol:
            symbol = code[2:]

        try:
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"Failed to collect cash flow for {code}: {e}")
            return None

    def collect_ipo_info(self, code: str) -> Optional[Dict[str, Any]]:
        symbol = code[2:]

        try:
            df = ak.stock_ipo_summary_cninfo(symbol=symbol)
            if df is None or df.empty:
                return None

            info = {"code": code}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]

            info["_updated_at"] = datetime.now()

            return info

        except Exception as e:
            logger.error(f"Failed to collect IPO info for {code}: {e}")
            return None


class DividendCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect(self, codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if codes is None:
            codes = self.get_all_stock_codes()

        all_records = []

        for code in codes:
            try:
                records = self.execute_with_retry(self.collect_single, code)
                if records:
                    all_records.extend(records)
            except Exception as e:
                logger.error(f"Failed to collect dividend for {code}: {e}")

        return all_records

    def collect_single(self, code: str) -> Optional[List[Dict[str, Any]]]:
        symbol = code[2:]

        try:
            df = ak.stock_dividend_detail(symbol=symbol)
            if df is None or df.empty:
                return None

            df["code"] = code
            df["_updated_at"] = datetime.now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect dividend for {code}: {e}")
            return None