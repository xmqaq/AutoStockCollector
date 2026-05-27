"""
股票基础信息采集器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import akshare as ak
from .base import BaseCollector
from core.storage.mongo_storage import StockInfoStorage
from utils.logger import get_logger


logger = get_logger(__name__)


class StockInfoCollector(BaseCollector):
    def __init__(self):
        super().__init__()
        self.storage = StockInfoStorage()

    def collect(
        self,
        codes: Optional[List[str]] = None,
        update_existing: bool = False
    ) -> List[Dict[str, Any]]:
        if codes is None:
            codes = self.get_all_stock_codes()

        all_records = []

        for code in codes:
            try:
                record = self.execute_with_retry(self.collect_single, code)
                if record:
                    all_records.append(record)
                    self.storage.save_stock_info(record)
            except Exception as e:
                logger.error(f"Failed to collect stock info for {code}: {e}")

            if len(all_records) % 100 == 0:
                logger.info(f"Collected {len(all_records)} stock info records")

        logger.info(f"Stock info collection completed: {len(all_records)} records")
        return all_records

    def collect_single(self, code: str) -> Optional[Dict[str, Any]]:
        symbol = code[2:].lower()

        data_sources = [
            ("stock_profile_cninfo", {"symbol": code[2:]}),
            ("stock_individual_info_em", {"symbol": symbol}),
            ("stock_info_a_code_name", None),
        ]

        last_error = None
        for source_name, params in data_sources:
            try:
                func = getattr(ak, source_name, None)
                if func is None:
                    continue

                if params:
                    df = func(**params)
                else:
                    df = func()

                if df is not None and not df.empty:
                    info = {"code": code}

                    if source_name == "stock_individual_info_em":
                        for _, row in df.iterrows():
                            field = row.get("item", "")
                            value = row.get("value", "")
                            field_lower = str(field).lower().replace(" ", "_")
                            info[field_lower] = value
                    elif source_name == "stock_profile_cninfo":
                        for col in df.columns:
                            info[col] = df.iloc[0][col]
                    elif "代码" in df.columns and "名称" in df.columns:
                        stock_row = df[df["代码"].astype(str) == code[2:]]
                        if not stock_row.empty:
                            for col in df.columns:
                                info[col.lower()] = stock_row.iloc[0][col]
                    else:
                        for col in df.columns:
                            info[col.lower()] = df.iloc[0][col]

                    info["_updated_at"] = datetime.now()
                    return info

            except Exception as e:
                last_error = e
                logger.warning(f"{source_name} failed for {code}: {e}")
                continue

        logger.error(f"All stock info sources failed for {code}, last error: {last_error}")
        return None

    def get_stock_basic_info(self, code: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_by_code(code)

    def collect_all_basic_info(self) -> pd.DataFrame:
        try:
            df = ak.stock_info_a_code_name()
            df["code"] = df["code"].apply(self._normalize_code)
            return df
        except Exception as e:
            logger.error(f"Failed to collect all basic info: {e}")
            return pd.DataFrame()

    def get_stocks_by_industry(self, industry: str) -> List[str]:
        try:
            industry_df = ak.stock_board_industry_name_em()

            if industry not in industry_df["板块名称"].values:
                logger.warning(f"Industry {industry} not found")
                return []

            industry_code = industry_df[
                industry_df["板块名称"] == industry
            ]["板块代码"].iloc[0]

            component_df = ak.stock_board_industry_cons_em(symbol=industry_code)

            codes = []
            for _, row in component_df.iterrows():
                code = row["代码"]
                if code.startswith("6"):
                    codes.append(f"SH{code}")
                else:
                    codes.append(f"SZ{code}")

            return codes

        except Exception as e:
            logger.error(f"Failed to get stocks by industry {industry}: {e}")
            return []

    def get_stocks_by_concept(self, concept: str) -> List[str]:
        try:
            concept_df = ak.stock_board_concept_name_em()

            if concept not in concept_df["板块名称"].values:
                logger.warning(f"Concept {concept} not found")
                return []

            concept_code = concept_df[
                concept_df["板块名称"] == concept
            ]["板块代码"].iloc[0]

            component_df = ak.stock_board_concept_cons_em(symbol=concept_code)

            codes = []
            for _, row in component_df.iterrows():
                code = row["代码"]
                if code.startswith("6"):
                    codes.append(f"SH{code}")
                else:
                    codes.append(f"SZ{code}")

            return codes

        except Exception as e:
            logger.error(f"Failed to get stocks by concept {concept}: {e}")
            return []