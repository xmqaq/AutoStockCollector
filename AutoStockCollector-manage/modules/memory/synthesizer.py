"""记忆合成器 - 将三层记忆融合为结构化 UserContext"""
from typing import Any, Dict, List, Optional
from modules.memory.models import UserContext, UserProfile, MemoryConfig
from modules.memory.working_memory import WorkingMemory
from modules.memory.episodic_memory import EpisodicMemory
from modules.memory.semantic_memory import SemanticMemory


class MemorySynthesizer:
    """记忆合成器：融合三层记忆为完整用户上下文"""

    def __init__(
        self,
        working: Optional[WorkingMemory] = None,
        episodic: Optional[EpisodicMemory] = None,
        semantic: Optional[SemanticMemory] = None,
        config: Optional[MemoryConfig] = None,
    ):
        self.config = config or MemoryConfig()
        self.working = working or WorkingMemory(self.config)
        self.episodic = episodic or EpisodicMemory(self.config)
        self.semantic = semantic or SemanticMemory(self.config)

    async def synthesize(
        self,
        user_id: str,
        stock_code: Optional[str] = None,
        include_patterns: bool = True,
    ) -> UserContext:
        """合成用户上下文"""
        profile = self.episodic.get_profile(user_id)
        session = self.working.get_or_create(user_id)
        holdings = self.episodic.get_holding_summary(user_id)
        recent_views = self.episodic.get_recent_views(user_id)
        previous_analyses = []
        if stock_code:
            previous_analyses = self.episodic.get_stock_analyses(
                user_id, stock_code
            )

        patterns = []
        if include_patterns:
            patterns = self.semantic.get_top_patterns(user_id)
            if not patterns:
                try:
                    patterns = self.semantic.analyze_patterns(user_id)
                except Exception:
                    pass

        return UserContext(
            user_id=user_id,
            profile=profile,
            current_holdings=holdings,
            recent_views=recent_views,
            previous_analyses=previous_analyses,
            patterns=patterns,
            last_interaction=(
                session.last_interaction.isoformat()
                if session.last_interaction else None
            ),
            session_stock=session.current_stock,
        )

    async def on_analysis_complete(
        self,
        user_id: str,
        code: str,
        analysis_type: str,
        verdict: str,
        recommendation: str,
    ):
        """分析完成后记录历史"""
        from modules.memory.models import AnalysisHistory
        from datetime import datetime

        self.episodic.record_analysis(AnalysisHistory(
            user_id=user_id,
            code=code,
            analysis_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            analysis_type=analysis_type,
            verdict=verdict,
            recommendation=recommendation,
        ))

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """获取记忆统计"""
        session = self.working.get_session(user_id)
        holdings = self.episodic.get_holding_summary(user_id)
        analyses = self.episodic.get_recent_analyses(user_id, limit=1)
        pattern_stats = self.semantic.get_stats(user_id)

        from modules.memory.models import MemoryStats
        stats = MemoryStats(
            working_memory_active=session is not None,
            holding_count=holdings.get("count", 0),
            analysis_count=len(self.episodic.get_recent_analyses(user_id, limit=1000)),
            pattern_count=pattern_stats.get("pattern_count", 0),
            last_interaction=(
                session.last_interaction.isoformat()
                if session and session.last_interaction else None
            ),
        )
        return {
            "working_memory_active": stats.working_memory_active,
            "holding_count": stats.holding_count,
            "analysis_count": stats.analysis_count,
            "pattern_count": stats.pattern_count,
            "last_interaction": stats.last_interaction,
            "patterns": pattern_stats.get("top_patterns", []),
        }
