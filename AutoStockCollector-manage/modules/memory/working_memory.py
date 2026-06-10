"""工作记忆 - 短期会话上下文"""
from datetime import datetime, timedelta
from utils.helpers import beijing_now
from typing import Dict, List, Optional, Any
from modules.memory.models import SessionContext, MemoryConfig


class WorkingMemory:
    """工作记忆：当前会话上下文，存于内存，会话结束后清理"""

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._sessions: Dict[str, SessionContext] = {}

    def get_or_create(self, user_id: str) -> SessionContext:
        if user_id not in self._sessions:
            self._sessions[user_id] = SessionContext(
                user_id=user_id,
                last_interaction=beijing_now(),
                current_stock=None,
                conversation_history=[],
                pending_actions=[],
            )
        else:
            ctx = self._sessions[user_id]
            ctx.last_interaction = beijing_now()
            self._cleanup_old_history(ctx)
        return self._sessions[user_id]

    def update_last_interaction(self, user_id: str, stock_code: Optional[str] = None):
        ctx = self.get_or_create(user_id)
        ctx.last_interaction = beijing_now()
        if stock_code:
            ctx.current_stock = stock_code

    def add_conversation(self, user_id: str, role: str, content: str):
        ctx = self.get_or_create(user_id)
        ctx.conversation_history.append({
            "role": role, "content": content,
            "timestamp": beijing_now().isoformat(),
        })
        self._cleanup_old_history(ctx)

    def add_pending_action(self, user_id: str, action: str):
        ctx = self.get_or_create(user_id)
        ctx.pending_actions.append(action)

    def get_session(self, user_id: str) -> Optional[SessionContext]:
        ctx = self._sessions.get(user_id)
        if ctx and ctx.last_interaction:
            elapsed = beijing_now() - ctx.last_interaction
            if elapsed.total_seconds() > self.config.working_ttl_minutes * 60:
                self.clear_session(user_id)
                return None
        return ctx

    def clear_session(self, user_id: str):
        self._sessions.pop(user_id, None)

    def clear_all(self):
        self._sessions.clear()

    def _cleanup_old_history(self, ctx: SessionContext):
        max_len = self.config.max_conversation_history
        if len(ctx.conversation_history) > max_len:
            ctx.conversation_history = ctx.conversation_history[-max_len:]

    @property
    def active_count(self) -> int:
        return len(self._sessions)
