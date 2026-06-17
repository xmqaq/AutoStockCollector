"""
AI高级分析接口
包含：批量分析、多Agent协作分析、实时进度追踪
支持MongoDB持久化存储
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading
import time
import uuid
from utils.logger import get_logger
from utils.helpers import beijing_now

logger = get_logger(__name__)

ai_advanced_bp = Blueprint("ai_advanced", __name__, url_prefix="/api/v1/ai")


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _normalize_code(code: str) -> str:
    from utils.helpers import normalize_stock_code_flexible
    return normalize_stock_code_flexible(code)


def _save_batch_task_to_db(task_id: str, task_data: Dict):
    """保存批量任务到MongoDB"""
    db = _get_db()
    task_data["task_id"] = task_id
    task_data["updated_at"] = beijing_now().isoformat()

    existing = db["batch_tasks"].find_one({"task_id": task_id})
    if existing:
        db["batch_tasks"].update_one(
            {"task_id": task_id},
            {"$set": task_data}
        )
    else:
        task_data["created_at"] = beijing_now().isoformat()
        db["batch_tasks"].insert_one(task_data)


def _get_batch_task_from_db(task_id: str) -> Optional[Dict]:
    """从MongoDB获取批量任务"""
    db = _get_db()
    task = db["batch_tasks"].find_one({"task_id": task_id})
    if task:
        task.pop("_id", None)
    return task


def _get_batch_tasks_from_db(limit: int = 20) -> List[Dict]:
    """获取所有批量任务"""
    db = _get_db()
    tasks = list(db["batch_tasks"].find(
        sort=[("created_at", -1)],
        limit=limit
    ))
    for task in tasks:
        task.pop("_id", None)
    return tasks


@ai_advanced_bp.route("/batch-analyze", methods=["POST"])
def batch_analyze():
    """批量AI分析接口"""
    data = request.get_json() or {}
    codes = data.get("codes", [])
    analysis_type = data.get("type", "comprehensive")

    if not codes:
        return jsonify({"error": "codes is required"}), 400

    task_id = f"batch_{uuid.uuid4().hex[:12]}"
    task_data = {
        "codes": codes,
        "type": analysis_type,
        "status": "pending",
        "total": len(codes),
        "completed": 0,
        "failed": 0,
        "results": [],
        "errors": [],
        "current": None,
        "started_at": None,
        "completed_at": None,
    }

    _save_batch_task_to_db(task_id, task_data)

    thread = threading.Thread(
        target=_simulate_batch_analysis,
        args=(task_id, codes, analysis_type)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "total": len(codes),
        "message": "批量分析任务已创建"
    })


def _simulate_batch_analysis(task_id: str, codes: List[str], analysis_type: str):
    """模拟批量分析任务"""
    task_data = {
        "status": "running",
        "started_at": beijing_now().isoformat()
    }
    _save_batch_task_to_db(task_id, task_data)

    from modules.ai.ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer()

    for i, code in enumerate(codes):
        task_data = {
            "completed": i,
            "current": code
        }
        _save_batch_task_to_db(task_id, task_data)

        try:
            result = analyzer.analyze(code, analysis_type)
            task_data = {
                "results": [{"code": code, **result}]
            }
            _save_batch_task_to_db(task_id, task_data)
        except Exception as e:
            task_data = {
                "errors": [{"code": code, "error": str(e)}]
            }
            _save_batch_task_to_db(task_id, task_data)

        time.sleep(0.5)

    task_data = {
        "status": "completed",
        "completed": len(codes),
        "completed_at": beijing_now().isoformat()
    }
    _save_batch_task_to_db(task_id, task_data)


@ai_advanced_bp.route("/batch-progress/<task_id>", methods=["GET"])
def get_batch_progress(task_id: str):
    """获取批量分析进度"""
    task = _get_batch_task_from_db(task_id)

    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status"),
        "total": task.get("total"),
        "completed": task.get("completed"),
        "failed": task.get("failed"),
        "current": task.get("current"),
        "results": task.get("results", [])[-50:],
        "errors": task.get("errors", [])[-10:],
    })


@ai_advanced_bp.route("/batch-tasks", methods=["GET"])
def list_batch_tasks():
    """列出所有批量分析任务"""
    tasks = _get_batch_tasks_from_db()
    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks
    })


# ═══════════════════════════════════════════════════════════════
# 多空辩论 + 风险管控（SSE 流式实时推送）
# ═══════════════════════════════════════════════════════════════

def _fetch_all_stock_data(code: str) -> Dict[str, Any]:
    """采集全面的股票数据，返回结构化数据字典"""
    result: Dict[str, Any] = {
        "code": code,
        "kline_data": [],
        "stock_info": {},
        "fund_flow_data": {},
        "news_data": [],
        "financial_data": {},
        "margin_data": [],
    }
    try:
        from core.storage.mongo_storage import (
            KlineStorage, FundFlowStorage, NewsStorage,
            StockInfoStorage, FinancialStorage, MarginStorage,
        )
        kline_storage = KlineStorage()
        result["kline_data"] = list(kline_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=60
        ))
        stock_info_storage = StockInfoStorage()
        result["stock_info"] = stock_info_storage.get_by_code(code) or {}
        fund_storage = FundFlowStorage()
        result["fund_flow_data"] = fund_storage.get_latest_flow(code) or {}
        news_storage = NewsStorage()
        bare_code = code[2:] if code[:2] in ("SH", "SZ") else code
        stock_news = list(news_storage.find_many(
            {"code": {"$in": [code, bare_code]}},
            sort=[("publish_date", -1)], limit=10
        ))
        if not stock_news:
            stock_news = list(news_storage.find_many(
                {}, sort=[("publish_date", -1)], limit=10
            ))
        result["news_data"] = stock_news
        financial_storage = FinancialStorage()
        fin_records = list(financial_storage.find_many(
            {"code": code}, sort=[("report_date", -1)], limit=1
        ))
        if fin_records:
            result["financial_data"] = fin_records[0]
        margin_storage = MarginStorage()
        result["margin_data"] = list(margin_storage.find_many(
            {"code": code}, sort=[("date", -1)], limit=10
        ))
    except Exception as e:
        logger.warning(f"Failed to fetch stock data for debate: {e}")
    return result


def _format_stock_data_text(data: Dict[str, Any]) -> str:
    """将结构化股票数据格式化为LLM上下文文本"""
    code = data["code"]
    si = data.get("stock_info", {}) or {}
    kd = data.get("kline_data", []) or []
    fd = data.get("fund_flow_data", {}) or {}
    nd = data.get("news_data", []) or []
    md = data.get("margin_data", []) or []
    fin = data.get("financial_data", {}) or {}

    stock_name = si.get("name", "未知")

    pe = si.get("pe") or si.get("pe_ttm") or "暂无"
    pb = si.get("pb") or "暂无"
    industry = si.get("industry") or si.get("所属行业", "未知")
    market_cap = si.get("market_cap") or si.get("总市值", "暂无")
    roe = si.get("roe") or "暂无"
    total_shares = si.get("total_shares") or si.get("总股本", "暂无")

    def _kget(row, *keys):
        for k in keys:
            v = row.get(k)
            if v is not None and v != "":
                return v
        return ""

    kline_text = ""
    for k in kd[:15]:
        d = _kget(k, "date", "日期")
        c = _kget(k, "close", "收盘", "收盘价")
        h = _kget(k, "high", "最高", "最高价")
        lo = _kget(k, "low", "最低", "最低价")
        v = _kget(k, "volume", "成交量")
        a = _kget(k, "amount", "成交额")
        kline_text += f"  {d}  收盘:{c}  最高:{h}  最低:{lo}  成交量:{v}  成交额:{a}\n"

    main_net = fd.get("main_net_inflow") or fd.get("净额") or "暂无"
    retail_net = fd.get("retail_net_inflow") or "暂无"
    total_amount_flow = fd.get("total_amount") or fd.get("成交额") or "暂无"
    turnover = fd.get("turnover_rate") or fd.get("换手率") or "暂无"
    change_pct = fd.get("change_pct") or fd.get("涨跌幅") or "暂无"

    def _get_fin(keys):
        for k in keys:
            v = fin.get(k)
            if v is not None and str(v).strip():
                return v
        return "暂无"

    rev_growth = _get_fin(["revenue_growth", "营业总收入同比增长率", "营业收入同比增长率", "营业收入增长率"])
    profit_growth = _get_fin(["profit_growth", "净利润同比增长率", "净利润增长率"])
    gross_margin = _get_fin(["gross_margin", "销售毛利率", "毛利率"])
    debt_ratio = _get_fin(["debt_ratio", "资产负债率"])
    revenue = _get_fin(["营业总收入", "营业收入", "revenue"])
    net_profit = _get_fin(["净利润", "归属母公司股东的净利润", "net_profit"])
    report_date = _get_fin(["report_date", "报告期"])

    news_lines = []
    for n in nd[:8]:
        if isinstance(n, dict):
            title = n.get("title", "")
            pub = n.get("publish_date", "")
            src = n.get("source", "")
            if title:
                news_lines.append(f"  - [{pub}] {title}（{src}）" if pub else f"  - {title}")
    top_news = "\n".join(news_lines) or "  暂无"

    margin_text = ""
    for m in md[:5]:
        date_val = m.get("date", "")
        mb = m.get("margin_balance") or m.get("融资余额") or m.get("融资余额(元)") or "暂无"
        sb = m.get("short_balance") or m.get("融券余额") or m.get("融券余额(元)") or "暂无"
        margin_text += f"  - 日期:{date_val} 融资余额:{mb} 融券余额:{sb}\n"

    return f"""
