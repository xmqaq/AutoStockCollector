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
    def ensure_indexes(cls):
        db = cls.get_database()

        db.kline.create_index([("code", 1), ("date", -1)], unique=True)
        db.kline.create_index([("date", -1)])

        db.stock_info.create_index([("code", 1)], unique=True)
        db.stock_info.create_index([("update_time", -1)])

        db.financial.create_index([("code", 1), ("report_date", -1)], unique=True)
        db.financial.create_index([("report_date", -1)])

        db.news.create_index([("code", 1), ("publish_date", -1)])
        db.news.create_index([("publish_date", -1)])

        db.fund_flow.create_index([("code", 1), ("date", -1)], unique=True)
        db.fund_flow.create_index([("date", -1)])

        db.task.create_index([("task_id", 1)], unique=True)
        db.task.create_index([("status", 1), ("create_time", -1)])

        db.watchlist.create_index([("user_id", 1), ("group_id", 1)])
        db.watchlist.create_index([("code", 1)])

        db.ai_result.create_index([("code", 1), ("strategy", 1), ("date", -1)], unique=True)
        db.ai_result.create_index([("created_at", -1)])

        logger.info("Database indexes created successfully")


def get_database() -> Database:
    return DatabaseConfig.get_database()


def get_collection(name: str) -> Collection:
    return DatabaseConfig.get_collection(name)