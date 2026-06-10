"""提示词注入器 - 将用户记忆注入 LLM prompt"""
from typing import Dict, List, Optional
from modules.memory.models import UserContext


class PromptInjector:
    """提示词注入器：将合成后的用户记忆注入 LLM prompt"""

    RISK_LABELS = {
        "conservative": "保守型",
        "balanced": "稳健型",
        "aggressive": "进取型",
    }

    @classmethod
    def inject(cls, base_prompt: str, user_context: Optional[UserContext]) -> str:
        """将用户上下文注入到基础提示词中"""
        if not user_context:
            return base_prompt

        injections = cls._build_injections(user_context)
        if not injections:
            return base_prompt

        extra = "\n".join(injections)
        return f"{base_prompt}\n\n【用户上下文】\n{extra}"

    @classmethod
    def inject_into_messages(
        cls,
        messages: List[Dict[str, str]],
        user_context: Optional[UserContext],
    ) -> List[Dict[str, str]]:
        """将用户上下文注入到多轮对话 messages 中"""
        if not user_context:
            return messages

        injections = cls._build_injections(user_context)
        if not injections:
            return messages

        extra = "\n".join(injections)
        system_msg = f"【用户上下文】\n{extra}"

        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = f"{messages[0]['content']}\n\n{system_msg}"
        else:
            messages.insert(0, {"role": "system", "content": system_msg})
        return messages

    @classmethod
    def _build_injections(cls, ctx: UserContext) -> List[str]:
        parts = []

        if ctx.profile:
            risk_label = cls.RISK_LABELS.get(ctx.profile.risk_level, "稳健型")
            parts.append(f"- 风险偏好：{risk_label}")
            if ctx.profile.preferred_industries:
                inds = "、".join(ctx.profile.preferred_industries[:5])
                parts.append(f"- 关注行业：{inds}")
            horizon_map = {"short": "短线", "medium": "中长线", "long": "长线"}
            parts.append(
                f"- 持仓周期：{horizon_map.get(ctx.profile.holding_horizon, '中长线')}"
            )

        holdings = ctx.current_holdings
        if holdings and holdings.get("count", 0) > 0:
            codes = holdings.get("codes", [])
            sectors = holdings.get("sectors", {})
            parts.append(
                f"- 当前持仓：{holdings['count']}支"
                + (f"（{', '.join(codes[:5])}）" if codes else "")
            )
            if sectors:
                top_sectors = sorted(
                    sectors.items(), key=lambda x: -x[1]
                )[:3]
                parts.append(
                    f"- 持仓行业分布：{'、'.join(f'{s}({c}支)' for s, c in top_sectors)}"
                )

        if ctx.previous_analyses:
            last = ctx.previous_analyses[0]
            parts.append(
                f"- 历史分析：曾在{last.get('analysis_date', '近期')}分析过该股"
                + (f"，当时建议：{last.get('recommendation', '')}" if last.get('recommendation') else "")
            )
            if last.get("user_feedback"):
                fb = "认同" if last.get("user_feedback") == "agree" else "不认同"
                parts.append(f"  你对上次分析{fb}")

        recent = ctx.recent_views
        if recent and len(recent) > 3:
            parts.append(f"- 近期关注：{', '.join(recent[:8])}")

        patterns = ctx.patterns
        if patterns:
            for p in patterns[:2]:
                parts.append(f"- 投资洞察：{p.description}")

        if ctx.last_interaction:
            try:
                from datetime import datetime
                from utils.helpers import beijing_now
                last_dt = datetime.fromisoformat(ctx.last_interaction)
                now = beijing_now()
                delta_hours = (now - last_dt).total_seconds() / 3600
                if delta_hours < 1:
                    parts.append("- 上次交互：刚刚")
                elif delta_hours < 24:
                    parts.append(f"- 上次交互：{int(delta_hours)}小时前")
                else:
                    parts.append(f"- 上次交互：{int(delta_hours/24)}天前")
            except Exception:
                pass

        return parts
