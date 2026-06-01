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

    # 清理 workflow_execution 集合中的僵尸任务（超过30分钟仍为 running/pending）
    try:
        from datetime import datetime as _dt2, timedelta as _td
        db2 = DatabaseConfig.get_database()
        cutoff = (_dt2.now() - _td(minutes=30)).isoformat()
        we_result = db2["workflow_execution"].update_many(
            {"status": {"$in": ["running", "pending"]}, "started_at": {"$lt": cutoff}},
            {"$set": {
                "status": "failed",
                "error": "服务重启时自动终止（超时任务）",
                "current_step": "执行失败: 服务重启时自动终止",
                "finished_at": _dt2.now().isoformat()
            }}
        )
        if we_result.modified_count:
            logger.info(f"Cleaned up {we_result.modified_count} stale workflow executions")
        # 对于刚启动就还是 running（< 30分钟）的也一并清理，因为进程刚重启无法恢复
        we_result2 = db2["workflow_execution"].update_many(
            {"status": {"$in": ["running", "pending"]}},
            {"$set": {
                "status": "failed",
                "error": "服务重启时自动终止",
                "current_step": "执行失败: 服务重启时自动终止",
                "finished_at": _dt2.now().isoformat()
            }}
        )
        if we_result2.modified_count:
            logger.info(f"Cleaned up {we_result2.modified_count} additional stale workflow executions")
    except Exception as e:
        logger.warning(f"Workflow execution stale cleanup warning: {e}")

    try:
        from modules.ai.ai_key_manager import ai_key_manager
        ai_key_manager.restore_keys_from_db()
        logger.info("AI keys restored from database")
    except Exception as e:
        logger.warning(f"AI key restore warning: {e}")

    try:
        from core.scheduler.cron import start_daily_jobs
        start_daily_jobs()
        logger.info("Daily AI pick scheduler started")
    except Exception as e:
        logger.warning(f"Daily scheduler start warning: {e}")

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