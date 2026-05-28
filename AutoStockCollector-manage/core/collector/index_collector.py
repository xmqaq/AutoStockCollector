"""
指数成分股权重采集器
采集沪深300、中证500、上证50等主流指数成分股权重数据
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import akshare as ak
from .base import BaseCollector
from config.database import get_collection
from utils.logger import get_logger


logger = get_logger(__name__)


class IndexCollector:
    def __init__(self):
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = get_collection("index_components")
        return self._collection

    def collect(
        self,
        index_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if index_codes is None:
            index_codes = [
                "000300",
                "000905",
                "000016",
                "000001",
                "399001",
                "399006",
            ]

        results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }

        for index_code in index_codes:
            try:
                success = self._collect_index_components(index_code)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["total"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{index_code}: {str(e)}")
                logger.error(f"Failed to collect index {index_code}: {e}")

        return results

    def collect_single(self, code: str, **kwargs) -> Optional[Dict[str, Any]]:
        """采集单个指数的成分股权重，成功后返回汇总信息"""
        success = self._collect_index_components(code)
        if not success:
            return None
        components = self.get_index_components(code)
        return {
            "index_code": code,
            "component_count": len(components),
            "updated_at": datetime.now().isoformat(),
        }

    def _collect_index_components(self, index_code: str) -> bool:
        try:
            df = ak.index_stock_cons_csindex(symbol=index_code)
            if df is None or df.empty:
                logger.warning(f"No components found for index {index_code}")
                return False

            records = []
            for _, row in df.iterrows():
                record = self._parse_row(row, index_code)
                records.append(record)

            if records:
                logger.info(f"Collected {len(records)} components for index {index_code}")
                try:
                    self.collection.update_many(
                        {"index_code": index_code},
                        {"$set": {"updated_at": datetime.now()}},
                    )
                    self.collection.delete_many({"index_code": index_code})
                    self.collection.insert_many(records)
                except Exception as db_err:
                    logger.warning(f"Failed to save index {index_code} to MongoDB: {db_err}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to collect components for {index_code}: {e}")
            return False

    def _parse_row(self, row, index_code: str) -> Dict[str, Any]:
        return {
            "index_code": index_code,
            "stock_code": self._normalize_stock_code(row.get("品种代码", "")),
            "stock_name": row.get("品种名称", ""),
            "weight": self._parse_weight(row.get("权重", "0")),
            "updated_at": datetime.now()
        }

    def _normalize_stock_code(self, code: str) -> str:
        code = str(code).strip().upper()
        if not code.startswith(("SH", "SZ")):
            if code.startswith("6"):
                code = "SH" + code
            else:
                code = "SZ" + code
        return code

    def _parse_weight(self, weight_str: str) -> float:
        try:
            return float(weight_str.replace("%", "").strip())
        except (ValueError, AttributeError):
            return 0.0

    def collect_sse_index_components(self) -> List[Dict[str, Any]]:
        try:
            df = ak.index_stock_info(symbol="000001")
            return self._dataframe_to_records(df)
        except Exception as e:
            logger.error(f"Failed to collect SSE index: {e}")
            return []

    def collect_szse_index_components(self) -> List[Dict[str, Any]]:
        try:
            df = ak.index_stock_info(symbol="399001")
            return self._dataframe_to_records(df)
        except Exception as e:
            logger.error(f"Failed to collect SZSE index: {e}")
            return []

    def _dataframe_to_records(self, df) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            records.append(row.to_dict())

        return records

    def get_index_components(self, index_code: str) -> List[Dict[str, Any]]:
        try:
            return list(self.collection.find({"index_code": index_code}))
        except Exception as e:
            logger.error(f"Failed to get components for {index_code}: {e}")
            return []

    def get_stock_indices(self, stock_code: str) -> List[str]:
        try:
            records = self.collection.find({"stock_code": stock_code})
            return [r.get("index_code") for r in records]
        except Exception as e:
            logger.error(f"Failed to get indices for {stock_code}: {e}")
            return []

    def get_stock_weight_in_index(
        self,
        stock_code: str,
        index_code: str
    ) -> Optional[float]:
        try:
            record = self.collection.find_one({
                "stock_code": stock_code,
                "index_code": index_code
            })
            return record.get("weight") if record else None
        except Exception as e:
            logger.error(f"Failed to get weight: {e}")
            return None

    def get_top_holdings(
        self,
        index_code: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            records = self.collection.find(
                {"index_code": index_code}
            ).sort("weight", -1).limit(limit)
            return list(records)
        except Exception as e:
            logger.error(f"Failed to get top holdings: {e}")
            return []

    def sync_index_weights(self) -> Dict[str, int]:
        results = {"success": 0, "failed": 0}

        index_codes = [
            "000300", "000905", "000016",
            "000001", "399001", "399006"
        ]

        for code in index_codes:
            try:
                if self._collect_index_components(code):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception:
                results["failed"] += 1

        return results


index_collector = IndexCollector()