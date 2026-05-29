"""
AutoStockCollector 主入口
Flask应用启动文件
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

dotenv_path = project_root / ".env"
if dotenv_path.exists():
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from api import create_app
from config.settings import Settings
from config.database import DatabaseConfig
from utils.logger import get_logger


logger = get_logger(__name__)


def init_app():
    logger.info("Initializing AutoStockCollector...")

    try:
        DatabaseConfig.connect()
        DatabaseConfig.ensure_indexes()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")

    # 每次启动时将 DB 中残留的 running/pending 任务标记为 cancelled
    # 这些是上次进程被杀死前未能更新状态的任务
    try:
        from datetime import datetime as _dt
        db = DatabaseConfig.get_database()
        result = db.task.update_many(
            {"status": {"$in": ["running", "pending"]}},
            {"$set": {"status": "cancelled", "end_time": _dt.now()}}
        )
        if result.modified_count:
            logger.info(f"Cleaned up {result.modified_count} stale running/pending tasks")
    except Exception as e:
        logger.warning(f"Stale task cleanup warning: {e}")

    try:
        from modules.ai.ai_key_manager import ai_key_manager
        ai_key_manager.restore_keys_from_db()
        logger.info("AI keys restored from database")
    except Exception as e:
        logger.warning(f"AI key restore warning: {e}")

    logger.info("AutoStockCollector initialized successfully")


def main():
    app = create_app()
    init_app()

    host = Settings.API_CONFIG["host"]
    port = Settings.API_CONFIG["port"]
    debug = Settings.API_CONFIG["debug"]

    logger.info(f"Starting AutoStockCollector on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()