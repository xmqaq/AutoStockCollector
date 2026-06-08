"""Research-Battle 双环境辩论系统"""
from modules.ai.debate.mcp_bridge import MCPBridge, MCPTool
from modules.ai.debate.research_env import ResearchEnvironment, ResearchAgent, ResearchReport
from modules.ai.debate.battle_env import BattleEnvironment, DebateRound
from modules.ai.debate.game_tree import GameTree

__all__ = [
    "MCPBridge", "MCPTool",
    "ResearchEnvironment", "ResearchAgent", "ResearchReport",
    "BattleEnvironment", "DebateRound",
    "GameTree",
]
