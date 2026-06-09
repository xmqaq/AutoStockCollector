"""MCP 协议桥 - 为 Agent 提供标准化的工具调用接口"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class MCPCallResult:
    """MCP 调用结果"""
    success: bool
    tool_name: str
    data: Any = None
    error: str = ""
    elapsed_ms: float = 0.0


class MCPBridge:
    """MCP 协议桥：Agent 通过此桥调用金融数据工具"""

    _tools: Dict[str, MCPTool] = {}

    @classmethod
    def register_tool(cls, tool: MCPTool):
        cls._tools[tool.name] = tool

    @classmethod
    def get_tool(cls, name: str) -> Optional[MCPTool]:
        return cls._tools.get(name)

    @classmethod
    def get_all_tools(cls) -> List[MCPTool]:
        return list(cls._tools.values())

    @classmethod
    async def call_tool(cls, tool_name: str, params: Dict[str, Any]) -> MCPCallResult:
        tool = cls._tools.get(tool_name)
        if not tool:
            return MCPCallResult(
                success=False, tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
            )
        start = datetime.now()
        try:
            result = tool.handler(**params)
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return MCPCallResult(
                success=True, tool_name=tool_name,
                data=result, elapsed_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return MCPCallResult(
                success=False, tool_name=tool_name,
                error=str(e), elapsed_ms=round(elapsed, 1),
            )


# ==================== 注册 A 股专用 MCP 工具 ====================


def _strip_code(code: str) -> str:
    return code[2:] if code[:2] in ("SH", "SZ") else code

def _analyze_dragon_tiger(code: str = "", date: str = "") -> Dict:
    """龙虎榜席位分析"""
    try:
        code = _strip_code(code)
        from core.storage.mongo_storage import DragonTigerStorage
        storage = DragonTigerStorage()
        query = {}
        if code:
            query["code"] = code
        if date:
            query["date"] = date
        records = list(storage.collection.find(query).sort("date", -1).limit(10))
        for r in records:
            r.pop("_id", None)
        return {"records": records, "count": len(records)}
    except Exception as e:
        return {"error": str(e), "records": []}


def _analyze_sentiment(code: str = "") -> Dict:
    """新闻舆情分析"""
    try:
        code = _strip_code(code)
        from core.storage.mongo_storage import NewsStorage
        storage = NewsStorage()
        query = {"code": code} if code else {}
        records = list(storage.collection.find(query).sort("publish_date", -1).limit(20))
        for r in records:
            r.pop("_id", None)
            r.pop("_updated_at", None)
        return {"records": records, "count": len(records)}
    except Exception as e:
        return {"error": str(e), "records": []}


def _analyze_fund_flow(code: str = "") -> Dict:
    """资金流向分析"""
    try:
        from core.storage.mongo_storage import FundFlowStorage
        storage = FundFlowStorage()
        code = code[2:] if code[:2] in ("SH", "SZ") else code
        record = storage.get_latest_flow(code)
        return {"record": record} if record else {"error": "No data"}
    except Exception as e:
        return {"error": str(e)}


def _analyze_financial(code: str = "") -> Dict:
    """财务数据分析"""
    try:
        code = _strip_code(code)
        from core.storage.mongo_storage import FinancialStorage
        storage = FinancialStorage()
        records = list(storage.collection.find(
            {"code": code}, sort=[("report_date", -1)], limit=4
        ))
        for r in records:
            r.pop("_id", None)
        return {"records": records, "count": len(records)}
    except Exception as e:
        return {"error": str(e), "records": []}


def _get_kline_trend(code: str = "", days: int = 60) -> Dict:
    """K线趋势分析"""
    try:
        code = _strip_code(code)
        from core.storage.mongo_storage import KlineStorage
        storage = KlineStorage()
        records = list(storage.collection.find(
            {"code": code}, sort=[("date", -1)], limit=days
        ))
        for r in records:
            r.pop("_id", None)
            if "date" in r and hasattr(r["date"], "strftime"):
                r["date"] = r["date"].strftime("%Y-%m-%d")
        return {"records": records, "count": len(records)}
    except Exception as e:
        return {"error": str(e), "records": []}


def _get_capital_flow(**kwargs) -> Dict:
    """全市场资金流向"""
    try:
        from core.storage.mongo_storage import FundFlowStorage
        storage = FundFlowStorage()
        import pymongo
        latest = storage.collection.find_one(
            {"main_net_inflow": {"$exists": True}},
            sort=[("date", pymongo.DESCENDING)]
        )
        if latest is None:
            return {"error": "No capital flow data available"}
        return {"date": latest.get("date"), "market_flow": "positive" if latest.get("main_net_inflow", 0) > 0 else "negative"}
    except Exception as e:
        return {"error": str(e)}


MCPBridge.register_tool(MCPTool(
    name="dragon_tiger_analysis",
    description="龙虎榜席位分析：解析营业部操作风格，识别游资同盟和资金动向",
    input_schema={"code": {"type": "string"}, "date": {"type": "string"}},
    handler=_analyze_dragon_tiger,
))

MCPBridge.register_tool(MCPTool(
    name="news_sentiment",
    description="新闻舆情分析：获取个股相关新闻，分析市场情绪",
    input_schema={"code": {"type": "string"}},
    handler=_analyze_sentiment,
))

MCPBridge.register_tool(MCPTool(
    name="fund_flow_analysis",
    description="资金流向分析：个股主力资金净流入/流出情况",
    input_schema={"code": {"type": "string"}},
    handler=_analyze_fund_flow,
))

MCPBridge.register_tool(MCPTool(
    name="financial_analysis",
    description="财务数据分析：获取净资产收益率、营收增速、净利润等关键财务指标",
    input_schema={"code": {"type": "string"}},
    handler=_analyze_financial,
))

MCPBridge.register_tool(MCPTool(
    name="kline_trend",
    description="K线趋势分析：获取个股历史K线数据，分析价格趋势",
    input_schema={"code": {"type": "string"}, "days": {"type": "integer"}},
    handler=_get_kline_trend,
))

MCPBridge.register_tool(MCPTool(
    name="market_capital_flow",
    description="全市场资金流向：判断市场整体资金多空方向",
    input_schema={},
    handler=_get_capital_flow,
))
