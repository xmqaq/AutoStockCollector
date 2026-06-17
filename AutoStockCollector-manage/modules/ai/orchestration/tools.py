"""分析师可调用的数据工具层（有界 ReAct：计划→取数→分析）。

每个工具是 `callable(code) -> str`，返回一段可直接塞进 prompt 的文本摘要。
分析师先按菜单选 0-3 个工具，执行后把结果回灌再做正式分析。
所有工具内部自带兜底，取数失败返回空串，绝不抛出。
"""
from typing import Callable, Dict, List
from utils.logger import get_logger

logger = get_logger(__name__)


def _t_news(code: str) -> str:
    try:
        from core.storage.mongo_storage import NewsStorage
        news = NewsStorage().get_latest_news(code=code, limit=10) or []
        if not news:
            return ""
        lines = [
            f"- [{(n.get('publish_date') or n.get('发布时间') or '')[:10]}] "
            f"{n.get('title') or n.get('标题', '')}"
            for n in news[:10]
        ]
        return "【补充·最新新闻】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning(f"tool news failed for {code}: {e}")
        return ""


def _t_financial(code: str) -> str:
    try:
        from core.storage.mongo_storage import FinancialStorage
        rows = FinancialStorage().find_many(
            {"code": code}, sort=[("report_date", -1)], limit=6) or []
        if not rows:
            return ""
        lines = []
        for f in rows[:6]:
            rd = str(f.get("report_date", ""))[:10]
            rev = f.get("营业总收入") or f.get("revenue")
            npf = f.get("净利润") or f.get("net_profit")
            roe = f.get("净资产收益率") or f.get("roe")
            lines.append(f"- {rd}: 营收{rev} 净利{npf} ROE{roe}")
        return "【补充·财务趋势】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning(f"tool financial failed for {code}: {e}")
        return ""


def _t_fund_flow(code: str) -> str:
    try:
        from core.storage.mongo_storage import FundFlowStorage
        doc = FundFlowStorage().get_latest_flow(code)
        if not doc:
            return ""
        keys = ("main_net_inflow", "主力净流入", "turnover_rate", "换手率",
                "total_amount", "成交额")
        parts = [f"{k}={doc.get(k)}" for k in keys if doc.get(k) is not None]
        return "【补充·资金流】\n" + "，".join(parts) if parts else ""
    except Exception as e:
        logger.warning(f"tool fund_flow failed for {code}: {e}")
        return ""


def _t_dragon_tiger(code: str) -> str:
    try:
        from core.storage.mongo_storage import DragonTigerStorage
        rows = DragonTigerStorage().find_many(
            {"code": code}, sort=[("date", -1)], limit=5) or []
        if not rows:
            return ""
        lines = [
            f"- {str(r.get('date', ''))[:10]}: 净买额"
            f"{r.get('net_buy') or r.get('净买额') or r.get('龙虎榜净买额')}"
            for r in rows[:5]
        ]
        return "【补充·龙虎榜】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning(f"tool dragon_tiger failed for {code}: {e}")
        return ""


def _t_margin(code: str) -> str:
    try:
        from core.storage.mongo_storage import MarginStorage
        rows = MarginStorage().find_many(
            {"code": code}, sort=[("date", -1)], limit=5) or []
        if not rows:
            return ""
        lines = [
            f"- {str(r.get('date', ''))[:10]}: 融资余额"
            f"{r.get('rzye') or r.get('融资余额') or r.get('margin_balance')}"
            for r in rows[:5]
        ]
        return "【补充·融资融券】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning(f"tool margin failed for {code}: {e}")
        return ""


# 工具名 → (一句话描述, 执行函数)
TOOL_REGISTRY: Dict[str, tuple] = {
    "news": ("最近10条个股新闻标题", _t_news),
    "financial": ("近6期财务趋势(营收/净利/ROE)", _t_financial),
    "fund_flow": ("最新主力资金流/换手率/成交额", _t_fund_flow),
    "dragon_tiger": ("近5次龙虎榜净买额", _t_dragon_tiger),
    "margin": ("近5期融资融券余额", _t_margin),
}


def tools_menu() -> str:
    return "\n".join(f"- {name}: {desc}" for name, (desc, _) in TOOL_REGISTRY.items())


def run_tools(names: List[str], code: str, limit: int = 3) -> str:
    """执行选中的工具（去重、上限 limit 个），拼接返回；全失败返回空串。"""
    seen, out = set(), []
    for name in names:
        key = str(name).strip()
        if key in seen or key not in TOOL_REGISTRY:
            continue
        seen.add(key)
        text = TOOL_REGISTRY[key][1](code)
        if text:
            out.append(text)
        if len(seen) >= limit:
            break
    return "\n\n".join(out)
