"""博弈树 - 多轮辩论权重更新与共识计算"""
import statistics
from typing import Any, Dict, List, Optional, Tuple
from modules.ai.debate.schemas import DebateRound, BattleResult, DebateArgument


class GameTree:
    """扩展型博弈树：每轮辩论更新各 Agent 权重，计算共识"""

    @staticmethod
    def update_weights(
        current_weights: Dict[str, float],
        debate_round: DebateRound,
    ) -> Dict[str, float]:
        """基于辩论结果更新权重"""
        new_weights = {}
        for agent_id, weight in current_weights.items():
            persuasion = debate_round.agent_persuasions.get(agent_id, 0.5)
            delta = (persuasion - 0.5) * 0.2
            new_weights[agent_id] = weight * (1 + delta)

        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}
        return new_weights

    @staticmethod
    def compute_consensus(
        arguments: List[Dict[str, Any]],
        weights: Dict[str, float],
    ) -> BattleResult:
        """计算加权共识"""
        if not arguments:
            return BattleResult(
                final_tendency=0, consensus_level=0,
                confidence=0, winning_side="neutral",
            )

        weighted_scores = {}
        for arg in arguments:
            aid = arg.get("agent_id", "")
            stance = arg.get("stance", "neutral")
            w = weights.get(aid, 1.0 / max(len(weights), 1))
            if stance == "bullish":
                weighted_scores[aid] = w * 1.0
            elif stance == "bearish":
                weighted_scores[aid] = w * -1.0
            else:
                weighted_scores[aid] = w * 0.0

        tendency = sum(weighted_scores.values()) / max(sum(weights.values()), 0.01) if weights else 0

        stances = [a.get("stance", "neutral") for a in arguments]
        bullish_count = sum(1 for s in stances if s == "bullish")
        bearish_count = sum(1 for s in stances if s == "bearish")
        total = len(stances) if stances else 1
        divergence = 1.0 - abs(bullish_count - bearish_count) / total
        consensus_level = 1.0 - divergence

        confidence = max(0, 1.0 - divergence * 1.5)

        if tendency > 0.15:
            winning_side = "bullish"
        elif tendency < -0.15:
            winning_side = "bearish"
        else:
            winning_side = "neutral"

        return BattleResult(
            final_tendency=round(tendency, 3),
            consensus_level=round(consensus_level, 2),
            confidence=round(confidence, 2),
            winning_side=winning_side,
        )

    @staticmethod
    def compute_persuasions(
        arguments: List[DebateArgument],
        context: Dict,
    ) -> Dict[str, float]:
        """评估各 Agent 的说服力"""
        persuasions = {}
        for arg in arguments:
            evidence_count = len(arg.evidence)
            arg_length = len(arg.argument)
            base = 0.3 + min(evidence_count * 0.1, 0.3) + min(arg_length / 500 * 0.2, 0.2)
            persuasions[arg.agent_id] = round(min(base, 0.95), 2)
        return persuasions

    @staticmethod
    def initial_weights(agent_ids: List[str]) -> Dict[str, float]:
        n = len(agent_ids)
        return {aid: 1.0 / n for aid in agent_ids} if n > 0 else {}
