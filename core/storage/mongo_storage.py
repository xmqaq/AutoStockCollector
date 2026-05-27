"""
MongoDB 数据存储模块
提供统一的数据写入、查询、更新操作
"""
import time
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
import pandas as pd
from pymongo import UpdateOne, InsertOne, DeleteOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, DuplicateKeyError
from config.database import DatabaseConfig
from utils.logger import get_logger
from utils.helpers import chunk_list


logger = get_logger(__name__)


class MongoStorage:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = DatabaseConfig.get_collection(self.collection_name)
        return self._collection

    def insert_one(self, document: Dict[str, Any]) -> str:
        try:
            result = self.collection.insert_one(document)
            logger.debug(f"Inserted document with _id: {result.inserted_id}")
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Duplicate document found: {document.get('code', 'unknown')}")
            return ""

    def insert_many(
        self,
        documents: List[Dict[str, Any]],
        ordered: bool = False,
        chunk_size: int = 1000
    ) -> Tuple[int, int]:
        if not documents:
            return (0, 0)

        success_count = 0
        error_count = 0

        for chunk in chunk_list(documents, chunk_size):
            try:
                result = self.collection.insert_many(chunk, ordered=ordered)
                success_count += len(result.inserted_ids)
            except BulkWriteError as e:
                success_count += e.details.get("nInserted", 0)
                error_count += e.details.get("nErrored", 0)
                logger.warning(f"Bulk write errors: {e.details.get('writeErrors', [])}")
            except Exception as e:
                error_count += len(chunk)
                logger.error(f"Batch insert failed: {e}")

        logger.info(
            f"Batch insert completed: {success_count} succeeded, {error_count} failed"
        )
        return (success_count, error_count)

    def upsert_one(
        self,
        filter_doc: Dict[str, Any],
        update_doc: Dict[str, Any],
        set_on_insert: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            update = {"$set": update_doc}
            if set_on_insert:
                update["$setOnInsert"] = set_on_insert

            result = self.collection.update_one(
                filter_doc,
                update,
                upsert=True
            )

            if result.upserted_id:
                logger.debug(f"Upserted document with _id: {result.upserted_id}")
            return True

        except Exception as e:
            logger.error(f"Upsert failed: {e}")
            return False

    def upsert_many(
        self,
        documents: List[Dict[str, Any]],
        key_fields: List[str]
    ) -> Tuple[int, int]:
        if not documents:
            return (0, 0)

        operations = []
        for doc in documents:
            filter_doc = {k: doc[k] for k in key_fields if k in doc}
            update_doc = {k: v for k, v in doc.items() if k not in key_fields}
            update_doc["_updated_at"] = datetime.now()

            operations.append(
                UpdateOne(
                    filter_doc,
                    {"$set": update_doc},
                    upsert=True
                )
            )

        try:
            result = self.collection.bulk_write(operations, ordered=False)
            logger.info(
                f"Bulk upsert completed: {result.upserted_count} upserted, "
                f"{result.modified_count} modified"
            )
            return (result.upserted_count, result.modified_count)
        except BulkWriteError as e:
            logger.warning(f"Bulk write partially failed: {e.details}")
            return (e.details.get("nUpserted", 0), e.details.get("nModified", 0))
        except Exception as e:
            logger.error(f"Bulk upsert failed: {e}")
            return (0, 0)

    def update_one(
        self,
        filter_doc: Dict[str, Any],
        update_doc: Dict[str, Any],
        upsert: bool = False
    ) -> int:
        try:
            result = self.collection.update_one(filter_doc, {"$set": update_doc}, upsert=upsert)
            return result.modified_count
        except Exception as e:
            logger.error(f"Update one failed: {e}")
            return 0

    def update_many(
        self,
        filter_doc: Dict[str, Any],
        update_doc: Dict[str, Any]
    ) -> int:
        try:
            result = self.collection.update_many(filter_doc, {"$set": update_doc})
            logger.info(f"Updated {result.modified_count} documents")
            return result.modified_count
        except Exception as e:
            logger.error(f"Update many failed: {e}")
            return 0

    def find_one(
        self,
        filter_doc: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, int]] = None,
        sort: Optional[List[Tuple[str, int]]] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.collection.find(filter_doc or {}, projection)
            if sort:
                cursor = cursor.sort(sort)
            count = self.collection.count_documents(filter_doc or {})
            return cursor.next() if count > 0 else None
        except StopIteration:
            return None
        except Exception as e:
            logger.error(f"Find one failed: {e}")
            return None

    def find_many(
        self,
        filter_doc: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, int]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 0,
        batch_size: int = 1000
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.collection.find(filter_doc or {}, projection)

            if sort:
                cursor = cursor.sort(sort)

            cursor = cursor.skip(skip)

            if limit > 0:
                cursor = cursor.limit(limit)
            else:
                cursor = cursor.batch_size(batch_size)

            return list(cursor)

        except Exception as e:
            logger.error(f"Find many failed: {e}")
            return []

    def count_documents(
        self,
        filter_doc: Optional[Dict[str, Any]] = None
    ) -> int:
        try:
            return self.collection.count_documents(filter_doc or {})
        except Exception as e:
            logger.error(f"Count documents failed: {e}")
            return 0

    def delete_one(self, filter_doc: Dict[str, Any]) -> bool:
        try:
            result = self.collection.delete_one(filter_doc)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Delete one failed: {e}")
            return False

    def delete_many(self, filter_doc: Dict[str, Any]) -> int:
        try:
            result = self.collection.delete_many(filter_doc)
            logger.info(f"Deleted {result.deleted_count} documents")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Delete many failed: {e}")
            return 0

    def aggregate(
        self,
        pipeline: List[Dict[str, Any]],
        allow_disk_use: bool = True
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.collection.aggregate(
                pipeline,
                allowDiskUse=allow_disk_use
            )
            return list(cursor)
        except Exception as e:
            logger.error(f"Aggregate failed: {e}")
            return []

    def distinct(
        self,
        field: str,
        filter_doc: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        try:
            return self.collection.distinct(field, filter_doc or {})
        except Exception as e:
            logger.error(f"Distinct failed: {e}")
            return []

    def create_index(
        self,
        keys: Union[str, List[Tuple[str, int]]],
        unique: bool = False,
        sparse: bool = False,
        name: Optional[str] = None
    ) -> str:
        try:
            index_name = self.collection.create_index(
                keys,
                unique=unique,
                sparse=sparse,
                name=name
            )
            logger.info(f"Created index: {index_name}")
            return index_name
        except Exception as e:
            logger.error(f"Create index failed: {e}")
            return ""

    def drop_index(self, name: str) -> bool:
        try:
            self.collection.drop_index(name)
            logger.info(f"Dropped index: {name}")
            return True
        except Exception as e:
            logger.error(f"Drop index failed: {e}")
            return False

    def query_by_date_range(
        self,
        code: str,
        date_field: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        if not code:
            logger.error("Code cannot be empty in query_by_date_range")
            return []

        if not start_date or not end_date:
            logger.error("start_date and end_date are required")
            return []

        try:
            if start_date > end_date:
                logger.warning(f"start_date {start_date} > end_date {end_date}, swapping")
                start_date, end_date = end_date, start_date
        except TypeError:
            pass

        filter_doc = {
            "code": code,
            date_field: {
                "$gte": start_date,
                "$lte": end_date
            }
        }
        return self.find_many(filter_doc, sort=[(date_field, -1)])

    def get_latest_record(
        self,
        filter_doc: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        cursor = self.collection.find(filter_doc).sort("_updated_at", -1).limit(1)
        result = list(cursor)
        return result[0] if result else None

    def get_earliest_record(
        self,
        filter_doc: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        cursor = self.collection.find(filter_doc).sort("_updated_at", 1).limit(1)
        result = list(cursor)
        return result[0] if result else None

    def get_records_count_by_date(
        self,
        date: str,
        date_field: str = "date"
    ) -> int:
        return self.count_documents({date_field: date})

    def to_dataframe(
        self,
        filter_doc: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        limit: int = 0
    ) -> pd.DataFrame:
        records = self.find_many(filter_doc, sort=sort, limit=limit)

        if not records:
            return pd.DataFrame()

        for record in records:
            record.pop("_id", None)
            record.pop("_updated_at", None)

        return pd.DataFrame(records)

    def bulk_write(
        self,
        operations: List[Any]
    ) -> Dict[str, int]:
        try:
            result = self.collection.bulk_write(operations, ordered=False)
            return {
                "inserted": result.inserted_count,
                "updated": result.modified_count,
                "upserted": getattr(result, "upserted_count", 0),
                "deleted": result.deleted_count
            }
        except BulkWriteError as e:
            return {
                "inserted": e.details.get("nInserted", 0),
                "updated": e.details.get("nModified", 0),
                "upserted": e.details.get("nUpserted", 0),
                "deleted": e.details.get("nDeleted", 0),
                "errors": len(e.details.get("writeErrors", []))
            }
        except Exception as e:
            logger.error(f"Bulk write failed: {e}")
            return {"error": str(e)}


class KlineStorage(MongoStorage):
    def __init__(self):
        super().__init__("kline")

    def get_latest_date(self, code: str) -> Optional[str]:
        record = self.find_one(
            {"code": code},
            sort=[("date", -1)]
        )
        return record.get("date") if record else None

    def get_earliest_date(self, code: str) -> Optional[str]:
        record = self.find_one(
            {"code": code},
            sort=[("date", 1)]
        )
        return record.get("date") if record else None

    def get_kline_range(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        latest = self.get_latest_date(code)
        earliest = self.get_earliest_date(code)
        return (earliest, latest)

    def save_kline_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.upsert_many(records, ["code", "date"])


class StockInfoStorage(MongoStorage):
    def __init__(self):
        super().__init__("stock_info")

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"code": code})

    def save_stock_info(self, info: Dict[str, Any]) -> bool:
        info["_updated_at"] = datetime.now()
        return self.upsert_one({"code": info["code"]}, info)


class FinancialStorage(MongoStorage):
    def __init__(self):
        super().__init__("financial")

    def get_by_code_and_period(
        self,
        code: str,
        report_date: str
    ) -> Optional[Dict[str, Any]]:
        return self.find_one({
            "code": code,
            "report_date": report_date
        })

    def save_financial_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.upsert_many(records, ["code", "report_date"])


class NewsStorage(MongoStorage):
    def __init__(self):
        super().__init__("news")

    def get_latest_news(
        self,
        code: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        filter_doc = {"code": code} if code else {}
        return self.find_many(
            filter_doc,
            sort=[("publish_date", -1)],
            limit=limit
        )

    def save_news(self, news: Dict[str, Any]) -> str:
        if "title" in news and "publish_date" in news:
            return self.upsert_one(
                {"title": news["title"], "publish_date": news["publish_date"]},
                news
            )
        return self.insert_one(news)

    def save_news_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.insert_many(records)


class FundFlowStorage(MongoStorage):
    def __init__(self):
        super().__init__("fund_flow")

    def get_latest_flow(self, code: str) -> Optional[Dict[str, Any]]:
        return self.find_one(
            {"code": code},
            sort=[("date", -1)]
        )

    def save_fund_flow_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.upsert_many(records, ["code", "date"])


class TaskStorage(MongoStorage):
    def __init__(self):
        super().__init__("task")

    def create_task(
        self,
        task_id: str,
        task_type: str,
        params: Dict[str, Any]
    ) -> str:
        task_doc = {
            "task_id": task_id,
            "task_type": task_type,
            "params": params,
            "status": "pending",
            "progress": 0,
            "total": 0,
            "success": 0,
            "failed": 0,
            "create_time": datetime.now(),
            "update_time": datetime.now()
        }
        return self.insert_one(task_doc)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        **kwargs
    ) -> bool:
        update_doc = {
            "status": status,
            "update_time": datetime.now()
        }
        update_doc.update(kwargs)
        return self.update_one({"task_id": task_id}, update_doc) > 0

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.find_one({"task_id": task_id})

    def get_pending_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.find_many(
            {"status": "pending"},
            sort=[("create_time", 1)],
            limit=limit
        )

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        return self.find_many({"status": "running"})


class WatchlistStorage(MongoStorage):
    def __init__(self):
        super().__init__("watchlist")

    def add_stock(
        self,
        user_id: str,
        code: str,
        group_id: str = "default",
        priority: int = 0
    ) -> bool:
        doc = {
            "user_id": user_id,
            "code": code,
            "group_id": group_id,
            "priority": priority,
            "add_time": datetime.now(),
            "enabled": True
        }
        return self.upsert_one(
            {"user_id": user_id, "code": code},
            doc
        )

    def remove_stock(self, user_id: str, code: str) -> bool:
        return self.delete_one({"user_id": user_id, "code": code})

    def get_user_watchlist(
        self,
        user_id: str,
        group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        filter_doc = {"user_id": user_id, "enabled": True}
        if group_id:
            filter_doc["group_id"] = group_id
        return self.find_many(filter_doc)

    def update_stock_priority(
        self,
        user_id: str,
        code: str,
        priority: int
    ) -> bool:
        return self.update_one(
            {"user_id": user_id, "code": code},
            {"priority": priority}
        ) > 0


class BlockStorage(MongoStorage):
    def __init__(self):
        super().__init__("block")

    def save_block(self, block: Dict[str, Any]) -> str:
        if "code" in block and "block_type" in block:
            filter_doc = {"code": block["code"], "block_type": block["block_type"]}
            return self.upsert_one(filter_doc, block)
        return self.insert_one(block)

    def get_block_by_code(self, code: str, block_type: str = "industry") -> Optional[Dict[str, Any]]:
        return self.find_one({"code": code, "block_type": block_type})

    def get_blocks_by_type(self, block_type: str) -> List[Dict[str, Any]]:
        return self.find_many({"block_type": block_type})


class DragonTigerStorage(MongoStorage):
    def __init__(self):
        super().__init__("dragon_tiger")

    def save_daily_rank(self, rank: Dict[str, Any]) -> str:
        if "code" in rank and "date" in rank:
            filter_doc = {"code": rank["code"], "date": rank["date"]}
            return self.upsert_one(filter_doc, rank)
        return self.insert_one(rank)

    def get_rank_by_date(self, date: str) -> List[Dict[str, Any]]:
        return self.find_many({"date": date}, sort=[("涨跌幅", -1)])

    def get_rank_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self.find_one(
            {"code": code},
            sort=[("date", -1)]
        )


class MarginStorage(MongoStorage):
    def __init__(self):
        super().__init__("margin_data")

    def save_margin(self, margin: Dict[str, Any]) -> str:
        if "信用交易日期" in margin and "market" in margin:
            filter_doc = {"信用交易日期": margin["信用交易日期"], "market": margin["market"]}
            return self.upsert_one(filter_doc, margin)
        return self.insert_one(margin)

    def get_latest_margin(self, market: str = "sh") -> Optional[Dict[str, Any]]:
        return self.find_one(
            {"market": market},
            sort=[("信用交易日期", -1)]
        )

    def save_margin_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.insert_many(records)