【股票基本信息】
- 代码：{code} 名称：{stock_name} 行业：{industry}
- 市盈率(PE)：{pe} 市净率(PB)：{pb} ROE：{roe}
- 总市值：{market_cap} 总股本：{total_shares}

【K线行情（最新15日，按日期降序）】
{kline_text if kline_text.strip() else '  暂无数据'}

【财务数据（报告期：{report_date}）】
- 营业总收入：{revenue}
- 净利润：{net_profit}
- 营收同比增长率：{rev_growth}
- 净利润同比增长率：{profit_growth}
- 销售毛利率：{gross_margin}
- 资产负债率：{debt_ratio}

【资金流向】
- 主力净流入：{main_net}
- 散户净流入：{retail_net}
- 总成交额：{total_amount_flow}
- 换手率：{turnover}
- 涨跌幅：{change_pct}

【融资融券（最近5日）】
{margin_text if margin_text.strip() else '  暂无数据'}

【最新新闻与舆情】
{top_news}
"""


def _calculate_debate_factors(data: Dict[str, Any]) -> Dict[str, Any]:
    """计算多维度因子评分，返回因子得分与详细数据"""
    from modules.ai.foundation.factors import (
        fundamental_score, technical_score,
        fund_flow_detail_score, valuation_detail_score,
        composite_score,
    )

    kd = data.get("kline_data", []) or []
    si = data.get("stock_info", {}) or {}
    fd = data.get("fund_flow_data", {}) or {}
    fin = data.get("financial_data", {}) or {}

    # kd 按 date DESC 排列，technical_score 要求正序（旧→新），需要反转
    kd_asc = list(reversed(kd))

    def _kval(row, *keys):
        for k in keys:
            v = row.get(k)
            if v is not None:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
        return None

    closes = [v for k in kd_asc if (v := _kval(k, "close", "收盘", "收盘价")) is not None]
    amounts = [v for k in kd_asc if (v := _kval(k, "amount", "成交额")) is not None]
    industry = si.get("industry") or si.get("所属行业", "")
    pe = si.get("pe") or si.get("pe_ttm")
    pb = si.get("pb")
    roe = si.get("roe")

    def _safe_float(v, default=None):
        if v is None:
            return default
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    roe = _safe_float(roe)
    pe = _safe_float(pe)
    pb = _safe_float(pb)

    def _get_first_float(*keys):
        for k in keys:
            v = _safe_float(fin.get(k))
            if v is not None:
                return v
        return None

    revenue_growth = _get_first_float("revenue_growth", "营业总收入同比增长率", "营业收入同比增长率", "营业收入增长率")
    profit_growth = _get_first_float("profit_growth", "净利润同比增长率", "净利润增长率")
    gross_margin = _get_first_float("gross_margin", "销售毛利率", "毛利率")
    debt_ratio = _get_first_float("debt_ratio", "资产负债率")

    main_net = _safe_float(fd.get("main_net_inflow") or fd.get("净额"))
    total_amount_flow = _safe_float(fd.get("total_amount") or fd.get("成交额"))
    turnover_rate = _safe_float(fd.get("turnover_rate") or fd.get("换手率"))

    dim_scores: Dict[str, Any] = {}

    tech_s, tech_d = technical_score(closes, amounts) if closes and amounts else (50, {"data_available": False})
    dim_scores["technical"] = (tech_s, tech_d)

    funda_s, funda_d = fundamental_score(
        roe=roe, revenue_growth=revenue_growth,
        profit_growth=profit_growth, gross_margin=gross_margin,
        debt_ratio=debt_ratio, industry=industry,
    )
    dim_scores["fundamental"] = (funda_s, funda_d)

    flow_s, flow_d = fund_flow_detail_score(main_net, total_amount_flow, turnover_rate)
    dim_scores["fund_flow"] = (flow_s, flow_d)

    val_s, val_d = valuation_detail_score(pe, pb, industry)
    dim_scores["valuation"] = (val_s, val_d)

    weights = {"fundamental": 0.30, "technical": 0.25, "fund_flow": 0.20, "valuation": 0.15, "size": 0.10}
    composite, _ = composite_score(dim_scores, weights)

    kline_count = len(kd)
    news_count = len(data.get("news_data", []))
    margin_count = len(data.get("margin_data", []))

    return {
        "technical": {"score": round(tech_s, 1), "details": tech_d},
        "fundamental": {"score": round(funda_s, 1), "details": funda_d},
        "fund_flow": {"score": round(flow_s, 1), "details": flow_d},
        "valuation": {"score": round(val_s, 1), "details": val_d},
        "composite": round(composite, 1),
        "data_quality": {
            "kline_days": kline_count,
            "has_financial": bool(data.get("financial_data")),
            "has_fund_flow": bool(fd),
            "news_count": news_count,
            "has_margin": margin_count > 0,
        },
    }


def _format_factor_text(factors: Dict[str, Any]) -> str:
    """将因子评分结果格式化为LLM上下文文本"""
    comp = factors.get("composite", 50)
    lines = [f"【量化因子评分】（综合评分：{comp}/100）\n"]

    for key, label in [("technical", "技术面"), ("fundamental", "基本面"),
                        ("fund_flow", "资金面"), ("valuation", "估值")]:
        f = factors.get(key, {})
        score = f.get("score", 50)
        details = f.get("details", {})
        lines.append(f"  {label}评分：{score}/100")
        if isinstance(details, dict):
            for k, v in details.items():
                if isinstance(v, dict) and "score" in v:
                    lines.append(f"    - {k}: {v.get('value', 'N/A')} → {v['score']}分")
                elif isinstance(v, str) and v:
                    lines.append(f"    - {k}: {v}")

    dq = factors.get("data_quality", {})
    lines.append(f"\n【数据质量】")
    lines.append(f"  K线天数：{dq.get('kline_days', 0)}")
    lines.append(f"  财务数据：{'✓' if dq.get('has_financial') else '✗'}")
    lines.append(f"  资金流向：{'✓' if dq.get('has_fund_flow') else '✗'}")
    lines.append(f"  新闻数量：{dq.get('news_count', 0)}")
    lines.append(f"  融资融券：{'✓' if dq.get('has_margin') else '✗'}")

    return "\n".join(lines)


_BASE_AGENT_IDS = [
    "market_analyst",
    "technical_analyst",
    "fund_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "risk_analyst",
]


@ai_advanced_bp.route("/debate/stream", methods=["POST"])
def debate_stream():
    """多空辩论 + 风险管控（SSE 流式推送，实时可见进度和内容）"""
    from flask import Response
    import json as _json

    data = request.get_json() or {}
    code = data.get("code")
    if not code:
        return jsonify({"error": "code is required"}), 400
    code = _normalize_code(code)

    def generate():
        from modules.ai.foundation.llm_router import LLMRouter

        router = LLMRouter()
        db = _get_db()

        # ═══════════════════════════════════════════
        # 阶段1: 数据采集
        # ═══════════════════════════════════════════
        yield f"data: {_json.dumps({'event': 'data:start', 'message': '开始采集多维度股票数据...'})}\n\n"
        data_sources = [
            ("kline", "K线行情数据"),
            ("stock_info", "股票基本信息"),
            ("fund_flow", "资金流向数据"),
            ("news", "新闻舆情数据"),
            ("financial", "财务数据"),
            ("margin", "融资融券数据"),
        ]
        stock_data = _fetch_all_stock_data(code)
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 0, 'total': len(data_sources), 'name': 'kline', 'label': 'K线行情数据', 'status': 'done'})}\n\n"
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 1, 'total': len(data_sources), 'name': 'stock_info', 'label': '股票基本信息', 'status': 'done'})}\n\n"
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 2, 'total': len(data_sources), 'name': 'fund_flow', 'label': '资金流向数据', 'status': 'done'})}\n\n"
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 3, 'total': len(data_sources), 'name': 'news', 'label': '新闻舆情数据', 'status': 'done'})}\n\n"
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 4, 'total': len(data_sources), 'name': 'financial', 'label': '财务数据', 'status': 'done'})}\n\n"
        yield f"data: {_json.dumps({'event': 'data:progress', 'index': 5, 'total': len(data_sources), 'name': 'margin', 'label': '融资融券数据', 'status': 'done'})}\n\n"
        stock_data_text = _format_stock_data_text(stock_data)
        yield f"data: {_json.dumps({'event': 'data:done'})}\n\n"

        # ═══════════════════════════════════════════
        # 阶段2: 因子计算
        # ═══════════════════════════════════════════
        yield f"data: {_json.dumps({'event': 'factor:start', 'message': '开始计算多维度量化因子...'})}\n\n"
        factor_names = [
            ("technical", "技术面因子"),
            ("fundamental", "基本面因子"),
            ("fund_flow", "资金面因子"),
            ("valuation", "估值因子"),
        ]
        factor_results = _calculate_debate_factors(stock_data)
        for fi, (fk, fl) in enumerate(factor_names):
            yield f"data: {_json.dumps({'event': 'factor:progress', 'index': fi, 'total': len(factor_names), 'name': fk, 'label': fl, 'status': 'done', 'score': factor_results.get(fk, {}).get('score', 0)})}\n\n"
        factor_text = _format_factor_text(factor_results)
        yield f"data: {_json.dumps({'event': 'factor:done', 'data': factor_results})}\n\n"

        # ═══════════════════════════════════════════
        # 阶段3: 6位基础分析师 (使用LangGraph编排)
        # ═══════════════════════════════════════════
        enriched_context = f"{stock_data_text}\n\n{factor_text}"

        yield f"data: {_json.dumps({'event': 'base:start', 'message': '6位基础分析师开始分析...'})}\n\n"
        base_results: Dict[str, str] = {}

        for idx, agent_id in enumerate(_BASE_AGENT_IDS):
            agent_doc = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
            agent_name = agent_doc["name"] if agent_doc else agent_id
            yield f"data: {_json.dumps({'event': 'agent:start', 'agent_id': agent_id, 'name': agent_name, 'index': idx, 'total': len(_BASE_AGENT_IDS)})}\n\n"

            agent_full = ""
            try:
                if agent_doc:
                    prompt = f"""{agent_doc['system_prompt']}

