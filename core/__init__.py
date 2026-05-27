"""
核心模块初始化
"""
from .risk_control.risk_control import RiskController

__all__ = [
    "BaseCollector",
    "MongoStorage",
    "DataValidator",
    "TaskScheduler",
    "RiskController",
]


def __getattr__(name):
    if name == "BaseCollector":
        from .collector.base import BaseCollector
        return BaseCollector
    elif name == "MongoStorage":
        from .storage.mongo_storage import MongoStorage
        return MongoStorage
    elif name == "DataValidator":
        from .validator.validator import DataValidator
        return DataValidator
    elif name == "TaskScheduler":
        from .scheduler.scheduler import TaskScheduler
        return TaskScheduler
    elif name == "RiskController":
        from .risk_control.risk_control import RiskController
        return RiskController
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")