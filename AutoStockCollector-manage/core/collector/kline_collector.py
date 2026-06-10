"""
K线行情数据采集器
支持日线、周线、月线及分时数据采集
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from utils.helpers import beijing_now
import pandas as pd
import akshare as ak
from .base import BaseCollector, ProgressTracker
from core.storage.mongo_storage import KlineStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class KlineCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = KlineStorage()

    def collect(
        self,
        codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
        period: str = "daily"
    ) -> List[Dict[str, Any]]:
        if not codes:
            codes = self.get_all_stock_codes()
            if not codes:
                logger.warning("No stock codes available for collection")
                return []

        seen_codes = set()
        unique_codes = []
        for code in codes:
            code_normalized = self._normalize_code(code)
            if code_normalized not in seen_codes:
                seen_codes.add(code_normalized)
                unique_codes.append(code_normalized)

        logger.info(f"Starting kline collection for {len(unique_codes)} unique stocks")

        all_records = []
        tracker = ProgressTracker(len(unique_codes))

        for i, code in enumerate(unique_codes):
            try:
                records = self.execute_with_retry(
                    self.collect_single,
                    code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                    period=period
                )
                if records:
                    all_records.extend(records)
                    tracker.increment(success=True)
                else:
                    tracker.increment(success=False)
            except Exception as e:
                logger.error(f"Failed to collect kline for {code}: {e}")
                tracker.increment(success=False)

            tracker.log_progress(interval=50)

        if all_records:
            success, failed = self.storage.save_kline_batch(all_records)
            logger.info(
                f"Kline collection completed: {success} saved, {failed} failed, "
                f"total records: {len(all_records)}"
            )

        return all_records

    def collect_single(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
        period: str = "daily",
        prefer_source: str = "auto"
    ) -> Optional[List[Dict[str, Any]]]:
        if not code:
            logger.error("Stock code cannot be empty")
            return None

        code = self._normalize_code(code)
        symbol = code.lower()

        period_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "minute": "60"
        }
        akshare_period = period_map.get(period, "daily")

        if adjust not in ("qfq", "hfq", "none"):
            logger.warning(f"Invalid adjust parameter: {adjust}, using 'qfq'")
            adjust = "qfq"

        try:
            if end_date is None:
                end_date = beijing_now().strftime("%Y%m%d")
            else:
                end_date = end_date.replace("-", "")

            if start_date is None:
                start_date = (beijing_now() - timedelta(days=365)).strftime("%Y%m%d")
            else:
                start_date = start_date.replace("-", "")

            if start_date > end_date:
                logger.warning(f"start_date {start_date} > end_date {end_date}, swapping")
                start_date, end_date = end_date, start_date

            df = self._collect_with_multi_source(symbol, start_date, end_date, adjust, akshare_period)

            if df is None or df.empty:
                logger.warning(f"No data returned for {code} in date range {start_date}-{end_date}")
                return None

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect kline for {code}: {e}")
            return None

    def _collect_with_multi_source(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
        period: str = "daily",
        max_retries: int = 2
    ):
        data_sources = [
            ("stock_zh_a_hist_tx", "腾讯财经"),
            ("stock_zh_a_daily", "新浪财经"),
            ("stock_zh_a_hist", "东方财富"),   # 东财代理不稳定，放最后兜底
        ]

        last_error = None
        for source_name, source_desc in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_desc} ({source_name}) for {symbol}")

                if source_name == "stock_zh_a_hist_tx":
                    df = ak.stock_zh_a_hist_tx(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust
                    )
                elif source_name == "stock_zh_a_hist":
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust
                    )
                elif source_name == "stock_zh_a_daily":
                    df = ak.stock_zh_a_daily(
                        symbol=symbol,
                        adjust=adjust
                    )
                    # 该接口返回英文列名 date（YYYY-MM-DD），与入参 start/end（YYYYMMDD）
                    # 格式不同，需统一为 YYYYMMDD 再比较，否则筛选恒为空甚至抛 KeyError
                    if df is not None and not df.empty:
                        date_col = "date" if "date" in df.columns else (
                            "日期" if "日期" in df.columns else None
                        )
                        if date_col is not None:
                            d = df[date_col].astype(str).str.replace("-", "", regex=False)
                            df = df[(d >= start_date) & (d <= end_date)]
                else:
                    continue

                if df is not None and not df.empty:
                    logger.info(f"Successfully retrieved data from {source_desc} for {symbol}")
                    return df

            except Exception as e:
                last_error = e
                logger.warning(f"{source_desc} failed for {symbol}: {e}")
                continue

        logger.error(f"All data sources failed for {symbol}, last error: {last_error}")
        return None

    def collect_incremental(
        self,
        code: str,
        adjust: str = "qfq"
    ) -> Optional[List[Dict[str, Any]]]:
        latest_date = self.storage.get_latest_date(code)

        if latest_date:
            start_date = (datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
        else:
            start_date = (beijing_now() - timedelta(days=365)).strftime("%Y%m%d")

        return self.collect_single(
            code,
            start_date=start_date,
            end_date=None,
            adjust=adjust
        )

    def collect_batch_incremental(
        self,
        codes: List[str],
        adjust: str = "qfq",
        batch_size: int = 50
    ) -> Dict[str, Any]:
        all_records = []
        total_success = 0
        total_failed = 0

        for i in range(0, len(codes), batch_size):
            batch_codes = codes[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}")

            for code in batch_codes:
                try:
                    records = self.collect_incremental(code, adjust)
                    if records:
                        all_records.extend(records)
                        total_success += 1
                    else:
                        total_failed += 1
                except Exception as e:
                    logger.error(f"Failed incremental collect for {code}: {e}")
                    total_failed += 1

        if all_records:
            success, failed = self.storage.save_kline_batch(all_records)
            return {
                "total_codes": len(codes),
                "success": total_success,
                "failed": total_failed,
                "records_saved": success
            }

        return {
            "total_codes": len(codes),
            "success": total_success,
            "failed": total_failed,
            "records_saved": 0
        }

    def get_realtime_quote(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            exchange = "sh" if code.startswith("SH") else "sz"
            symbol = code.lower()

            df = ak.stock_zh_a_spot_em()

            code_num = code[2:]
            row = df[df["代码"] == code_num]

            if row.empty:
                return None

            return {
                "code": code,
                "name": row.iloc[0]["名称"],
                "price": row.iloc[0]["最新价"],
                "change": row.iloc[0]["涨跌幅"],
                "volume": row.iloc[0]["成交量"],
                "amount": row.iloc[0]["成交额"],
                "_updated_at": beijing_now()
            }

        except Exception as e:
            logger.error(f"Failed to get realtime quote for {code}: {e}")
            return None


class IndexKlineCollector(KlineCollector):
    def collect_single(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily"
    ) -> Optional[List[Dict[str, Any]]]:
        symbol = code.lower()

        try:
            if end_date is None:
                end_date = beijing_now().strftime("%Y%m%d")
            if start_date is None:
                start_date = (beijing_now() - timedelta(days=365)).strftime("%Y%m%d")

            df = ak.stock_zh_index_daily(symbol=symbol)

            if start_date:
                df = df[df["日期"] >= start_date]
            if end_date:
                df = df[df["日期"] <= end_date]

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect index kline for {code}: {e}")
            return None


class FundKlineCollector(KlineCollector):
    def collect_single(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq"
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            if end_date is None:
                end_date = beijing_now().strftime("%Y%m%d")
            if start_date is None:
                start_date = (beijing_now() - timedelta(days=365)).strftime("%Y%m%d")

            df = ak.fund_open_fund_info_em(
                fund=code,
                indicator="单位净值走势"
            )

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect fund kline for {code}: {e}")
            return None