【原始数据】
{enriched_context}

请结合以上原始数据和量化因子评分，给出专业的分析和建议。"""
                    for chunk in router.chat_stream(
                        prompt, use_cache=False,
                        task_type=f"debate_base_{agent_id}"
                    ):
                        if chunk:
                            agent_full += chunk
                            yield f"data: {_json.dumps({'event': 'agent:content', 'agent_id': agent_id, 'data': chunk})}\n\n"
            except Exception as e:
                logger.error(f"Base agent {agent_id} failed: {e}")
                agent_full = f"（{agent_name}分析暂不可用）"

            base_results[agent_id] = agent_full
            yield f"data: {_json.dumps({'event': 'agent:done', 'agent_id': agent_id, 'name': agent_name})}\n\n"

        # 拼接6个基础分析结果作为上下文
        base_context_parts = []
        for agent_id in _BASE_AGENT_IDS:
            doc = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
            name = doc["name"] if doc else agent_id
            content = base_results.get(agent_id, "")
            truncated = content[:1500] if content else "（无数据）"
            base_context_parts.append(f"【{name}】\n{truncated}")

        base_context = "\n\n".join(base_context_parts)
        yield f"data: {_json.dumps({'event': 'base:done'})}\n\n"

        # ═══════════════════════════════════════════
        # 阶段4: 多头分析师
        # ═══════════════════════════════════════════
        yield f"data: {_json.dumps({'event': 'bull:start', 'message': '多头分析师开始辩论...'})}\n\n"
        bull_full = ""
        try:
            bull_agent = db["ai_agents"].find_one({"id": "bull_analyst"}, {"_id": 0})
            if bull_agent:
                prompt = f"""{bull_agent['system_prompt']}

