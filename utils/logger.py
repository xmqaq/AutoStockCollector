"""
日志管理模块
提供分级日志、分类归档、自动清理能力
"""
import os
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class LogManager:
    _instances = {}
    _log_dir = Path(__file__).parent.parent.parent / "logs"

    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    RETENTION_DAYS = {
        "normal": 30,
        "error": 60
    }

    def __init__(self, name: str, log_level: str = "INFO", log_type: str = "normal"):
        self.name = name
        self.log_level = log_level
        self.log_type = log_type
        self.logger: Optional[logging.Logger] = None
        self._setup_logger()

    def _setup_logger(self):
        if self.logger is not None:
            return

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.LOG_LEVELS.get(self.log_level, logging.INFO))
        self.logger.handlers.clear()

        self._log_dir.mkdir(parents=True, exist_ok=True)

        log_file = self._log_dir / f"{self.name}_{self.log_type}.log"
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=self.RETENTION_DAYS.get(self.log_type, 30),
            encoding="utf-8"
        )

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs):
        self.logger.error(message, extra=kwargs)

    def critical(self, message: str, **kwargs):
        self.logger.critical(message, extra=kwargs)


def get_logger(name: str, log_level: str = "INFO", log_type: str = "normal") -> LogManager:
    key = f"{name}_{log_type}"
    if key not in LogManager._instances:
        LogManager._instances[key] = LogManager(name, log_level, log_type)
    return LogManager._instances[key]


def clean_old_logs(days: Optional[int] = None):
    if days is None:
        days = LogManager.RETENTION_DAYS["normal"]

    cutoff = datetime.now() - timedelta(days=days)

    for log_file in LogManager._log_dir.glob("*.log*"):
        if log_file.is_file():
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink(missing_ok=True)


def init_task_logger(task_id: str) -> LogManager:
    task_log_dir = LogManager._log_dir / "tasks" / task_id
    task_log_dir.mkdir(parents=True, exist_ok=True)
    return get_logger(f"task_{task_id}", log_level="INFO", log_type="normal")