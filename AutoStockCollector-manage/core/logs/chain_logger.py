"""
链路追踪日志模块
为增强调度器提供请求链路追踪能力
"""
import uuid
import threading
from enum import Enum
from datetime import datetime
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogStage(Enum):
    START = "start"
    PROCESSING = "processing"
    API_CALL = "api_call"
    STORAGE = "storage"
    COMPLETE = "complete"
    FAILED = "failed"


class ChainLogger:
    """
    链路追踪日志记录器
    将同一任务的所有日志通过 request_id 串联，便于全链路追踪与故障定位
    """

    def __init__(self):
        self._chains: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start_chain(self, task_id: str, task_type: str, params: Dict[str, Any]) -> str:
        """开启一条新的链路追踪，返回 request_id"""
        request_id = str(uuid.uuid4())
        with self._lock:
            self._chains[request_id] = {
                "request_id": request_id,
                "task_id": task_id,
                "task_type": task_type,
                "params": params,
                "start_time": datetime.now().isoformat(),
                "api_calls": [],
                "success": None,
            }
        logger.info(f"[CHAIN:{request_id[:8]}] Task {task_id} ({task_type}) started")
        return request_id

    def end_chain(
        self,
        request_id: Optional[str],
        success: bool = True,
        stats: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """结束链路追踪，记录最终状态"""
        if not request_id:
            return
        with self._lock:
            chain = self._chains.get(request_id)
            if chain:
                chain["success"] = success
                chain["end_time"] = datetime.now().isoformat()
                if stats:
                    chain["stats"] = stats
                if error_message:
                    chain["error_message"] = error_message

        level = "info" if success else "error"
        msg = (
            f"[CHAIN:{request_id[:8]}] Chain ended: success={success}"
            + (f", stats={stats}" if stats else "")
            + (f", error={error_message}" if error_message else "")
        )
        getattr(logger, level)(msg)

        # 避免内存无限增长，完成后清理
        with self._lock:
            self._chains.pop(request_id, None)

    def log_api_call(
        self,
        request_id: Optional[str],
        source: str,
        params: Dict[str, Any],
        duration: float,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """记录一次 API 调用到当前链路"""
        if not request_id:
            return
        call = {
            "source": source,
            "params": params,
            "duration_ms": round(duration * 1000, 2),
            "success": success,
            "time": datetime.now().isoformat(),
        }
        if error:
            call["error"] = error

        with self._lock:
            chain = self._chains.get(request_id)
            if chain:
                chain["api_calls"].append(call)

        level = "debug" if success else "warning"
        getattr(logger, level)(
            f"[CHAIN:{request_id[:8]}] API {source} "
            f"{'OK' if success else 'FAIL'} ({duration*1000:.0f}ms)"
            + (f" error={error}" if error else "")
        )

    def get_chain(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._chains.get(request_id)


chain_logger = ChainLogger()
