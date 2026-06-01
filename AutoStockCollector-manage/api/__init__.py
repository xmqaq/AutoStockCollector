"""
API模块初始化
"""
from flask import Flask
from flask_cors import CORS
from utils.logger import get_logger

_logger = get_logger(__name__)


def _bootstrap(app: Flask) -> None:
    """应用启动时的一次性初始化（幂等，可被多次调用）。
    放在 create_app() 内保证 flask run / gunicorn / python main.py 均能执行。
    """
    from config.database import DatabaseConfig
    try:
        DatabaseConfig.connect()
        DatabaseConfig.ensure_indexes()
        _logger.info("Database connected")
    except Exception as e:
        _logger.warning(f"Database init warning: {e}")

    # 将上次进程异常退出遗留的 running/pending 任务标记为 cancelled
    try:
        from datetime import datetime as _dt
        db = DatabaseConfig.get_database()
        r = db.task.update_many(
            {"status": {"$in": ["running", "pending"]}},
            {"$set": {"status": "cancelled", "end_time": _dt.now()}}
        )
        if r.modified_count:
            _logger.info(f"Cleaned up {r.modified_count} stale tasks")
    except Exception as e:
        _logger.warning(f"Stale task cleanup warning: {e}")

    try:
        from modules.ai.ai_key_manager import ai_key_manager
        ai_key_manager.restore_keys_from_db()
    except Exception as e:
        _logger.warning(f"AI key restore warning: {e}")

    try:
        from core.scheduler.cron import start_daily_jobs
        start_daily_jobs()
        _logger.info("Cron scheduler started")
    except Exception as e:
        _logger.warning(f"Cron scheduler start warning: {e}")


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.settings.Settings")

    CORS(app)

    from api.routes import register_routes
    register_routes(app)

    _bootstrap(app)

    return app


__all__ = ["create_app"]