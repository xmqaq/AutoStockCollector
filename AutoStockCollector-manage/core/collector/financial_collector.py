"""
财务报表数据采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.helpers import beijing_now
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
            end_year = beijing_now().year
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
        end_year: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        symbol = code[2:]  # 去掉 SH/SZ 前缀，THS 只要纯数字代码

        # 从 start_date/end_date 推导年份范围
        if start_date and start_year is None:
            start_year = int(start_date[:4])
        if end_date and end_year is None:
            end_year = int(end_date[:4])
        if end_year is None:
            end_year = beijing_now().year
        if start_year is None:
            start_year = end_year - 5

        try:
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is None or df.empty:
                logger.warning(f"stock_financial_abstract_ths returned empty for {code}")
                return None

            df = df.copy()
            # 报告期列名兼容
            date_col = "报告期" if "报告期" in df.columns else df.columns[0]
            df["report_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["report_date"])

            # 按年份过滤
            df = df[
                (df["report_date"] >= f"{start_year}-01-01") &
                (df["report_date"] <= f"{end_year}-12-31")
            ]
            if df.empty:
                return None

            df["code"] = code
            df["report_type"] = report_type
            df["_updated_at"] = beijing_now()

            records = self.normalize_dataframe(df, code)
            logger.debug(f"{code}: {len(records)} financial records ({start_year}~{end_year})")
            return records if records else None

        except Exception as e:
            logger.error(f"stock_financial_abstract_ths failed for {code}: {e}")
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

            info["_updated_at"] = beijing_now()

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
            df["_updated_at"] = beijing_now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect dividend for {code}: {e}")
            return None