【原始数据与量化因子】
{enriched_context}

【6位基础分析师观点】
{base_context}

请综合以上原始数据、量化因子和基础分析观点，从多头视角进行全面辩论。

【重要】你必须在回答的最后一行单独给出综合评分，格式严格为：
综合评分：XX/100
其中XX是0-100的整数（0=完全没有看涨理由，100=极度看涨）。这一行前后不要有其他文字。"""
                for progress in range(20, 51, 10):
                    yield f"data: {_json.dumps({'event': 'progress', 'agent': 'bull', 'progress': progress})}\n\n"

                for chunk in router.chat_stream(
                    prompt, use_cache=False,
                    task_type="debate_bull"
                ):
                    if chunk:
                        bull_full += chunk
                        yield f"data: {_json.dumps({'event': 'bull:content', 'data': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Bull analysis failed: {e}")
            yield f"data: {_json.dumps({'event': 'bull:error', 'data': str(e)})}\n\n"

        bull_score = _extract_debate_score(bull_full) if bull_full else 50
        yield f"data: {_json.dumps({'event': 'bull:done', 'score': bull_score, 'fullContent': bull_full})}\n\n"

        # ── 步骤2: 空头分析师 ──
        yield f"data: {_json.dumps({'event': 'bear:start', 'message': '空头分析师开始辩论...'})}\n\n"
        bear_full = ""
        try:
            bear_agent = db["ai_agents"].find_one({"id": "bear_analyst"}, {"_id": 0})
            if bear_agent:
                prompt = f"""{bear_agent['system_prompt']}

