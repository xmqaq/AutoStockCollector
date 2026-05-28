"""
调度器基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .enums import TaskStatus


class BaseScheduler(ABC):
    @abstractmethod
    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        pass


class IncrementalScheduler(BaseScheduler):
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        return self.scheduler.create_task(task_type, params)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.scheduler.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.scheduler.list_tasks(status, limit)

    def cancel_task(self, task_id: str) -> bool:
        return self.scheduler.cancel_task(task_id)

    def schedule_incremental(
        self,
        codes: Optional[List[str]] = None,
        data_type: str = "kline"
    ) -> str:
        params = {
            "codes": codes or [],
            "data_type": data_type
        }
        return self.scheduler.create_task("incremental", params)

    def schedule_daily(
        self,
        time_str: str = "15:30"
    ):
        pass


class BackfillScheduler(BaseScheduler):
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        return self.scheduler.create_task(task_type, params)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.scheduler.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.scheduler.list_tasks(status, limit)

    def cancel_task(self, task_id: str) -> bool:
        return self.scheduler.cancel_task(task_id)

    def schedule_backfill(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> str:
        params = {
            "codes": codes,
            "start_date": start_date,
            "end_date": end_date
        }
        return self.scheduler.create_task("backfill", params)