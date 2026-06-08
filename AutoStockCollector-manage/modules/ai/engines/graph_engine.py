"""图编排引擎 - 编排多 Agent 协作流程"""
import json
from typing import Any, Dict, List, Optional, Tuple, Callable
from modules.ai.engines.graph_schemas import (
    GraphNode, GraphEdge, GraphNodeType,
    ConsensusResult, PortfolioDecision,
)
from modules.ai.philosophies.base import AgentSignal
from modules.ai.philosophies.registry import PhilosophyRegistry


class GraphEngine:
    """图编排引擎：参考 LangGraph 的有向图状态机，支持多 Agent 协作"""

    def __init__(
        self,
        dal=None,
        router=None,
        progress_callback: Optional[Callable] = None,
    ):
        self.dal = dal
        self.router = router
        self.progress_callback = progress_callback
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []

    # ==================== 图构建 ====================

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node

    def add_edge(self, source: str, target: str):
        self.edges.append(GraphEdge(source=source, target=target))

    def build_philosophy_debate_graph(self, agent_ids: List[str]) -> "GraphEngine":
        """构建投资哲学辩论图: DATA -> FACTOR -> AGENTS(并行) -> AGGREGATE -> PORTFOLIO -> SIGNAL"""
        self.add_node(GraphNode("data", GraphNodeType.DATA, {}))
        self.add_node(GraphNode("factor", GraphNodeType.FACTOR, {}))
        self.add_edge("data", "factor")

        for aid in agent_ids:
            self.add_node(GraphNode(
                f"agent_{aid}", GraphNodeType.AGENT,
                {"agent_id": aid},
                agent_philosophy=aid,
            ))
            self.add_edge("factor", f"agent_{aid}")
            self.add_edge(f"agent_{aid}", "aggregate")

        self.add_node(GraphNode("aggregate", GraphNodeType.AGGREGATE, {}))
        self.add_node(GraphNode("portfolio", GraphNodeType.PORTFOLIO, {}))
        self.add_node(GraphNode("signal", GraphNodeType.SIGNAL, {}))
        self.add_edge("aggregate", "portfolio")
        self.add_edge("portfolio", "signal")
        return self

    # ==================== 执行 ====================

    async def execute(self, stock_code: str, user_context: Optional[Dict] = None) -> Dict[str, Any]:
        from modules.ai.foundation.dal import StockDAL
        from modules.ai.foundation.llm_router import LLMRouter

        if self.dal is None:
            self.dal = StockDAL()
        if self.router is None:
            self.router = LLMRouter()

        order = self._topological_sort()
        results: Dict[str, Any] = {}
        total = len(order)

        for idx, node_id in enumerate(order):
            node = self.nodes[node_id]
            node.status = "running"
            self._report_progress(int((idx / total) * 100), f"执行 {node_id}")

            try:
                if node.type == GraphNodeType.DATA:
                    results[node_id] = await self._exec_data(stock_code)
                elif node.type == GraphNodeType.FACTOR:
                    results[node_id] = await self._exec_factor(results, stock_code)
                elif node.type == GraphNodeType.AGENT:
                    results[node_id] = await self._exec_agent(
                        node, results["factor"], stock_code, user_context
                    )
                elif node.type == GraphNodeType.AGGREGATE:
                    results[node_id] = await self._exec_aggregate(results)
                elif node.type == GraphNodeType.PORTFOLIO:
                    results[node_id] = await self._exec_portfolio(results)
                elif node.type == GraphNodeType.SIGNAL:
                    results[node_id] = await self._exec_signal(results)
                node.status = "completed"
            except Exception as e:
                node.status = "error"
                results[node_id] = {"error": str(e)}

            node.result = results.get(node_id)

        self._report_progress(100, "完成")
        return results

    # ==================== 节点执行器 ====================

    async def _exec_data(self, stock_code: str) -> Dict[str, Any]:
        bundle = self.dal.get_stock_bundle(stock_code)
        return {"stock_code": stock_code, "bundle": bundle}

    async def _exec_factor(self, results: Dict, stock_code: str) -> Dict[str, Any]:
        from modules.ai.foundation.factors import (
            fundamental_score, technical_score, fund_flow_detail_score,
            valuation_detail_score, composite_score,
        )
        bundle = results.get("data", {}).get("bundle")

        fundamental, fund_detail = fundamental_score(
            roe=bundle.roe, revenue_growth=bundle.revenue_growth,
            profit_growth=bundle.profit_growth, gross_margin=bundle.gross_margin,
            debt_ratio=bundle.debt_ratio, industry=bundle.industry,
        )
        technical, tech_detail = technical_score(
            list(reversed(bundle.closes)) if bundle.closes else [],
            list(reversed(bundle.volumes)) if bundle.volumes else [],
        )
        fund_flow, flow_detail = fund_flow_detail_score(
            main_net_inflow=bundle.main_net_inflow,
            total_amount=bundle.total_amount, turnover_rate=bundle.turnover_rate,
        )
        valuation, val_detail = valuation_detail_score(
            pe=bundle.pe, pb=bundle.pb, industry=bundle.industry,
        )

        dim_pairs: Dict[str, Tuple[float, Dict]] = {
            "fundamental": (fundamental, fund_detail),
            "technical": (technical, tech_detail),
            "fund_flow": (fund_flow, flow_detail),
            "valuation": (valuation, val_detail),
        }

        weighted_score, weight_details = composite_score(dim_pairs)

        raw_details: Dict[str, Dict] = {k: v[1] for k, v in dim_pairs.items()}

        flat_details = {}
        for dim, detail in raw_details.items():
            flat: Dict[str, Any] = {"data_available": detail.get("data_available", True)}
            flat["score"] = dim_pairs[dim][0]
            for key, val in detail.items():
                if key == "data_available":
                    continue
                if isinstance(val, dict) and "value" in val:
                    if val["value"] is not None:
                        flat[key] = val["value"]
                    if "score" in val:
                        flat[f"{key}_score"] = val["score"]
                elif isinstance(val, dict) and "score" in val:
                    flat[f"{key}_score"] = val["score"]
                    if val.get("value") is not None:
                        flat[key] = val["value"]
                else:
                    flat[key] = val
            flat_details[dim] = flat

        return {
            "dim_scores": {k: v[0] for k, v in dim_pairs.items()},
            "weighted_score": weighted_score,
            "details": flat_details,
            "weight_details": weight_details,
        }

    async def _exec_agent(
        self,
        node: GraphNode,
        factor_result: Dict,
        stock_code: str,
        user_context: Optional[Dict] = None,
    ) -> AgentSignal:
        agent_id = node.config.get("agent_id", "")
        philosophy = PhilosophyRegistry.get(agent_id)

        if not philosophy:
            return AgentSignal(
                agent_id=agent_id, philosophy="unknown",
                archetype=None, action="hold",
                confidence=0, score=50,
                reasoning=f"未知哲学 {agent_id}",
            )

        dim_scores = factor_result.get("dim_scores", {})
        details = factor_result.get("details", {})

        return philosophy.interpret_signal(dim_scores, details)

    async def _exec_aggregate(self, results: Dict) -> ConsensusResult:
        agent_results = []
        for nid, node in self.nodes.items():
            if node.type == GraphNodeType.AGENT:
                signal = results.get(nid)
                if signal and isinstance(signal, AgentSignal):
                    agent_results.append(signal.to_dict())

        if not agent_results:
            return ConsensusResult(
                tendency=0, consensus_level=0,
                confidence=0, high_conviction=False,
            )

        scores = [s.get("score", 50) for s in agent_results]
        avg_score = sum(scores) / len(scores) if scores else 50
        tendency = (avg_score - 50) / 50

        if len(scores) > 1:
            import statistics
            divergence = statistics.stdev(scores) / 100
        else:
            divergence = 0.5

        consensus = max(0, 1 - divergence)
        confidence = max(0, 1 - divergence * 1.5)

        return ConsensusResult(
            tendency=round(tendency, 3),
            consensus_level=round(consensus, 2),
            confidence=round(confidence, 2),
            high_conviction=divergence < 0.2,
            agent_signals=agent_results,
        )

    async def _exec_portfolio(self, results: Dict) -> PortfolioDecision:
        consensus = results.get("aggregate", ConsensusResult(tendency=0, consensus_level=0, confidence=0, high_conviction=False))

        if consensus.tendency > 0.3 and consensus.high_conviction:
            action = "strong_buy"
            position = "full"
        elif consensus.tendency > 0.1:
            action = "buy"
            position = "half"
        elif consensus.tendency < -0.3 and consensus.high_conviction:
            action = "sell"
            position = "none"
        elif consensus.tendency < -0.1:
            action = "watch"
            position = "quarter"
        else:
            action = "hold"
            position = "quarter"

        return PortfolioDecision(
            action=action,
            position_size=position,
            reasoning=f"共识度{consensus.consensus_level:.0%}，倾向{consensus.tendency:+.2f}",
            risk_level="low" if consensus.high_conviction else "medium",
        )

    async def _exec_signal(self, results: Dict) -> Dict[str, Any]:
        consensus = results.get("aggregate", {})
        portfolio = results.get("portfolio", {})
        return {
            "consensus": consensus,
            "portfolio": portfolio,
        }

    # ==================== 图遍历 ====================

    def _topological_sort(self) -> List[str]:
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}

        for edge in self.edges:
            if edge.source in adj and edge.target in in_degree:
                adj[edge.source].append(edge.target)
                in_degree[edge.target] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            remaining = set(self.nodes.keys()) - set(order)
            order.extend(remaining)

        return order

    def _report_progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)