【原始数据与量化因子】
{enriched_context}

【6位基础分析师观点】
{base_context}

请综合以上原始数据、量化因子和基础分析观点，从空头视角进行全面辩论。

【重要】你必须在回答的最后一行单独给出综合评分，格式严格为：
综合评分：XX/100
其中XX是0-100的整数（0=完全没有看跌理由，100=极度看跌）。这一行前后不要有其他文字。"""
                for progress in range(50, 71, 10):
                    yield f"data: {_json.dumps({'event': 'progress', 'agent': 'bear', 'progress': progress})}\n\n"

                for chunk in router.chat_stream(
                    prompt, use_cache=False,
                    task_type="debate_bear"
                ):
                    if chunk:
                        bear_full += chunk
                        yield f"data: {_json.dumps({'event': 'bear:content', 'data': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Bear analysis failed: {e}")
            yield f"data: {_json.dumps({'event': 'bear:error', 'data': str(e)})}\n\n"

        bear_score = _extract_debate_score(bear_full) if bear_full else 50
        yield f"data: {_json.dumps({'event': 'bear:done', 'score': bear_score, 'fullContent': bear_full})}\n\n"

        # ── 步骤3: 辩论裁判 + 风险管控 ──
        yield f"data: {_json.dumps({'event': 'judge:start', 'message': '裁判正在审阅多空双方论点...'})}\n\n"
        judge_full = ""
        try:
            judge_agent = db["ai_agents"].find_one({"id": "debate_judge"}, {"_id": 0})
            if judge_agent:
                prompt = f"""{judge_agent['system_prompt']}

