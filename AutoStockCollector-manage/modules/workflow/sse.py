"""
轻量级 SSE 事件总线，用于工作流执行进度推送。
"""
import json
import queue
import threading
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowSSE:
    _queues: Dict[str, queue.Queue] = {}
    _lock = threading.Lock()

    @classmethod
    def subscribe(cls, execution_id: str) -> queue.Queue:
        """订阅指定 execution 的事件，返回一个队列。"""
        with cls._lock:
            if execution_id not in cls._queues:
                cls._queues[execution_id] = queue.Queue(maxsize=500)
            return cls._queues[execution_id]

    @classmethod
    def publish(cls, execution_id: str, event: str, data: dict):
        """向指定 execution 的所有订阅者推送事件。"""
        with cls._lock:
            q = cls._queues.get(execution_id)
        if q is None:
            return
        try:
            payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            q.put_nowait(payload)
        except queue.Full:
            logger.warning(f"SSE queue full for execution {execution_id}, dropping event")

    @classmethod
    def unsubscribe(cls, execution_id: str, q: queue.Queue):
        """取消订阅。"""
        with cls._lock:
            existing = cls._queues.get(execution_id)
            if existing is q:
                del cls._queues[execution_id]

    @classmethod
    def cleanup(cls, execution_id: str):
        """清理 execution 的所有订阅队列。"""
        with cls._lock:
            cls._queues.pop(execution_id, None)
