"""
enhanced_scheduler — 已合并入 scheduler.py
保留此文件仅为兼容旧导入路径，不再独立存在逻辑。
"""
from .scheduler import TaskScheduler, Task, TaskMetrics, scheduler

# 向后兼容别名
EnhancedTaskScheduler = TaskScheduler
EnhancedTask = Task
enhanced_scheduler = scheduler

__all__ = [
    "TaskScheduler",
    "EnhancedTaskScheduler",
    "Task",
    "EnhancedTask",
    "TaskMetrics",
    "scheduler",
    "enhanced_scheduler",
]