【原始数据与量化因子】
{enriched_context}

【6位基础分析师观点】
{base_context}

【多头观点】
{bull_full or '（暂无多头分析）'}

【空头观点】
{bear_full or '（暂无空头分析）'}

请综合以上所有信息，给出最终的风险控制裁决。"""
                for progress in range(70, 91, 10):
                    yield f"data: {_json.dumps({'event': 'progress', 'agent': 'judge', 'progress': progress})}\n\n"

                for chunk in router.chat_stream(
                    prompt, use_cache=False,
                    task_type="debate_judge"
                ):
                    if chunk:
                        judge_full += chunk
                        yield f"data: {_json.dumps({'event': 'judge:content', 'data': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Judge analysis failed: {e}")
            yield f"data: {_json.dumps({'event': 'judge:error', 'data': str(e)})}\n\n"

        yield f"data: {_json.dumps({'event': 'judge:done', 'fullContent': judge_full})}\n\n"

        # ── 最终裁决 ──
        verdict = _build_final_verdict(code, bull_score, bear_score, bull_full, bear_full, judge_full)
        yield f"data: {_json.dumps({'event': 'verdict', 'data': verdict})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


def _extract_debate_score(text: str) -> int:
    """从分析文本末尾提取评分，避免匹配引用的量化因子数字"""
    import re
    tail = text[-600:] if len(text) > 600 else text

    high_priority = [
        r'综合评分[：:]\s*(\d+(?:\.\d+)?)\s*(?:/\s*100)?',
        r'(?:综合)?信心[指度][数标]?[：:]\s*(\d+(?:\.\d+)?)',
    ]
    for pat in high_priority:
        matches = list(re.finditer(pat, tail))
        if matches:
            val = int(float(matches[-1].group(1)))
            if 0 <= val <= 100:
                return val

    low_priority = [
        r'(?:得分|打分)[：:]\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*/\s*100',
    ]
    for pat in low_priority:
        matches = list(re.finditer(pat, tail))
        if matches:
            val = int(float(matches[-1].group(1)))
            if 0 <= val <= 100:
                return val

    return 50


def _build_final_verdict(
    code: str, bull_score: int, bear_score: int,
    bull_text: str, bear_text: str, judge_text: str,
) -> Dict:
    """构建最终裁决结果。

    bull_score: 多头信心 (0-100, 越高越看涨)
    bear_score: 空头信心 (0-100, 越高越看跌)

    统一到看涨尺度后比较：
      bull_bullish = bull_score       (多头说看涨 78 → 78)
      bear_bullish = 100 - bear_score (空头说看跌 72 → 看涨 28)
    """
    bull_bullish = bull_score
    bear_bullish = 100 - bear_score

    net = (bull_bullish + bear_bullish) / 2

    if net >= 55:
        tendency = "偏多"
    elif net <= 45:
        tendency = "偏空"
    else:
        tendency = "中性震荡"

    risk_keywords = ["高风险", "🔥🔥🔥🔥🔥", "🔥🔥🔥🔥", "警惕", "回避"]
    risk_level = "中"
    for kw in risk_keywords:
        if judge_text and kw in judge_text:
            risk_level = "高"
            break
    if not any(kw in (judge_text or "") for kw in risk_keywords):
        if judge_text and ("低风险" in judge_text or "风险较低" in judge_text):
            risk_level = "低"
        elif judge_text and ("中高风险" in judge_text or "🔥🔥🔥" in judge_text):
            risk_level = "中高"
        elif judge_text and ("中低风险" in judge_text or "风险中低" in judge_text):
            risk_level = "中低"

    if net >= 60:
        recommendation = "买入"
    elif net <= 40:
        recommendation = "回避"
    else:
        recommendation = "观望"

    return {
        "code": code,
        "bullScore": bull_score,
        "bearScore": bear_score,
        "tendency": tendency,
        "riskLevel": risk_level,
        "recommendation": recommendation,
        "bullArgument": bull_text[:500] if bull_text else "",
        "bearArgument": bear_text[:500] if bear_text else "",
        "judgeVerdict": judge_text[:800] if judge_text else "",
        "generatedAt": beijing_now().isoformat()
    }


# ==================== Research-Battle 双环境辩论（V2） ====================


@ai_advanced_bp.route("/research-battle/stream", methods=["POST"])
def research_battle_stream():
    """Research-Battle 双环境辩论 - SSE 流式
    Body: {"code": "000001", "num_rounds": 3, "user_id": "default"}
    """
    import json as _json
    import asyncio
    from flask import Response

    data = request.get_json() or {}
    code = data.get("code", "")
    num_rounds = int(data.get("num_rounds", 3))
    user_id = data.get("user_id", "default")

    if not code:
        return jsonify({"error": "code is required"}), 400

    normalized = _normalize_code(code)

    def generate():
        try:
            from modules.ai.orchestration.graph import create_trading_graph
            from modules.ai.orchestration.signal_processing import extract_final_verdict

            graph = create_trading_graph(use_tools=data.get("use_tools"))
            result = graph.run(normalized, user_id=user_id)
            verdict = result.get("verdict", {})

            yield f"data: {_json.dumps({'type': 'research:start', 'data': {'code': normalized}})}\n\n"

            for aid, out in result.get("analyst_outputs", {}).items():
                agent_payload = {
                    "agent_id": aid,
                    "agent_name": out.get("agent_name", aid),
                    "signal": out.get("signal", "neutral"),
                    "confidence": out.get("confidence", 0),
                    "key_findings": [out.get("content", "")[:200]],
                    "evidence": {},
                    "raw_analysis": out.get("content", ""),
                }
                yield f"data: {_json.dumps({'type': 'research:agent_done', 'data': agent_payload})}\n\n"

            yield f"data: {_json.dumps({'type': 'battle:start', 'data': {'code': normalized}})}\n\n"
            yield f"data: {_json.dumps({'type': 'judge:start', 'data': {}})}\n\n"

            yield f"data: {_json.dumps({'type': 'judge:done', 'data': verdict})}\n\n"
            yield f"data: {_json.dumps({'type': 'verdict', 'data': verdict})}\n\n"
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"

            try:
                from modules.memory.synthesizer import MemorySynthesizer
                syn = MemorySynthesizer()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(syn.on_analysis_complete(
                    user_id, normalized, "research_battle",
                    verdict.get("tendency", "neutral"),
                    f"倾向{verdict.get('tendency', '中性')}",
                ))
                loop.close()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Research-Battle failed: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@ai_advanced_bp.route("/orchestrate", methods=["POST"])
def orchestrate_analysis():
    """LangGraph 统一分析入口"""
    from modules.ai.orchestration.graph import create_trading_graph
    from modules.ai.reflection.decision_logger import DecisionLogger

    data = request.get_json() or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "code is required"}), 400

    normalized = _normalize_code(code)
    user_id = data.get("user_id", "default")
    try:
        graph = create_trading_graph(use_tools=data.get("use_tools"))
        result = graph.run(normalized, user_id=user_id)

        decision_logger = DecisionLogger()
        decision_logger.log_decision(result.get("run_id", ""), normalized, result.get("final_decision", {}))

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        return jsonify({"error": str(e)}), 500


@ai_advanced_bp.route("/orchestrate/stream", methods=["POST"])
def orchestrate_analysis_stream():
    """LangGraph 统一分析入口（SSE流式）"""
    from flask import Response
    import json as _json
    from modules.ai.orchestration.graph import create_trading_graph

    data = request.get_json() or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "code is required"}), 400
    normalized = _normalize_code(code)
    user_id = data.get("user_id", "default")

    def generate():
        try:
            graph = create_trading_graph(use_tools=data.get("use_tools"))
            # 逐节点真流式：节点一执行完，其事件立即推送，而非跑完整体回放
            for event in graph.run_stream(normalized, user_id=user_id):
                yield f"data: {_json.dumps({'event': event.get('event'), 'data': event.get('data')})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'event': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@ai_advanced_bp.route("/research-battle/quick", methods=["POST"])
def research_battle_quick():
    """Research-Battle 快速分析（非流式，使用 LangGraph 编排）"""
    from modules.ai.orchestration.graph import create_trading_graph

    data = request.get_json() or {}
    code = data.get("code", "")

    if not code:
        return jsonify({"error": "code is required"}), 400

    normalized = _normalize_code(code)
    user_id = data.get("user_id", "default")

    try:
        graph = create_trading_graph(use_tools=data.get("use_tools"))
        result = graph.run(normalized, user_id=user_id)

        return jsonify({
            "success": True,
            "data": result,
        })
    except Exception as e:
        logger.error(f"Research-Battle quick failed: {e}")
        return jsonify({"error": str(e)}), 500