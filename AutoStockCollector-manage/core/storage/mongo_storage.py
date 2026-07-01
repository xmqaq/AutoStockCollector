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
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure
from config.database import DatabaseConfig
from utils.logger import get_logger
from utils.helpers import chunk_list, beijing_now


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
            update_doc["_updated_at"] = beijing_now()

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
            if sort:
                return self.collection.find(filter_doc or {}, projection).sort(sort).limit(1).next()
            return self.collection.find_one(filter_doc or {}, projection)
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
        except OperationFailure as e:
            # code 86 IndexKeySpecsConflict: 同名索引已存在但规格不同（如已建 unique，
            # 本次请求非 unique）。索引已存在即数据完整性已保证，重建无意义，静默降级。
            # 其他 OperationFailure 仍记 ERROR。
            if e.code == 86:
                logger.debug(f"Index already exists with conflicting spec (skipped): {e}")
                return ""
            logger.error(f"Create index failed: {e}")
            return ""
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

        # 将字符串日期转为 datetime，兼容 MongoDB 中存储为 datetime 的字段
        from datetime import datetime as _dt
        def _to_dt(s):
            if isinstance(s, _dt):
                return s
            try:
                return _dt.strptime(s[:10], "%Y-%m-%d")
            except Exception:
                return s

        filter_doc = {
            "code": code,
            date_field: {
                "$gte": _to_dt(start_date),
                "$lte": _to_dt(end_date)
            }
        }
        return self.find_many(filter_doc, sort=[(date_field, 1)])

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
        self.create_index([("date", 1)])
        self.create_index([("code", 1), ("date", -1)])

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

    def get_signals(self, code: str, days: int = 30) -> Dict[str, Any]:
        klines = self.find_many({"code": code}, sort=[("date", -1)], limit=days)
        if len(klines) < 5:
            return {}

        closes = [k.get('close', 0) for k in klines]
        volumes = [k.get('volume', 0) for k in klines]

        signals = {
            "code": code,
            "ma5": sum(closes[:5]) / 5 if len(closes) >= 5 else 0,
            "ma10": sum(closes[:10]) / 10 if len(closes) >= 10 else 0,
            "ma20": sum(closes[:20]) / 20 if len(closes) >= 20 else 0,
            "volume_ratio": volumes[0] / (sum(volumes[1:6]) / 5) if len(volumes) >= 6 else 1,
            "trend": "up" if closes[0] > closes[4] else "down"
        }

        if len(closes) >= 26:
            ema12 = self._calc_ema(closes[:12], 12)
            ema26 = self._calc_ema(closes[:26], 26)
            macd_dif = ema12 - ema26
            macd_dea = macd_dif * 0.9
            macd_bar = (macd_dif - macd_dea) * 2
            signals["macd"] = {"dif": macd_dif, "dea": macd_dea, "bar": macd_bar}

        return signals

    def _calc_ema(self, data: List[float], period: int) -> float:
        if len(data) < period:
            return 0
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema


class StockInfoStorage(MongoStorage):
    def __init__(self):
        super().__init__("stock_info")
        self.create_index([("_updated_at", -1)])

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        record = self.find_one({"code": code})
        if record:
            record.pop("_id", None)
            record.pop("_updated_at", None)
        return record

    def save_stock_info(self, info: Dict[str, Any]) -> bool:
        info["_updated_at"] = beijing_now()
        return self.upsert_one({"code": info["code"]}, info)


class FinancialStorage(MongoStorage):
    def __init__(self):
        super().__init__("financial")
        self.create_index([("report_date", 1)])

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
        return self.upsert_many(records, ["code", "report_date", "report_type"])


