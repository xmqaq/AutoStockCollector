"""Research 环境 - 多 Agent 并行研究"""
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from modules.ai.debate.schemas import ResearchReport
from modules.ai.debate.mcp_bridge import MCPBridge
from modules.ai.philosophies.registry import PhilosophyRegistry
from utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    """研究 Agent - 可独立研究并产出报告"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        archetype: str,
        system_prompt: str,
        tool_names: List[str] = None,
        router=None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.archetype = archetype
        self.system_prompt = system_prompt
        self.tool_names = tool_names or []
        self.router = router

    async def research(self, stock_code: str, stock_data: Dict) -> ResearchReport:
        """执行研究"""
        tool_results = {}
        for tool_name in self.tool_names:
            result = await MCPBridge.call_tool(tool_name, {"code": stock_code})
            if result.success:
                tool_results[tool_name] = result.data

        data_sources = list(tool_results.keys())

        if self.router:
            prompt = self._build_research_prompt(stock_code, tool_results, stock_data)
            try:
                llm_result = self.router.chat(
                    prompt, use_cache=False,
                    task_type=f"research_{self.agent_id}",
                )
                raw_analysis = llm_result.raw if llm_result.success else ""
            except Exception:
                raw_analysis = ""
        else:
            raw_analysis = self._fallback_analysis(stock_code, stock_data)

        key_findings = self._extract_findings(raw_analysis, tool_results, stock_data)
        signal, confidence = self._determine_signal(key_findings, stock_data)

        return ResearchReport(
            agent_id=self.agent_id,
            agent_name=self.name,
            archetype=self.archetype,
            data_sources=data_sources,
            key_findings=key_findings,
            signal=signal,
            confidence=confidence,
            evidence=tool_results,
            raw_analysis=raw_analysis,
        )

    def _build_research_prompt(self, code: str, tools: Dict, data: Dict) -> str:
        context_parts = [f"股票代码：{code}"]

        flow = tools.get("fund_flow_analysis", {})
        if flow and isinstance(flow, dict) and not flow.get("error"):
            context_parts.append(f"资金流向：主力净流入 {flow.get('record', {}).get('main_net_inflow', 'N/A')}")

        kline = tools.get("kline_trend", {})
        if kline and isinstance(kline, dict) and not kline.get("error"):
            context_parts.append(f"K线数据：最近 {kline.get('count', 0)} 条记录")

        context = "\n".join(context_parts)
        return f"{self.system_prompt}\n\n【研究标的】\n{context}\n\n请基于以上数据输出分析结论。"

    def _fallback_analysis(self, code: str, data: Dict) -> str:
        return f"{self.name} 基于现有数据完成分析，综合评分中性。"

    def _extract_findings(self, analysis: str, tools: Dict, data: Dict) -> List[str]:
        findings = []
        flow = tools.get("fund_flow_analysis", {})
        if flow and isinstance(flow, dict):
            record = flow.get("record", {})
            if record and record.get("main_net_inflow", 0) > 0:
                findings.append("主力资金净流入")
            elif record:
                findings.append("主力资金净流出")
        return findings or ["数据有限，未获取到明确信号"]

    def _determine_signal(self, findings: List[str], data: Dict) -> tuple:
        if not findings:
            return "neutral", 0.5
        positive = sum(1 for f in findings if any(k in f for k in ["净流入", "上涨", "利好"]))
        negative = sum(1 for f in findings if any(k in f for k in ["净流出", "下跌", "利空"]))
        if positive > negative:
            return "bullish", 0.5 + 0.1 * (positive - negative)
        elif negative > positive:
            return "bearish", 0.5 + 0.1 * (negative - positive)
        return "neutral", 0.5


class ResearchEnvironment:
    """Research 环境：多 Agent 并行研究，通过 MCP 协议获取专属数据工具"""

    def __init__(self, router=None):
        self.router = router
        self.agents: Dict[str, ResearchAgent] = {}
        self._init_default_agents()

    def register_agent(self, agent: ResearchAgent):
        self.agents[agent.agent_id] = agent

    def _init_default_agents(self):
        # 8个默认研究Agent
        default_agents = [
            ResearchAgent("sentiment", "舆情分析", "sentiment",
                "分析新闻舆情对股票的影响", ["news_sentiment"], self.router),
            ResearchAgent("hot_money", "游资追踪", "hot_money",
                "跟踪龙虎榜资金动向和游资行为", ["dragon_tiger_analysis", "fund_flow_analysis"], self.router),
            ResearchAgent("technical", "技术分析", "technical",
                "基于量价指标进行技术面分析", ["kline_trend", "fund_flow_analysis"], self.router),
            ResearchAgent("fundamental", "基本面分析", "value",
                "深入分析公司财务数据和成长性", ["financial_analysis"], self.router),
            ResearchAgent("capital", "资金流向", "quant",
                "分析主力资金和市场整体资金动向", ["fund_flow_analysis", "market_capital_flow"], self.router),
            ResearchAgent("risk", "风险扫描", "risk",
                "扫描流动性、估值、基本面等多维度风险", ["financial_analysis", "kline_trend"], self.router),
        ]
        for agent in default_agents:
            self.register_agent(agent)

    async def run_research(self, stock_code: str, stock_data: Optional[Dict] = None) -> Dict[str, ResearchReport]:
        """并行执行所有 Agent 的研究"""
        data = stock_data or {}
        tasks = {
            aid: agent.research(stock_code, data)
            for aid, agent in self.agents.items()
        }
        results = {}
        for aid, task in tasks.items():
            try:
                results[aid] = await task
            except Exception as e:
                logger.error(f"Research agent {aid} failed: {e}")
                results[aid] = ResearchReport(
                    agent_id=aid,
                    agent_name=self.agents[aid].name if aid in self.agents else aid,
                    archetype="unknown",
                    key_findings=[f"研究失败: {e}"],
                    signal="neutral",
                    confidence=0,
                )
        return results

    def get_agent_list(self) -> List[Dict]:
        return [
            {"id": aid, "name": a.name, "archetype": a.archetype, "tools": a.tool_names}
            for aid, a in self.agents.items()
        ]
