import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from modules.ai.orchestration.state import TradingState, AnalystOutput, DebateEntry, RiskEntry
from modules.ai.orchestration.nodes import (
    create_data_fetch_node, create_factor_calc_node, create_analyst_node,
    create_bull_node, create_bear_node, create_research_manager_node,
    create_trader_node, create_risk_debater_node, create_portfolio_manager_node,
)
from modules.ai.orchestration.signal_processing import extract_final_verdict
from modules.ai.orchestration.checkpointer import MongoCheckpointer
from utils.logger import get_logger

logger = get_logger(__name__)


class GraphNode:
    def __init__(self, name: str, fn, children: List[str] = None):
        self.name = name
        self.fn = fn
        self.children = children or []


class TradingGraph:
    ANALYST_IDS = [
        "market_analyst", "technical_analyst", "fund_analyst",
        "fundamental_analyst", "sentiment_analyst", "risk_analyst",
    ]

    def __init__(self):
        self.checkpointer = MongoCheckpointer()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._build_nodes()

    def _build_nodes(self):
        self.nodes: Dict[str, GraphNode] = {}

        self.nodes["data_fetch"] = GraphNode("data_fetch", create_data_fetch_node(), ["factor_calc"])
        self.nodes["factor_calc"] = GraphNode("factor_calc", create_factor_calc_node(), ["analyst_team"])

        self.nodes["analyst_team"] = GraphNode("analyst_team", self._run_analyst_team, ["debate"])

        self.nodes["debate"] = GraphNode("debate", self._run_debate, ["research_manager"])

        for aid in self.ANALYST_IDS:
            name_map = {
                "market_analyst": "市场分析师", "technical_analyst": "技术分析师",
                "fund_analyst": "资金分析师", "fundamental_analyst": "基本面分析师",
                "sentiment_analyst": "舆情分析师", "risk_analyst": "风险分析师",
            }
            self.nodes[f"analyst_{aid}"] = GraphNode(
                f"analyst_{aid}", create_analyst_node(aid, name_map.get(aid, aid)), []
            )

        self.nodes["bull_analyst"] = GraphNode("bull_analyst", create_bull_node(), [])
        self.nodes["bear_analyst"] = GraphNode("bear_analyst", create_bear_node(), [])
        self.nodes["research_manager"] = GraphNode("research_manager", create_research_manager_node(), ["trader"])
        self.nodes["trader"] = GraphNode("trader", create_trader_node(), ["risk_debate_team"])

        self.nodes["risk_debate_team"] = GraphNode("risk_debate_team", self._run_risk_debate_team, ["portfolio_manager"])

        for debater_id, name, stance in [
            ("aggressive", "激进风控师", "激进"),
            ("conservative", "保守风控师", "保守"),
            ("neutral", "中性风控师", "中性"),
        ]:
            self.nodes[f"risk_{debater_id}"] = GraphNode(
                f"risk_{debater_id}", create_risk_debater_node(debater_id, name, stance), []
            )

        self.nodes["portfolio_manager"] = GraphNode("portfolio_manager", create_portfolio_manager_node(), [])

    def _run_analyst_team(self, state: TradingState):
        futures = {}
        for aid in self.ANALYST_IDS:
            agent_id = f"analyst_{aid}"
            node = self.nodes.get(agent_id)
            if node:
                fut = self._executor.submit(node.fn, state)
                futures[aid] = fut

        for aid, fut in futures.items():
            try:
                result = fut.result(timeout=120)
                if result and "analyst_outputs" in result:
                    state.analyst_outputs.update(result["analyst_outputs"])
            except Exception as e:
                logger.error(f"Analyst team member {aid} failed: {e}")
                state.errors.append(f"analyst_team_{aid}: {e}")

        return {"analyst_outputs": state.analyst_outputs}

    def _run_debate(self, state: TradingState):
        """多空多轮辩论：每轮 bull 先发、bear 针对反驳，逐轮写入 debate_history。

        max_debate_rounds 控制轮数；若某轮多空净倾向已高度一致（分差<5）则提前收敛，
        避免无谓的 LLM 调用。最终 bull_analysis/bear_analysis 保留最后一轮，供研判与裁决。
        """
        bull_fn = self.nodes["bull_analyst"].fn
        bear_fn = self.nodes["bear_analyst"].fn
        rounds = max(1, getattr(state, "max_debate_rounds", 1))

        for i in range(rounds):
            state.debate_round = i + 1
            bull_fn(state)
            bear_fn(state)
            state.debate_history.append(DebateEntry(
                round_number=state.debate_round,
                bull_argument=state.bull_analysis,
                bear_argument=state.bear_analysis,
                bull_score=state.bull_score,
                bear_score=state.bear_score,
            ))
            state.add_event("graph:node_stream", {
                "node_id": "debate",
                "content": f"第{state.debate_round}轮：多头{state.bull_score} vs 空头{state.bear_score}",
            })
            # 提前收敛：多头看涨度与空头看跌度的净倾向已趋同
            net = (state.bull_score + (100 - state.bear_score)) / 2
            if i >= 1 and abs(net - 50) < 5:
                break

        return {
            "bull_analysis": state.bull_analysis, "bear_analysis": state.bear_analysis,
            "bull_score": state.bull_score, "bear_score": state.bear_score,
            "debate_history": state.debate_history,
        }

    def _run_risk_debate_team(self, state: TradingState):
        debaters = ["aggressive", "conservative", "neutral"]
        futures = {}
        for debater_id in debaters:
            node_name = f"risk_{debater_id}"
            node = self.nodes.get(node_name)
            if node:
                fut = self._executor.submit(node.fn, state)
                futures[debater_id] = fut

        for debater_id, fut in futures.items():
            try:
                fut.result(timeout=60)
            except Exception as e:
                logger.error(f"Risk debater {debater_id} failed: {e}")

        return {"risk_assessments": state.risk_assessments, "risk_discuss_history": state.risk_discuss_history}

    def _serialize_state(self, state: TradingState) -> Dict[str, Any]:
        d = dict(state.__dict__)
        d["analyst_outputs"] = {k: v.to_dict() for k, v in d.get("analyst_outputs", {}).items()}
        d["debate_history"] = [
            {"round_number": e.round_number, "bull_argument": e.bull_argument,
             "bear_argument": e.bear_argument, "bull_score": e.bull_score, "bear_score": e.bear_score}
            for e in d.get("debate_history", [])
        ]
        d["risk_discuss_history"] = [
            {"agent_id": e.agent_id, "stance": e.stance, "argument": e.argument, "risk_score": e.risk_score}
            for e in d.get("risk_discuss_history", [])
        ]
        return d

    @staticmethod
    def _deserialize_state(state: TradingState, checkpoint: Dict[str, Any]):
        for key, val in checkpoint.items():
            if key == "analyst_outputs":
                state.analyst_outputs = {
                    k: AnalystOutput(**v) if isinstance(v, dict) else v
                    for k, v in val.items()
                }
            elif key == "debate_history":
                state.debate_history = [
                    DebateEntry(**e) if isinstance(e, dict) else e for e in val
                ]
            elif key == "risk_discuss_history":
                state.risk_discuss_history = [
                    RiskEntry(**e) if isinstance(e, dict) else e for e in val
                ]
            else:
                setattr(state, key, val)

    def _execute_node(self, node_name: str, state: TradingState) -> Dict[str, Any]:
        node = self.nodes.get(node_name)
        if not node:
            logger.warning(f"Node {node_name} not found")
            return {}
        return node.fn(state)

    def run(self, stock_code: str, run_id: Optional[str] = None,
            user_id: str = "default") -> Dict[str, Any]:
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        state = TradingState(stock_code=stock_code, user_id=user_id)

        logger.info(f"[TradingGraph] Starting run {run_id} for {stock_code}")

        checkpoint = self.checkpointer.load(run_id)
        if checkpoint:
            self._deserialize_state(state, checkpoint)
            logger.info(f"[TradingGraph] Resumed from checkpoint {run_id}")

        execution_order = [
            "data_fetch", "factor_calc", "analyst_team",
            "debate",
            "research_manager", "trader",
            "risk_debate_team", "portfolio_manager",
        ]

        try:
            for node_name in execution_order:
                logger.info(f"[TradingGraph] Executing node: {node_name}")
                self._execute_node(node_name, state)
                self.checkpointer.save(run_id, self._serialize_state(state))
        except Exception as e:
            logger.error(f"[TradingGraph] Run {run_id} failed at node {node_name}: {e}")
            state.errors.append(f"graph_execution: {e}")

        verdict = extract_final_verdict(state)
        result = {
            "run_id": run_id,
            "stock_code": stock_code,
            "status": "completed" if not state.errors else "completed_with_errors",
            "errors": state.errors,
            "verdict": verdict,
            "events": state.stream_events,
            "analyst_outputs": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v
                for k, v in state.analyst_outputs.items()
            },
            "final_decision": state.final_decision,
        }

        logger.info(f"[TradingGraph] Run {run_id} completed")
        return result

    def run_stream(self, stock_code: str, run_id: Optional[str] = None,
                   user_id: str = "default"):
        """逐节点真流式：每个节点执行完立即把新产生的事件 yield 出去（而非跑完回放）。

        最后 yield 一个 verdict 事件与 done 事件，并落决策记录。
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        state = TradingState(stock_code=stock_code, user_id=user_id)

        checkpoint = self.checkpointer.load(run_id)
        if checkpoint:
            self._deserialize_state(state, checkpoint)

        execution_order = [
            "data_fetch", "factor_calc", "analyst_team",
            "debate",
            "research_manager", "trader",
            "risk_debate_team", "portfolio_manager",
        ]

        emitted = 0
        try:
            for node_name in execution_order:
                self._execute_node(node_name, state)
                self.checkpointer.save(run_id, self._serialize_state(state))
                while emitted < len(state.stream_events):
                    yield state.stream_events[emitted]
                    emitted += 1
        except Exception as e:
            logger.error(f"[TradingGraph] Stream run {run_id} failed: {e}")
            state.errors.append(f"graph_execution: {e}")
            while emitted < len(state.stream_events):
                yield state.stream_events[emitted]
                emitted += 1

        verdict = extract_final_verdict(state)
        try:
            from modules.ai.reflection.decision_logger import DecisionLogger
            DecisionLogger().log_decision(run_id, stock_code, state.final_decision or {})
        except Exception as e:
            logger.warning(f"Decision log failed in stream: {e}")

        yield {"event": "graph:complete", "data": {"verdict": verdict, "run_id": run_id}}
        yield {"event": "done", "data": {}}


def create_trading_graph() -> TradingGraph:
    return TradingGraph()