class NewsStorage(MongoStorage):
    def __init__(self):
        super().__init__("news")
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.create_index([("news_type", 1)])
        self.create_index([("channel_name", 1)])
        self.create_index([("is_breaking", 1)])
        self.create_index([("source", 1)])
        # 复合索引匹配列表查询的排序键 (publish_date, _updated_at)，
        # 使排序走 IXSCAN 而非阻塞式内存 SORT；其 publish_date 前缀同时覆盖单字段排序/过滤。
        self.create_index([("publish_date", -1), ("_updated_at", -1)])
        # 个股精确舆情按 code + 时间查询（StockNewsSentimentAnalyzer / hotspot）的索引
        # [("code",1),("publish_date",-1)] 已由 settings.py 的 news 配置经
        # DatabaseConfig.ensure_indexes() 建好，这里不重复创建（重复+sparse 会 IndexKeySpecsConflict）。

    def get_latest_news(
        self,
        code: Optional[str] = None,
        news_type: Optional[str] = None,
        channel_name: Optional[str] = None,
        is_breaking: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        filter_doc: Dict[str, Any] = {}
        if code:
            filter_doc["code"] = code
        if news_type:
            filter_doc["news_type"] = news_type
        if channel_name:
            filter_doc["channel_name"] = channel_name
        if is_breaking is not None:
            filter_doc["is_breaking"] = is_breaking

        records = self.find_many(
            filter_doc,
            sort=[("publish_date", -1), ("_updated_at", -1)],
            limit=limit
        )
        for record in records:
            record.pop("_id", None)
            record.pop("_updated_at", None)
            record.pop("_collect_at", None)
        return records

    def get_news_by_category(
        self,
        category: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        return self.get_latest_news(news_type=category, limit=limit)

    def get_breaking_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.get_latest_news(is_breaking=True, limit=limit)

    def save_news(self, news: Dict[str, Any]) -> str:
        if "title" in news and "url" in news:
            return self.upsert_one(
                {"title": news["title"], "url": news["url"]},
                news
            )
        if "title" in news and "publish_date" in news:
            return self.upsert_one(
                {"title": news["title"], "publish_date": news["publish_date"]},
                news
            )
        return self.insert_one(news)

    def get_latest_publish_date(self, channel_name: str) -> Optional[str]:
        """获取指定频道最新一条新闻的 publish_date，用于增量采集截止判断"""
        try:
            doc = self.collection.find_one(
                {"channel_name": channel_name,
                 "publish_date": {"$exists": True, "$nin": [None, ""]}},
                sort=[("publish_date", -1)],
                projection={"publish_date": 1, "_id": 0},
            )
            return doc["publish_date"] if doc else None
        except Exception:
            return None

    def save_news_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        valid = [r for r in records if r.get("title")]
        if not valid:
            return (0, 0)

        # 每条都生成 _uid 做去重 upsert（含个股 code 记录）：优先 title+url，
        # 无 url 退到 title+publish_date，仍无则用 title。避免重复抓取产生重复文档，
        # 也避免无 url 记录因缺 _uid 导致 filter_doc={} 误命中全集合。
        for record in valid:
            title = str(record.get("title", ""))
            url = str(record.get("url", "") or "")
            pub = str(record.get("publish_date", "") or "")
            if url:
                record["_uid"] = f"{title}_{url[:50]}"
            elif pub:
                record["_uid"] = f"{title}_{pub}"
            else:
                record["_uid"] = title

        return self.upsert_many(valid, ["_uid"])

    def get_news_stats(self) -> Dict[str, Any]:
        stats = {
            "total": self.count_documents({}),
            "by_type": {},
            "by_channel": {},
            "breaking_count": self.count_documents({"is_breaking": True})
        }

        pipeline = [
            {"$group": {"_id": "$news_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        type_stats = self.aggregate(pipeline)
        for item in type_stats:
            stats["by_type"][item["_id"] or "general"] = item["count"]

        pipeline = [
            {"$group": {"_id": "$channel_name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        channel_stats = self.aggregate(pipeline)
        for item in channel_stats:
            stats["by_channel"][item["_id"] or "unknown"] = item["count"]

        return stats


class FundFlowStorage(MongoStorage):
    def __init__(self):
        super().__init__("fund_flow")
        self.create_index([("date", -1)])

    def get_latest_flow(self, code: str) -> Optional[Dict[str, Any]]:
        """支持带 SH/SZ 前缀和不带前缀两种 code 格式。"""
        # 构建两种候选 code：带前缀 + 裸代码
        bare = code[2:] if code[:2] in ("SH", "SZ") else code
        candidates = [code]
        if code == bare:
            # 输入是裸代码，补充 SH/SZ 前缀候选
            prefix = "SH" if bare.startswith(("6", "9")) else "SZ"
            candidates.append(f"{prefix}{bare}")
        record = self.find_one({"code": {"$in": candidates}}, sort=[("date", -1)])
        if record:
            record.pop("_id", None)
            record.pop("_updated_at", None)
        return record

    def save_fund_flow_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self.upsert_many(records, ["code", "date"])


class TaskStorage(MongoStorage):
    def __init__(self):
        super().__init__("task")
        self.create_index([("create_time", -1)])
        self.create_index([("task_id", 1)])

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
            "create_time": beijing_now(),
            "update_time": beijing_now()
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
            "update_time": beijing_now()
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

    def delete_task(self, task_id: str) -> bool:
        return self.delete_one({"task_id": task_id})

    def delete_finished(self) -> int:
        return self.delete_many({"status": {"$in": ["completed", "failed", "cancelled"]}})


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
            "add_time": beijing_now(),
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
        self.create_index([("_updated_at", -1)])

    def save_block(self, block: Dict[str, Any]) -> str:
        if "code" in block and "block_type" in block:
            filter_doc = {"code": block["code"], "block_type": block["block_type"]}
            return self.upsert_one(filter_doc, block)
        return self.insert_one(block)

    def get_block_by_code(self, code: str, block_type: str = "industry") -> Optional[Dict[str, Any]]:
        return self.find_one({"code": code, "block_type": block_type})

    def get_blocks_by_type(self, block_type: str) -> List[Dict[str, Any]]:
        return self.find_many({"block_type": block_type})

    def get_stocks_by_block_name(self, block_name: str, block_type: str = "industry") -> List[str]:
        blocks = self.find_many({"block_name": block_name, "block_type": block_type})
        return [b.get("code") for b in blocks if b.get("code")]

    def get_block_names_by_type(self, block_type: str = "industry") -> List[str]:
        blocks = self.find_many({"block_type": block_type}, projection=["block_name"])
        names = set()
        for b in blocks:
            name = b.get("block_name")
            if name:
                names.add(name)
        return list(names)


class DragonTigerStorage(MongoStorage):
    def __init__(self):
        super().__init__("dragon_tiger")
        self.create_index([("上榜日", -1)])

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

    def save_dragon_tiger_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        if not records:
            return (0, 0)
        return self.upsert_many(records, ["代码", "上榜日", "上榜原因"])


class MarginStorage(MongoStorage):
    def __init__(self):
        super().__init__("margin_data")
        self.create_index([("date", -1)])

    def save_margin(self, margin: Dict[str, Any]) -> str:
        # 个股数据用 code + date；旧市场汇总数据兼容 信用交易日期 + market
        if "code" in margin and "date" in margin:
            return self.upsert_one({"code": margin["code"], "date": margin["date"]}, margin)
        if "信用交易日期" in margin and "market" in margin:
            return self.upsert_one({"信用交易日期": margin["信用交易日期"], "market": margin["market"]}, margin)
        return self.insert_one(margin)

    def get_latest_margin(self, market: str = "sh") -> Optional[Dict[str, Any]]:
        return self.find_one(
            {"market": market},
            sort=[("date", -1)]
        )

    def save_margin_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        if not records:
            return (0, 0)
        # 个股数据用 code + date 唯一键
        if records and "code" in records[0]:
            return self.upsert_many(records, ["code", "date"])
        return self.upsert_many(records, ["信用交易日期", "market"])


class ValuationStorage(MongoStorage):
    def __init__(self):
        super().__init__("stock_valuation")
        self.create_index([("updated_at", -1)])

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        record = self.find_one({"code": code})
        if record:
            record.pop("_id", None)
        return record

    def get_by_codes(self, codes: List[str]) -> List[Dict[str, Any]]:
        records = self.find_many({"code": {"$in": codes}})
        for r in records:
            r.pop("_id", None)
        return records

    def save_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        if not records:
            return (0, 0)
        return self.upsert_many(records, ["code"])


class ResearchReportStorage(MongoStorage):
    def __init__(self):
        super().__init__("research_reports")
        self.create_index([("date", -1)])
        self.create_index([("code", 1), ("date", -1)])
        self.create_index([("cached_at", -1)])

    def save_report(self, report: Dict[str, Any]) -> str:
        report_id = report.get("report_id", "")
        if report_id:
            return self.upsert_one({"report_id": report_id}, report)
        return self.insert_one(report)

    def save_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        if not records:
            return (0, 0)
        keys = [k for k in ["report_id"] if k in records[0]]
        if keys:
            return self.upsert_many(records, keys)
        return self.upsert_many(records, ["code", "date", "title"])

    def find_by_code(self, code: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.find_many(
            {"code": code},
            sort=[("date", -1)],
            limit=limit,
        )

    def search(
        self,
        keyword: str = "",
        code: str = "",
        org: str = "",
        days: int = 90,
        page: int = 1,
        page_size: int = 50,
        ratings: Optional[List[str]] = None,
        industry: str = "",
        author: str = "",
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        from datetime import datetime, timedelta
        query: Dict[str, Any] = {}
        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"name": {"$regex": keyword, "$options": "i"}},
            ]
        if code:
            query["code"] = code
        if org:
            query["org"] = {"$regex": org, "$options": "i"}
        if ratings:
            query["rating"] = {"$in": ratings}
        if industry:
            query["industry"] = {"$regex": industry, "$options": "i"}
        if author:
            query["author"] = {"$regex": author, "$options": "i"}
        cutoff = datetime.now() - timedelta(days=days)
        query["date"] = {"$gte": cutoff.strftime("%Y-%m-%d")}
        total = self.collection.count_documents(query)
        skip = (page - 1) * page_size
        sort_dir = -1 if sort_order == "desc" else 1
        results = self.find_many(query, sort=[(sort_by, sort_dir)], skip=skip, limit=page_size)
        for r in results:
            r.pop("_id", None)
        return results, total