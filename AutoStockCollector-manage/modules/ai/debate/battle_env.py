"""Battle 环境 - 多轮博弈辩论"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from modules.ai.debate.schemas import (
    ResearchReport, DebateRound, DebateArgument, BattleResult,
)
from modules.ai.debate.game_tree import GameTree
from modules.ai.philosophies.registry import PhilosophyRegistry
from modules.ai.philosophies.base import Archetype
from utils.logger import get_logger

logger = get_logger(__name__)


class BattleEnvironment:
    """Battle 环境：多轮博弈辩论，使用扩展型博弈树动态更新权重"""

    def __init__(self, router=None):
        self.router = router
        self.rounds: List[DebateRound] = []
        self.agent_weights: Dict[str, float] = {}

    async def run(
        self,
        research_reports: Dict[str, ResearchReport],
        num_rounds: int = 3,
    ) -> BattleResult:
        """执行多轮辩论"""
        agent_ids = list(research_reports.keys())

        self.agent_weights = GameTree.initial_weights(agent_ids)
        stances = {
            aid: report.signal
            for aid, report in research_reports.items()
        }

        for round_num in range(num_rounds):
            debate_round = DebateRound(round_number=round_num + 1)

            for aid in agent_ids:
                report = research_reports.get(aid)
                if not report:
                    continue

                arguments = self._generate_argument(
                    aid, report, round_num, stances,
                )
                debate_round.arguments.append(arguments)

            persuasion_context = {
                "round": round_num,
                "reports": research_reports,
                "weights": self.agent_weights,
            }
            debate_round.agent_persuasions = GameTree.compute_persuasions(
                debate_round.arguments, persuasion_context,
            )

            self.agent_weights = GameTree.update_weights(
                self.agent_weights, debate_round,
            )

            self.rounds.append(debate_round)

        all_arguments = []
        for r in self.rounds:
            all_arguments.extend(r.arguments)

        argument_dicts = []
        for arg in all_arguments:
            if isinstance(arg, DebateArgument):
                argument_dicts.append({
                    "agent_id": arg.agent_id,
                    "agent_name": arg.agent_name,
                    "stance": arg.stance,
                })

        result = GameTree.compute_consensus(argument_dicts, self.agent_weights)
        result.rounds = self.rounds
        result.key_insights = self._extract_insights(research_reports, result)
        result.risk_flags = self._extract_risks(research_reports)

        return result

    def _generate_argument(
        self,
        agent_id: str,
        report: ResearchReport,
        round_num: int,
        stances: Dict[str, str],
    ) -> DebateArgument:
        """生成辩论论点"""
        stance = "bullish" if report.signal == "bullish" else "bearish" if report.signal == "bearish" else "neutral"

        findings_text = "；".join(report.key_findings[:3]) if report.key_findings else "数据有限"
        argument_text = (
            f"基于{len(report.data_sources)}个数据源分析：{findings_text}。"
            f"置信度{report.confidence:.0%}。"
        )

        opposite_agents = [
            aid for aid, s in stances.items()
            if s != report.signal and aid != agent_id
        ]
        target = opposite_agents[0] if round_num > 0 and opposite_agents else None

        if round_num > 0:
            weight = self.agent_weights.get(agent_id, 0.1)
            argument_text += f" 当前权重{weight:.1%}。"

        return DebateArgument(
            agent_id=agent_id,
            agent_name=report.agent_name,
            stance=stance,
            argument=argument_text,
            evidence=report.key_findings[:3],
            rebuttal_target=target,
        )

    def _extract_insights(
        self,
        reports: Dict[str, ResearchReport],
        result: BattleResult,
    ) -> List[str]:
        insights = []
        for report in reports.values():
            if report.key_findings:
                insights.extend(report.key_findings[:2])
        insights.append(
            f"最终倾向：{result.winning_side}（共识度{result.consensus_level:.0%}）"
        )
        return insights[:5]

    def _extract_risks(self, reports: Dict[str, ResearchReport]) -> List[str]:
        risks = []
        risk_agent = reports.get("risk")
        if risk_agent and risk_agent.signal == "bearish":
            risks.append("风控Agent提示风险")
        return risks
