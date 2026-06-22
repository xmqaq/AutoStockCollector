"""
MongoDB 数据库配置
"""
import os
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from .settings import Settings
from utils.logger import get_logger


logger = get_logger(__name__)


class DatabaseConfig:
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    @classmethod
    def connect(cls, uri: Optional[str] = None, database: Optional[str] = None) -> Database:
        if cls._db is not None:
            return cls._db

        uri = uri or Settings.MONGODB_URI
        database = database or Settings.MONGODB_DATABASE

        if not uri:
            raise ValueError("MongoDB URI is not configured. Please set MONGODB_URI environment variable.")

        try:
            cls._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                maxPoolSize=50,
                minPoolSize=5
            )
            cls._client.admin.command("ping")
            cls._db = cls._client[database]
            logger.info(f"Successfully connected to MongoDB database: {database}")
            return cls._db
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    def get_client(cls) -> MongoClient:
        if cls._client is None:
            cls.connect()
        return cls._client

    @classmethod
    def get_database(cls) -> Database:
        if cls._db is None:
            cls.connect()
        return cls._db

    @classmethod
    def get_collection(cls, name: str) -> Collection:
        db = cls.get_database()
        return db[name]

    @classmethod
    def close(cls):
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB connection closed")

    @classmethod
    def _dedup_collection(cls, collection, key_field: str):
        """按 key_field 去重，保留 _id 最大（最新插入）的文档"""
        pipeline = [
            {"$sort": {"_id": -1}},
            {"$group": {"_id": f"${key_field}", "keep": {"$first": "$_id"}}},
        ]
        keep_ids = [r["keep"] for r in collection.aggregate(pipeline)]
        if not keep_ids:
            return
        result = collection.delete_many({"_id": {"$nin": keep_ids}})
        if result.deleted_count:
            logger.info(f"Deduplicated {collection.name}.{key_field}: removed {result.deleted_count} duplicates")

    @classmethod
    def _safe_index(cls, collection, keys, **kwargs):
        """创建索引，失败时只打 WARNING 不中断启动"""
        try:
            collection.create_index(keys, **kwargs)
        except Exception as e:
            logger.warning(f"Index skipped [{collection.name}]: {e}")

    @classmethod
    def ensure_indexes(cls):
        db = cls.get_database()

        cls._safe_index(db.kline, [("code", 1), ("date", -1)], unique=True)
        cls._safe_index(db.kline, [("date", -1)])

        cls._safe_index(db.stock_info, [("code", 1)], unique=True)
        cls._safe_index(db.stock_info, [("update_time", -1)])

        try:
            db.financial.drop_index("code_1_report_date_-1")
        except Exception:
            pass
        cls._safe_index(db.financial, [("code", 1), ("report_date", -1), ("report_type", 1)], unique=True)
        cls._safe_index(db.financial, [("report_date", -1)])

        cls._safe_index(db.news, [("code", 1), ("publish_date", -1)])
        cls._safe_index(db.news, [("publish_date", -1)])

        cls._safe_index(db.fund_flow, [("code", 1), ("date", -1)], unique=True)
        cls._safe_index(db.fund_flow, [("date", -1)])

        # task 集合先去重再建唯一索引，避免历史脏数据导致 duplicate key error
        cls._dedup_collection(db.task, "task_id")
        cls._safe_index(db.task, [("task_id", 1)], unique=True)
        cls._safe_index(db.task, [("status", 1), ("create_time", -1)])

        cls._safe_index(db.watchlist, [("user_id", 1), ("group_id", 1)])
        cls._safe_index(db.watchlist, [("code", 1)])

        cls._safe_index(db.ai_result, [("code", 1), ("strategy", 1), ("date", -1)], unique=True)
        cls._safe_index(db.ai_result, [("created_at", -1)])

        cls._safe_index(db.cron_schedule, [("label", 1)], unique=True)

        cls._safe_index(db.stock_valuation, [("code", 1)], unique=True)
        cls._safe_index(db.stock_valuation, [("updated_at", -1)])

        cls._safe_index(db.todo, [("updatedAt", -1)])
        cls._safe_index(db.todo, [("category", 1)])
        cls._safe_index(db.todo, [("done", 1)])

        cls._safe_index(db.users, [("username", 1)], unique=True)
        cls._safe_index(db.users, [("email", 1)], sparse=True)
        cls._safe_index(db.users, [("user_id", 1)], unique=True)

        # 模拟交易
        cls._safe_index(db.trade_records, [("user_id", 1), ("traded_at", -1)])
        cls._safe_index(db.paper_account, [("user_id", 1)], unique=True)

        # 价格行为学缓存 & 扫描结果
        cls._dedup_collection(db.pa_quotes_cache, "cache_key")
        cls._safe_index(db.pa_quotes_cache, [("cache_key", 1)], unique=True)
        cls._safe_index(db.pa_quotes_cache, [("cached_at", -1)], expireAfterSeconds=86400 * 7)
        cls._dedup_collection(db.pa_scan_results, "scan_id")
        cls._safe_index(db.pa_scan_results, [("scan_id", 1)], unique=True)
        cls._safe_index(db.pa_scan_results, [("created_at", -1)])
        cls._dedup_collection(db.pa_backtest_cache, "cache_key")
        cls._safe_index(db.pa_backtest_cache, [("cache_key", 1)], unique=True)
        cls._safe_index(db.pa_backtest_cache, [("created_at", -1)], expireAfterSeconds=86400)

        # 研报分析缓存 & 结果
        cls._dedup_collection(db.reports_cache, "report_id")
        cls._safe_index(db.reports_cache, [("sector", 1)])
        cls._safe_index(db.reports_cache, [("report_id", 1)])
        cls._safe_index(db.reports_cache, [("cached_at", -1)], expireAfterSeconds=86400 * 14)
        cls._dedup_collection(db.research_analysis_results, "task_id")
        cls._safe_index(db.research_analysis_results, [("task_id", 1)])
        cls._safe_index(db.research_analysis_results, [("sectors", 1)])
        cls._safe_index(db.research_analysis_results, [("created_at", -1)])
        cls._dedup_collection(db.research_llm_cache, "cache_key")
        cls._safe_index(db.research_llm_cache, [("cache_key", 1)], unique=True)
        cls._safe_index(db.research_llm_cache, [("created_at", -1)], expireAfterSeconds=86400 * 2)

        logger.info("Database indexes ensured successfully")


def get_database() -> Database:
    return DatabaseConfig.get_database()


def get_collection(name: str) -> Collection:
    return DatabaseConfig.get_collection(name)