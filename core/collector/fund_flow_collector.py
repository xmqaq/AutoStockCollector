"""
资金流向数据采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import akshare as ak
from .base import BaseCollector, ProgressTracker
from core.storage.mongo_storage import FundFlowStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class FundFlowCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = FundFlowStorage()

    def collect(
        self,
        codes: Optional[List[str]] = None,
        period: str = "daily"
    ) -> List[Dict[str, Any]]:
        if codes is None:
            codes = self.get_all_stock_codes()

        all_records = []
        tracker = ProgressTracker(len(codes))

        for code in codes:
            try:
                records = self.execute_with_retry(
                    self.collect_single,
                    code,
                    period=period
                )
                if records:
                    all_records.extend(records)
                    tracker.increment(success=True)
                else:
                    tracker.increment(success=False)
            except Exception as e:
                logger.error(f"Failed to collect fund flow for {code}: {e}")
                tracker.increment(success=False)

            tracker.log_progress(interval=50)

        if all_records:
            self.storage.save_fund_flow_batch(all_records)

        return all_records

    def collect_single(
        self,
        code: str,
        period: str = "daily"
    ) -> Optional[List[Dict[str, Any]]]:
        symbol = code[2:]

        data_sources = [
            ("stock_fund_flow_individual", {"symbol": "即时"}),
            ("stock_main_fund_flow", {}),
            ("stock_individual_fund_flow", {"stock": symbol}),
        ]

        last_error = None
        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                logger.info(f"Trying {source_name} for fund flow")

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is not None and not df.empty:
                    if source_name == "stock_fund_flow_individual":
                        df["code"] = code
                        df["_updated_at"] = datetime.now()
                        return self.normalize_dataframe(df, code)
                    elif "代码" in df.columns:
                        code_data = df[df["代码"].astype(str).str.contains(symbol)]
                        if not code_data.empty:
                            code_data = code_data.copy()
                            code_data["_updated_at"] = datetime.now()
                            return self.normalize_dataframe(code_data, code)

            except Exception as e:
                last_error = e
                logger.warning(f"{source_name} failed: {e}")
                continue

        logger.error(f"All fund flow sources failed, last error: {last_error}")
        return None

    def collect_money_flow(
        self,
        market: str = "all"
    ) -> pd.DataFrame:
        try:
            if market == "all":
                df = ak.stock_market_fund_flow()
            elif market == "sh":
                df = ak.stock_market_fund_flow_individual(indicator="sh")
            else:
                df = ak.stock_market_fund_flow_individual(indicator="sz")

            return df

        except Exception as e:
            logger.error(f"Failed to collect money flow: {e}")
            return pd.DataFrame()

    def collect_sector_flow(self) -> pd.DataFrame:
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="即时")
            return df
        except Exception as e:
            logger.error(f"Failed to collect sector flow: {e}")
            return pd.DataFrame()


class DragonTigerCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import DragonTigerStorage
        self.storage = DragonTigerStorage()

    def collect(
        self,
        date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            df = ak.stock_lhb_stock_statistic_em(symbol="近一月")
            
            if df is None or df.empty:
                return []

            df["date"] = date or end_date or datetime.now().strftime("%Y%m%d")
            df["_updated_at"] = datetime.now()

            records = self.normalize_dataframe(df)
            return records

        except Exception as e:
            logger.error(f"Failed to collect dragon tiger: {e}")
            return []

    def collect_specific_stocks(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        symbol = code[2:]

        try:
            df = ak.stock_lhb_statistic_sina(stock=symbol)

            if df is None or df.empty:
                return []

            df["code"] = code
            df["_updated_at"] = datetime.now()

            return self.normalize_dataframe(df, code)

        except Exception as e:
            logger.error(f"Failed to collect dragon tiger for {code}: {e}")
            return []

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self.collect_specific_stocks(code, kwargs.get("start_date", ""), kwargs.get("end_date", ""))


class MarginCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        from core.storage.mongo_storage import MarginStorage
        self.storage = MarginStorage()

    def collect(self, codes: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        return self.collect_detailed_margin(codes)

    def collect_single(self, code: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        return self._collect_single_margin(code)

    def collect_margin_data(self, date: str) -> pd.DataFrame:
        try:
            df = ak.stock_margin_detail_sz(date=date)
            return df
        except Exception as e:
            logger.error(f"Failed to collect margin data: {e}")
            return pd.DataFrame()

    def collect_margin_summary(self, date: str) -> Optional[Dict[str, Any]]:
        try:
            df = ak.stock_margin(start_date=date, end_date=date)
            if df is None or df.empty:
                return None

            return {
                "date": date,
                "margin_balance": df.iloc[0].get("融资余额", 0),
                "margin_buy": df.iloc[0].get("融资买入额", 0),
                "margin_repay": df.iloc[0].get("融资偿还额", 0),
                "short_balance": df.iloc[0].get("融券余额", 0),
                "short_sell": df.iloc[0].get("融券卖出量", 0),
                "short_repay": df.iloc[0].get("融券偿还量", 0),
                "_updated_at": datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to collect margin summary: {e}")
            return None

    def collect_detailed_margin(
        self,
        codes: Optional[List[str]] = None,
        start_date: str = "20260501",
        end_date: str = "20260527"
    ) -> List[Dict[str, Any]]:
        all_records = []

        try:
            df_sh = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
            if df_sh is not None and not df_sh.empty:
                df_sh["market"] = "sh"
                df_sh["_updated_at"] = datetime.now()
                all_records.extend(df_sh.to_dict("records"))
                logger.info(f"Collected {len(df_sh)} margin records from SSE")
        except Exception as e:
            logger.warning(f"Failed to collect SSE margin: {e}")

        try:
            df_sz = ak.stock_margin_szse(start_date=start_date, end_date=end_date)
            if df_sz is not None and not df_sz.empty:
                df_sz["market"] = "sz"
                df_sz["_updated_at"] = datetime.now()
                all_records.extend(df_sz.to_dict("records"))
                logger.info(f"Collected {len(df_sz)} margin records from SZSE")
        except Exception as e:
            logger.warning(f"Failed to collect SZSE margin: {e}")

        if all_records:
            for record in all_records:
                try:
                    self.storage.save_margin(record)
                except Exception as e:
                    logger.warning(f"Failed to save margin record: {e}")

        return all_records

    def _collect_single_margin(self, code: str) -> List[Dict[str, Any]]:
        symbol = code[2:]
        records = []

        try:
            df = ak.stock_margin_detail_sina(symbol=symbol)
            if df is not None and not df.empty:
                df["code"] = code
                df["_updated_at"] = datetime.now()
                records.extend(self.normalize_dataframe(df, code))
        except Exception as e:
            logger.warning(f"No margin data for {code}: {e}")

        try:
            df_sz = ak.stock_margin_detail_sz(protocol="margin_detail")
            if df_sz is not None and not df_sz.empty:
                code_data = df_sz[df_sz["股票代码"] == symbol]
                if not code_data.empty:
                    code_data = code_data.copy()
                    code_data["code"] = code
                    code_data["_updated_at"] = datetime.now()
                    records.extend(code_data.to_dict("records"))
        except Exception as e:
            logger.warning(f"No SZ margin data for {code}: {e}")

        return records

    def get_margin_ratios(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            klines = self._get_latest_price(code)
            margin_data = self.storage.find_one({"code": code}, sort=[("date", -1)])

            if not margin_data or not klines:
                return None

            market_cap = klines.get("close", 0) * klines.get("volume", 0)

            margin_balance = margin_data.get("margin_balance", 0)
            short_balance = margin_data.get("short_balance", 0)

            margin_ratio = (margin_balance / market_cap * 100) if market_cap > 0 else 0
            short_ratio = (short_balance / market_cap * 100) if market_cap > 0 else 0

            return {
                "code": code,
                "date": margin_data.get("date"),
                "margin_balance": margin_balance,
                "short_balance": short_balance,
                "margin_ratio": round(margin_ratio, 4),
                "short_ratio": round(short_ratio, 4),
                "total_margin": margin_balance + short_balance,
                "total_ratio": round(margin_ratio + short_ratio, 4)
            }
        except Exception as e:
            logger.error(f"Failed to calculate margin ratios: {e}")
            return None

    def _get_latest_price(self, code: str) -> Optional[Dict[str, Any]]:
        from core.storage.mongo_storage import KlineStorage
        storage = KlineStorage()
        return storage.find_one({"code": code}, sort=[("date", -1)])

    def analyze_margin_trend(self, code: str, days: int = 30) -> Dict[str, Any]:
        try:
            records = list(self.storage.find(
                {"code": code}
            ).sort("date", -1).limit(days))

            if len(records) < 5:
                return {"error": "Insufficient data"}

            margin_balances = [r.get("margin_balance", 0) for r in records]
            short_balances = [r.get("short_balance", 0) for r in records]

            margin_trend = "stable"
            if len(margin_balances) >= 2:
                recent_avg = sum(margin_balances[:5]) / min(5, len(margin_balances))
                older_avg = sum(margin_balances[5:10]) / min(5, len(margin_balances[5:]))
                if older_avg > 0:
                    margin_change = (recent_avg - older_avg) / older_avg * 100
                    if margin_change > 10:
                        margin_trend = "increasing"
                    elif margin_change < -10:
                        margin_trend = "decreasing"

            return {
                "code": code,
                "margin_trend": margin_trend,
                "latest_margin_balance": margin_balances[0] if margin_balances else 0,
                "latest_short_balance": short_balances[0] if short_balances else 0,
                "data_points": len(records)
            }
        except Exception as e:
            logger.error(f"Failed to analyze margin trend: {e}")
            return {"error": str(e)}


class BlockCollector(BaseCollector):
    def __init__(self):
        super().__init__()

    def collect_industry_block(self) -> pd.DataFrame:
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            logger.error(f"Failed to collect industry block: {e}")
            return pd.DataFrame()

    def collect_concept_block(self) -> pd.DataFrame:
        try:
            df = ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            logger.error(f"Failed to collect concept block: {e}")
            return pd.DataFrame()

    def collect_block_component(
        self,
        block_code: str,
        block_type: str = "industry"
    ) -> List[Dict[str, Any]]:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_cons_em(symbol=block_code)
            else:
                df = ak.stock_board_concept_cons_em(symbol=block_code)

            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                code = row.get("代码", "")
                if code.startswith("6"):
                    code = f"SH{code}"
                else:
                    code = f"SZ{code}"

                records.append({
                    "code": code,
                    "name": row.get("名称", ""),
                    "block_code": block_code,
                    "block_type": block_type,
                    "_updated_at": datetime.now()
                })

            return records

        except Exception as e:
            logger.error(f"Failed to collect block component: {e}")
            return []

    def collect_block_ranking(self, block_type: str = "industry") -> pd.DataFrame:
        try:
            if block_type == "industry":
                df = ak.stock_board_industry_rank_em()
            else:
                df = ak.stock_board_concept_rank_em()

            return df

        except Exception as e:
            logger.error(f"Failed to collect block ranking: {e}")
            return pd.DataFrame()