"""
AI Agent 管理相关接口
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from utils.helpers import beijing_now
from utils.logger import get_logger
from typing import Dict, Any

ai_agent_bp = Blueprint("ai_agent", __name__, url_prefix="/api/v1/ai-agents")

logger = get_logger(__name__)


def _get_db():
    from config.database import DatabaseConfig
    return DatabaseConfig.get_database()


def _ensure_collection():
    """确保 ai_agents 集合存在并补全缺失的默认 Agent"""
    db = _get_db()
    if "ai_agents" not in db.list_collection_names():
        db.create_collection("ai_agents")
        db["ai_agents"].create_index([("id", 1)], unique=True)
    _sync_default_agents()


def _sync_default_agents():
    """同步默认 Agent 配置（覆盖 system_prompt/description/role 等关键字段，保留用户新增的 agent）"""
    db = _get_db()
    for agent in _default_agent_configs():
        agent["updated_at"] = beijing_now().isoformat()
        db["ai_agents"].update_one(
            {"id": agent["id"]},
            {"$set": {k: v for k, v in agent.items() if k != "created_at"}},
            upsert=True
        )


def _init_default_agents():
    """初始化默认 Agent（全量覆盖，仅首次建库时调用）"""
    db = _get_db()
    for agent in _default_agent_configs():
        db["ai_agents"].update_one({"id": agent["id"]}, {"$set": agent}, upsert=True)


def _default_agent_configs():
    """返回所有默认 Agent 配置"""
    return [
        {
            "id": "market_analyst",
            "name": "市场分析师",
            "description": "分析宏观经济环境和市场整体走势",
            "role": "market_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股市场分析师，擅长结合多维度数据判断个股走势。

# 你收到的数据
- 近10日收盘价与成交量
- 主力资金净流入/流出（亿元）
- 最近2条新闻标题
- 综合评分（技术/基本面/资金/综合）

# 分析框架
1. 【趋势判断】根据近期收盘价变化判断价格趋势，用 0-100 量化趋势强度
2. 【量价分析】比较每日涨跌幅与成交量变化，识别放量突破或缩量背离
3. 【资金面】主力净流入 > 0.5 亿为积极，< -0.5 亿为承压
4. 【综合评分】技术 + 基本面 + 资金三维度加权解读

# 输出格式
请输出如下结构（无需 Markdown 代码块框）：
---
**趋势判断**: [上升/下降/震荡]（趋势强度 XX/100）
**量价分析**: [结论]（量价配合：健康/背离/观望）
**资金面**: [主力净流入/流出 XX 亿元]（评分 XX/100）
**关键信号**: [XX]
**综合评分**: XX/100
**投资建议**: [买入 / 观望 / 回避]（置信度 XX%）
**理由简述**: [2-3 句话]
---""",
            "temperature": 0.7,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 1,
            "skills": ["market_analysis"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "technical_analyst",
            "name": "技术分析师",
            "description": "分析股票价格走势和技术指标信号",
            "role": "technical_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股技术分析专家，擅长通过 K 线数据识别交易信号。

# 你收到的数据
- 近20日收盘价与成交量（最新在前）
- 技术评分（0-100）、成交量评分（0-100）
- MA5、MA20 具体数值
- 最近5日涨跌幅趋势

# 分析框架
1. 【均线系统】MA5 > MA20 为短期多头，反之为空头；两个均线均可计算
2. 【量价配合】上涨日若放量则为健康，缩量则为背离
3. 【MACD 模拟】无直接 MACD 值时，用收盘价短期均线 - 长期均线差近似判断金叉/死叉
4. 【支撑压力】近期低点为支撑，近期高点为压力

# 输出格式
---
**趋势判断**: [上升趋势 / 下降趋势 / 横盘震荡]
**均线系统**: MA5 = XX, MA20 = XX → [多头排列 / 空头排列]
**MACD 信号**: [金叉 / 死叉 / 粘合]（动能：增强/减弱）
**量价配合**: [健康 / 背离 / 观望]
**关键支撑位**: XX（近期最低收盘价附近）
**关键压力位**: XX（近期最高收盘价附近）
**技术评分**: XX/100
**操作建议**: [买入 / 持有 / 卖出 / 观望]（置信度 XX%）
---""",
            "temperature": 0.5,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 2,
            "skills": ["technical_analysis"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "fund_analyst",
            "name": "资金分析师",
            "description": "分析资金流向和大单交易",
            "role": "fund_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股资金流向分析师，擅长从量价和资金流数据判断主力动向。

# 你收到的数据
- 近10日成交量明细
- 主力净流入金额（亿元）
- 资金评分（0-100）

# 分析框架
1. 【量价关系】上涨日放量 = 资金推动（看多），下跌日放量 = 资金出逃（看空）
2. 【主力资金】净流入 > 1 亿为强流入，> 0.5 亿为温和流入；净流出同理
3. 【资金持续性】对比最近 3 日与前面 7 日的成交量均值，判断资金趋势
4. 【资金评分】> 70 为资金活跃，40-70 为正常，< 40 为低迷

# 输出格式
---
**资金活跃度**: [活跃 / 正常 / 低迷]（评分 XX/100）
**主力净流入**: [流入/流出 XX 亿元]
**量价配合**: [放量上涨 / 放量下跌 / 缩量整理 / 平量盘整]
**资金趋势**: [持续流入 / 持续流出 / 无明显趋势]
**信号提示**: [XX]
**结论**: [看多 / 看空 / 中性]（置信度 XX%）
---""",
            "temperature": 0.6,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 3,
            "skills": ["fund_flow"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "fundamental_analyst",
            "name": "基本面分析师",
            "description": "分析公司财务数据和基本面",
            "role": "fundamental_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股基本面分析师，擅长通过财务指标评估公司内在价值。

# 你收到的数据
- PE（TTM 市盈率）、PB（市净率）
- ROE（净资产收益率 %）
- 毛利率（%）、负债率（%）
- 营收同比增速（%）、净利润同比增速（%）
- 基本面评分（0-100）

# 分析框架
1. 【估值分析】PE < 15 为低估、15-30 为合理、> 30 为高估（行业差异酌情调整）
2. 【盈利质量】ROE > 15% 为优秀、> 10% 为良好、< 5% 为较差
3. 【成长性】营收/利润增速 > 20% 为高增长、0-20% 为稳定、< 0 为下滑
4. 【财务健康】负债率 < 50% 为稳健、50-70% 为正常、> 70% 为高风险
5. 【合理估值推算】按 PE × 净利润增速（PEG）< 1 为低估，> 2 为高估

# 输出格式
---
**估值分析**: PE = XX, PB = XX → [低估 / 合理 / 高估]
**盈利质量**: ROE = XX% → [优秀 / 良好 / 一般 / 较差]
**成长性**: 营收增 XX% | 净利增 XX% → [高增长 / 稳定 / 下滑]
**财务健康**: 负债率 XX% → [稳健 / 正常 / 高风险]
**PEG 估算**: [PEG < 1 / PEG 1-2 / PEG > 2]（若增速数据可用）
**基本面评分**: XX/100
**核心评价**: [XX]
---""",
            "temperature": 0.6,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 4,
            "skills": ["fundamental"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "risk_analyst",
            "name": "风险分析师",
            "description": "识别和评估投资风险",
            "role": "risk_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股风险控制专家，擅长从多维度识别和量化投资风险。

# 你收到的数据
- 近20日收盘价、PE、PB、ROE
- 主力净流入、近3条新闻标题
- 技术评分、基本面评分、资金评分、综合评分

# 分析框架
1. 【技术风险】连续 5 日收盘价走低 = 趋势转弱；评分 < 40 = 高风险
2. 【估值风险】PE > 行业均值 2 倍 或 PB > 5 为估值泡沫风险；与基本面评分交叉验证
3. 【资金风险】主力净流出 > 0.5 亿为资金撤离信号
4. 【消息面风险】新闻标题含"处罚""立案""减持""亏损"等为利空信号
5. 【流动性风险】近 5 日成交量较前 10 日均量萎缩 > 50% 为流动性枯竭

# 输出格式
---
**综合风险等级**: [低 / 中低 / 中 / 中高 / 高]
**各维度风险评估**:
  - 技术面: [低 / 中 / 高] → [简述原因]
  - 估值面: [低 / 中 / 高] → [简述原因]
  - 资金面: [低 / 中 / 高] → [简述原因]
  - 消息面: [低 / 中 / 高] → [简述原因]
**核心风险点**: [1-2 个主要风险]
**建议止损位**: [具体价位或 XX% 幅度]
**仓位建议**: [满仓 / 半仓 / 轻仓 / 空仓]
---""",
            "temperature": 0.5,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 5,
            "skills": ["risk_control"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "sentiment_analyst",
            "name": "舆情分析师",
            "description": "分析市场舆情、新闻情绪和社会热度",
            "role": "sentiment_analyst",
            "system_prompt": """# 角色
你是一位专业的 A 股舆情分析师，擅长通过新闻标题判断市场情绪和热点方向。

# 你收到的数据
- 最近5条新闻标题及日期
- 无数值评分（需自行根据标题研判）

# 分析框架
1. 【情绪分类】逐条判断每条新闻的情绪倾向：正面 / 负面 / 中性
2. 【强度打分】每条新闻对股价的潜在影响打分（-3 到 +3，0 为中性）
3. 【综合情绪】累计情绪得分：> 5 为积极，-5 到 5 为中性，< -5 为消极
4. 【热点判断】新闻覆盖主题（政策/业绩/行业/监管等）判断是否为当前市场主线

# 输出格式
---
**综合情绪**: [积极 / 中性 / 消极]（累计评分 XX / 总分上限 XX）
**逐条分析**:
  - [日期] [标题摘要] → [正面/负面/中性]（强度 [±X]）
  - （最多 5 条）
**热点主题**: [XX]
**对股价短期影响**: [正面 / 负面 / 不确定]（置信度 XX%）
**操作提示**: [XX]
---""",
            "temperature": 0.7,
            "max_tokens": 1500,
            "enabled": True,
            "priority": 6,
            "skills": ["sentiment"],
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "bull_analyst",
            "name": "多头分析师",
            "description": "从多头视角挖掘看涨信号和积极因素",
            "role": "bull_analyst",
            "system_prompt": """# 角色
你是一位坚定的 A 股多头分析师，你的使命是从数据中找出一切支持看涨的理由，但保持客观。

# 你收到的数据
- 近10日收盘价、PE、PB
- 技术评分、基本面评分、资金评分、综合评分
- 主力净流入金额、新闻标题
- 成交量数据

# 分析框架
1. 【技术面看涨】确认均线是否多头排列，收盘价是否站在关键均线上方
2. 【资金面看涨】主力净流入 + 放量 = 机构建仓信号
3. 【基本面看涨】低 PE + 低 PB = 估值洼地；ROE > 10% = 盈利质量认可
4. 【情绪面看涨】新闻面偏多 + 政策利好 = 催化剂

# 输出格式
---
**多头的逻辑**: [2-3 句话概括核心理由]
**技术面看涨**: [XX/100] → [简述]
**资金面看涨**: [XX/100] → [简述]
**基本面看涨**: [XX/100] → [简述]
**看涨理由（至少 3 条）**:
  1. [XX]
  2. [XX]
  3. [XX]
**目标价位**: XX - XX（短期 / 中期）
**建议买入区间**: XX - XX
**仓位建议**: [重仓 / 半仓 / 轻仓]（置信度 XX%）
---

最后必须给出一行：综合评分：XX/100（0=完全没有看涨理由，100=极度看涨，反映你作为多头的信心强度）""",
            "temperature": 0.8,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 7,
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "bear_analyst",
            "name": "空头分析师",
            "description": "从空头视角挖掘看跌信号和风险因素",
            "role": "bear_analyst",
            "system_prompt": """# 角色
你是一位谨慎的 A 股空头分析师，你的使命是找出一切看跌信号和风险，但保持客观。

# 你收到的数据
- 近10日收盘价、PE、PB
- 技术评分、基本面评分、资金评分、综合评分
- 主力净流入金额、新闻标题
- 成交量数据

# 分析框架
1. 【技术面看跌】确认均线是否空头排列，收盘价是否在关键均线下方
2. 【资金面看跌】主力净流出 + 放量下跌 = 机构撤离确认
3. 【基本面看跌】PE > 30 且增速为负 = 戴维斯双杀风险；负债率 > 70% = 财务风险
4. 【情绪面看跌】新闻含利空词（减持 / 处罚 / 下滑 / 亏损）

# 输出格式
---
**空头的逻辑**: [2-3 句话概括核心理由]
**技术面看跌**: [XX/100] → [简述]
**资金面看跌**: [XX/100] → [简述]
**基本面看跌**: [XX/100] → [简述]
**看跌理由（至少 3 条）**:
  1. [XX]
  2. [XX]
  3. [XX]
**目标下跌区间**: XX - XX（短期 / 中期）
**建议回避区间**: XX - XX
**风险等级**: [低 / 中 / 高]
**客观利好因素**: [同样存在的正面因素，保持公正]
---

最后必须给出一行：综合评分：XX/100（0=完全没有看跌理由，100=极度看跌，反映你作为空头的信心强度）""",
            "temperature": 0.8,
            "max_tokens": 2000,
            "enabled": True,
            "priority": 8,
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        },
        {
            "id": "debate_judge",
            "name": "辩论裁判与风险管控师",
            "description": "综合多空双方观点，评估风险等级，给出最终风险控制建议",
            "role": "debate_judge",
            "system_prompt": """# 角色
你是一位资深的 A 股风险管控专家和辩论裁判。你获得了全面数据（K线、财务、资金、新闻），需在审阅多空观点后做出最终裁决。

# 你收到的数据
- 近10日收盘价、PE、PB、主力净流入、新闻标题
- 技术/基本面/资金/综合评分
- 多头和空头双方的分析文本（将在本轮对话末尾附加）

# 裁决框架
1. 【论点强度评估】比较多空双方论据的数据支撑力度和逻辑严密性，各打 0-100 分
2. 【多空分歧点】明确双方在哪几个维度上存在分歧
3. 【风险评估】按风险维度逐项打分 0-100：
   - 技术面风险：趋势方向 + 均线排列
   - 基本面风险：估值百分位 + 盈利趋势
   - 资金面风险：主力动向 + 成交量变化
   - 情绪面风险：新闻情绪 + 政策风险
4. 【综合裁决】加权各维度后给出方向
5. 【风控建议】基于风险等级给出具体操作方案

# 输出格式
---
**多空评分**: 多头 XX/100 | 空头 XX/100
**关键分歧**: [XX]
**综合风险等级**: [低 / 中低 / 中 / 中高 / 高]
**倾向判断**: [偏多 / 偏空 / 中性震荡]
**信心指数**: XX/100
**方向性建议**: [买入 / 持有 / 减仓 / 回避]
**止损位**: [具体价位]
**止盈位**: [具体价位]
**仓位建议**: [满仓 / 半仓 / 轻仓 / 空仓]（建仓策略：分批 / 一次性 / 观望）
---""",
            "temperature": 0.5,
            "max_tokens": 2500,
            "enabled": True,
            "priority": 9,
            "created_at": beijing_now().isoformat(),
            "updated_at": beijing_now().isoformat()
        }
    ]


@ai_agent_bp.route("", methods=["GET"])
def list_agents():
    """获取所有 Agent 列表"""
    _ensure_collection()
    db = _get_db()
    agents = list(db["ai_agents"].find({}, {"_id": 0}).sort("priority", 1))
    return jsonify({"success": True, "data": agents, "count": len(agents)})


@ai_agent_bp.route("", methods=["POST"])
def create_agent():
    """创建新 Agent"""
    _ensure_collection()
    data = request.get_json() or {}
    
    required_fields = ["id", "name", "role", "system_prompt"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "error": f"{field} is required"}), 400
    
    db = _get_db()
    existing = db["ai_agents"].find_one({"id": data["id"]})
    if existing:
        return jsonify({"success": False, "error": "Agent ID already exists"}), 400
    
    agent = {
        "id": data["id"],
        "name": data["name"],
        "description": data.get("description", ""),
        "role": data["role"],
        "system_prompt": data["system_prompt"],
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 2000),
        "enabled": data.get("enabled", True),
        "priority": data.get("priority", 99),
        "skills": data.get("skills", []),
        "created_at": beijing_now().isoformat(),
        "updated_at": beijing_now().isoformat()
    }
    
    db["ai_agents"].insert_one(agent)
    agent.pop("_id", None)
    return jsonify({"success": True, "data": agent}), 201


@ai_agent_bp.route("/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """获取单个 Agent"""
    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    return jsonify({"success": True, "data": agent})


@ai_agent_bp.route("/<agent_id>", methods=["PUT"])
def update_agent(agent_id: str):
    """更新 Agent"""
    _ensure_collection()
    db = _get_db()
    data = request.get_json() or {}
    
    existing = db["ai_agents"].find_one({"id": agent_id})
    if not existing:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    
    update_fields = {}
    allowed_fields = ["name", "description", "role", "system_prompt", "temperature", "max_tokens", "enabled", "priority", "skills"]
    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]
    
    update_fields["updated_at"] = beijing_now().isoformat()
    
    db["ai_agents"].update_one({"id": agent_id}, {"$set": update_fields})
    updated = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    return jsonify({"success": True, "data": updated})


@ai_agent_bp.route("/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id: str):
    """删除 Agent"""
    _ensure_collection()
    db = _get_db()
    
    result = db["ai_agents"].delete_one({"id": agent_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "Agent not found"}), 404
    
    return jsonify({"success": True, "message": "Agent deleted"})


@ai_agent_bp.route("/<agent_id>/test", methods=["POST"])
def test_agent(agent_id: str):
    """测试 Agent，可选择传入股票代码从 MongoDB 获取实时数据进行测试"""
    _ensure_collection()
    from modules.ai.foundation.llm_router import LLMRouter

    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    test_message = data.get("message", "")
    stock_code = data.get("code")

    temperature = float(agent.get("temperature", 0.7))
    max_tokens = int(agent.get("max_tokens", 2000))

    try:
        router = LLMRouter()

        if stock_code:
            kline_data = []
            fund_flow_data = {}
            stock_info = {}

            try:
                from core.storage.mongo_storage import KlineStorage
                kline_storage = KlineStorage()
                kline_data = list(kline_storage.find_many(
                    {"code": stock_code}, sort=[("date", -1)], limit=20
                ))
            except Exception as e:
                logger.warning(f"Failed to fetch kline data for {stock_code}: {e}")

            try:
                from core.storage.mongo_storage import FundFlowStorage
                fund_storage = FundFlowStorage()
                fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
            except Exception as e:
                logger.warning(f"Failed to fetch fund flow data for {stock_code}: {e}")

            try:
                from core.storage.mongo_storage import StockInfoStorage
                info_storage = StockInfoStorage()
                stock_info = info_storage.get_by_code(stock_code) or {}
            except Exception as e:
                logger.warning(f"Failed to fetch stock info for {stock_code}: {e}")

            closes = [k.get("close") for k in kline_data if k.get("close")]
            volumes = [k.get("volume") for k in kline_data if k.get("volume")]
            main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d', '暂无')

            price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_info.get('name', '未知')}
- 近期收盘价：{closes[:10] if closes else '暂无数据'}
- 近期成交量：{volumes[:10] if volumes else '暂无数据'}
- PE：{stock_info.get('pe') or '暂无'}
- PB：{stock_info.get('pb') or '暂无'}
- 主力净流入：{main_net}
"""
            prompt = f"""{agent['system_prompt']}

{price_info}

用户问题: {test_message or '请分析这只股票'}
"""
        else:
            prompt = f"""{agent['system_prompt']}

用户问题: {test_message or '请简单介绍一下你自己'}
"""

        result = router.chat(prompt, use_cache=False,
                             temperature=temperature, max_tokens=max_tokens)

        if result.success:
            return jsonify({
                "success": True,
                "data": {
                    "content": result.raw,
                    "provider": result.provider
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error or "AI 服务暂不可用，请检查 AI Keys 配置"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_agent_bp.route("/compare", methods=["POST"])
def compare_stocks():
    """多股对比分析"""
    data = request.get_json() or {}
    codes = data.get("codes", [])

    if not codes or len(codes) < 2:
        return jsonify({"success": False, "error": "至少需要2个股票代码"}), 400

    if len(codes) > 10:
        return jsonify({"success": False, "error": "最多支持10个股票对比"}), 400

    try:
        from core.storage.mongo_storage import KlineStorage, StockInfoStorage, FundFlowStorage

        kline_storage = KlineStorage()
        stock_info_storage = StockInfoStorage()
        fund_storage = FundFlowStorage()

        comparison = []

        for code in codes:
            try:
                klines = list(kline_storage.find_many(
                    {"code": code},
                    sort=[("date", -1)],
                    limit=30
                ))

                stock_info = stock_info_storage.get_by_code(code) or {}
                fund_flow = fund_storage.get_latest_flow(code) or {}

                closes = [k.get("close") for k in klines if k.get("close")]
                volumes = [k.get("volume") for k in klines if k.get("volume")]

                price_change = 0
                if len(closes) >= 2:
                    price_change = ((closes[0] - closes[-1]) / closes[-1]) * 100 if closes[-1] else 0

                avg_volume = sum(volumes) / len(volumes) if volumes else 0

                comparison.append({
                    "code": code,
                    "name": stock_info.get("name", code),
                    "price": closes[0] if closes else 0,
                    "price_change": round(price_change, 2),
                    "pe": stock_info.get("pe") or stock_info.get("pe_ttm") or None,
                    "pb": stock_info.get("pb") or None,
                    "market_cap": stock_info.get("market_cap") or None,
                    "volume": avg_volume,
                    "main_net_inflow": fund_flow.get("main_net_inflow") or 0,
                    "close_prices": closes[:10] if closes else []
                })
            except Exception as e:
                logger.warning(f"Failed to fetch data for {code}: {e}")
                comparison.append({
                    "code": code,
                    "name": code,
                    "error": str(e)
                })

        return jsonify({
            "success": True,
            "data": {
                "stocks": comparison,
                "count": len(comparison)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@ai_agent_bp.route("/batch-analyze", methods=["POST"])
def batch_analyze():
    """批量分析多个股票"""
    from modules.ai.foundation.llm_router import LLMRouter
    data = request.get_json() or {}
    codes = data.get("codes", [])
    agent_id = data.get("agent_id", "technical_analyst")

    if not codes or len(codes) > 20:
        return jsonify({"success": False, "error": "最多支持20个股票"}), 400

    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    results = []
    for code in codes:
        try:
            from core.storage.mongo_storage import KlineStorage, StockInfoStorage
            kline_storage = KlineStorage()
            stock_info_storage = StockInfoStorage()

            klines = list(kline_storage.find_many(
                {"code": code},
                sort=[("date", -1)],
                limit=10
            ))
            stock_info = stock_info_storage.get_by_code(code) or {}

            closes = [k.get("close") for k in klines if k.get("close")]
            stock_name = stock_info.get("name", code)

            price_info = f"""
【股票数据】
- 股票代码：{code}
- 股票名称：{stock_name}
- 近期收盘价：{closes if closes else '暂无数据'}
- 市盈率(PE)：{stock_info.get('pe') or '暂无'}
- 市净率(PB)：{stock_info.get('pb') or '暂无'}
"""
            prompt = f"""{agent['system_prompt']}

{price_info}

请给出简短的分析结论（100字以内）。"""

            router = LLMRouter()
            result = router.chat(prompt, use_cache=False)

            results.append({
                "code": code,
                "name": stock_name,
                "success": result.success,
                "content": result.raw if result.success else result.error,
                "provider": result.provider if result.success else None
            })
        except Exception as e:
            results.append({
                "code": code,
                "success": False,
                "error": str(e)
            })

    return jsonify({
        "success": True,
        "data": {
            "results": results,
            "total": len(codes),
            "success_count": sum(1 for r in results if r.get("success"))
        }
    })


@ai_agent_bp.route("/<agent_id>/analyze/stream", methods=["POST"])
def analyze_with_agent_stream(agent_id: str):
    """使用指定 Agent 分析股票，流式响应"""
    from flask import Response
    import json

    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    stock_code = data.get("code")

    if not stock_code:
        return jsonify({"success": False, "error": "code is required"}), 400

    def generate():
        try:
            router = LLMRouter()
            kline_data = []
            fund_flow_data = {}
            news_data = {}
            stock_info = {}

            try:
                from core.storage.mongo_storage import KlineStorage
                kline_storage = KlineStorage()
                kline_data = list(kline_storage.find_many(
                    {"code": stock_code},
                    sort=[("date", -1)],
                    limit=30
                ))
                yield f"data: {json.dumps({'type': 'progress', 'data': 20})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch kline data: {e}")

            try:
                from core.storage.mongo_storage import FundFlowStorage
                fund_storage = FundFlowStorage()
                fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
                yield f"data: {json.dumps({'type': 'progress', 'data': 30})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch fund flow data: {e}")

            try:
                from core.storage.mongo_storage import NewsStorage
                news_storage = NewsStorage()
                news_data = list(news_storage.find_many(
                    {"related_codes": stock_code},
                    sort=[("published_at", -1)],
                    limit=5
                ))
                yield f"data: {json.dumps({'type': 'progress', 'data': 40})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch news data: {e}")

            try:
                from core.storage.mongo_storage import StockInfoStorage
                stock_info_storage = StockInfoStorage()
                stock_info = stock_info_storage.get_by_code(stock_code) or {}
                yield f"data: {json.dumps({'type': 'progress', 'data': 50})}\n\n"
            except Exception as e:
                logger.warning(f"Failed to fetch stock info: {e}")

            closes = [k.get("close") for k in kline_data if k.get("close")]
            volumes = [k.get("volume") for k in kline_data if k.get("volume")]
            main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d') or '暂无'
            stock_name = stock_info.get('name', '未知')
            pe = stock_info.get('pe') or stock_info.get('pe_ttm') or '暂无'
            pb = stock_info.get('pb') or '暂无'
            news_titles = [n.get('title', '') for n in news_data[:3] if isinstance(n, dict)]

            price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 近期收盘价（最新10日）：{closes[:10] if closes else '暂无数据'}
- 近期成交量（最新10日）：{volumes[:10] if volumes else '暂无数据'}
- 市盈率(PE)：{pe}
- 市净率(PB)：{pb}
- 主力净流入：{main_net}
- 最新新闻：{news_titles}
"""
            monitor_block = _get_monitor_signal_block(stock_code)
            prompt = f"""{agent['system_prompt']}

{price_info}
{monitor_block}

请结合以上数据给出专业的分析和建议。"""

            yield f"data: {json.dumps({'type': 'progress', 'data': 60, 'message': '开始AI分析...'})}\n\n"

            full_content = ""
            try:
                for chunk in router.chat_stream(prompt, use_cache=False):
                    if chunk:
                        full_content += chunk
                        yield f"data: {json.dumps({'type': 'content', 'data': chunk})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'data': {'content': full_content}})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@ai_agent_bp.route("/history", methods=["GET"])
def get_agent_history():
    """获取Agent执行历史记录"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    agent_id = request.args.get("agent_id", "")
    stock_code = request.args.get("code", "")

    db = _get_db()
    query = {}
    if agent_id:
        query["agent_id"] = agent_id
    if stock_code:
        query["stock_code"] = stock_code

    total = db["ai_analysis_history"].count_documents(query)
    skip = (page - 1) * page_size

    records = list(
        db["ai_analysis_history"]
        .find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    return jsonify({
        "success": True,
        "data": {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }
    })


@ai_agent_bp.route("/history", methods=["POST"])
def save_agent_history():
    """保存Agent执行记录"""
    db = _get_db()
    data = request.get_json() or {}

    if "agent_id" not in data or "stock_code" not in data:
        return jsonify({"success": False, "error": "agent_id and stock_code are required"}), 400

    record = {
        "agent_id": data.get("agent_id"),
        "stock_code": data.get("stock_code"),
        "stock_name": data.get("stock_name", ""),
        "content": data.get("content", ""),
        "score": data.get("score"),
        "recommendation": data.get("recommendation"),
        "provider": data.get("provider", ""),
        "duration_ms": data.get("duration_ms", 0),
        "created_at": beijing_now().isoformat()
    }

    result = db["ai_analysis_history"].insert_one(record)

    return jsonify({
        "success": True,
        "data": {"id": str(result.inserted_id)}
    })


@ai_agent_bp.route("/skills", methods=["GET"])
def list_skills():
    """列出所有可用技能"""
    from modules.ai.skills.registry import skill_registry
    skills = skill_registry.list_skills()
    return jsonify({"success": True, "count": len(skills), "data": skills})


@ai_agent_bp.route("/skills/<skill_name>", methods=["GET"])
def get_skill(skill_name: str):
    """获取单个技能完整内容"""
    from modules.ai.skills.registry import skill_registry
    content = skill_registry.get_skill(skill_name)
    if not content:
        return jsonify({"error": "Skill not found"}), 404
    return jsonify({"success": True, "data": {"name": skill_name, "content": content}})


def _get_monitor_signal_block(stock_code: str) -> str:
    """从 monitor_signals 获取预分析数据（含新闻舆情），返回格式化文本。"""
    try:
        db = _get_db()
        sig = db["monitor_signals"].find_one({"code": stock_code},
            {"composite": 1, "trading_advice": 1, "analysis.news_sentiment": 1, "_id": 0})
        if not sig:
            return ""

        lines = []
        cp = sig.get("composite", {})
        if cp.get("score") is not None:
            lines.append(f"- 综合信号：{cp.get('label','')}（评分 {cp['score']}/100）")

        ns = sig.get("analysis", {}).get("news_sentiment", {})
        ns_overall = ns.get("overall", {})
        if ns.get("news_count", 0) > 0:
            labels = {"bullish": "利好", "bearish": "利空", "neutral": "中性"}
            sl = labels.get(ns_overall.get("signal", ""), "中性")
            lines.append(f"- 新闻舆情：{sl}（评分 {ns_overall.get('score',50)}，共 {ns['news_count']} 条新闻）")
            lines.append(f"  · 利好 {ns.get('positive_count',0)} 条 / 利空 {ns.get('negative_count',0)} 条")
            for n in ns.get("recent_positive_news", [])[:2]:
                lines.append(f"  · 📰 {n.get('title','')[:60]}")
            for n in ns.get("recent_negative_news", [])[:2]:
                lines.append(f"  · ⚠️ {n.get('title','')[:60]}")

        ta = sig.get("trading_advice", {})
        if ta.get("action"):
            pp = ta.get("advice", {})
            lines.append(f"- 交易建议：{ta['action']}（置信度 {pp.get('confidence_level','中')}）")
            if pp.get("buy_price_low") and pp.get("buy_price_high"):
                lines.append(f"  · 买入区间：{pp['buy_price_low']}~{pp['buy_price_high']}")
            if pp.get("target_price"):
                lines.append(f"  · 目标价：{pp['target_price']} | 止损：{pp.get('stop_loss_price',0)}")
            if pp.get("expected_return"):
                lines.append(f"  · 预期收益：{pp['expected_return']:+.1f}% | 最大亏损：{pp['max_loss']:.1f}%")

        if not lines:
            return ""
        return "\n".join(["", "【监控预分析】"] + lines)
    except Exception as e:
        logger.debug(f"Monitor signal fetch failed: {e}")
        return ""


@ai_agent_bp.route("/<agent_id>/analyze", methods=["POST"])
def analyze_with_agent(agent_id: str):
    """使用指定 Agent 分析股票"""
    from modules.ai.foundation.llm_router import LLMRouter
    _ensure_collection()
    db = _get_db()
    agent = db["ai_agents"].find_one({"id": agent_id}, {"_id": 0})
    if not agent:
        return jsonify({"success": False, "error": "Agent not found"}), 404

    data = request.get_json() or {}
    stock_code = data.get("code")

    if not stock_code:
        return jsonify({"success": False, "error": "code is required"}), 400

    try:
        router = LLMRouter()
        kline_data = []
        fund_flow_data = {}
        news_data = []

        try:
            from core.storage.mongo_storage import KlineStorage, FundFlowStorage, NewsStorage, StockInfoStorage
            kline_storage = KlineStorage()
            kline_data = list(kline_storage.find_many(
                {"code": stock_code},
                sort=[("date", -1)],
                limit=30
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch kline data: {e}")

        try:
            from core.storage.mongo_storage import FundFlowStorage
            fund_storage = FundFlowStorage()
            fund_flow_data = fund_storage.get_latest_flow(stock_code) or {}
        except Exception as e:
            logger.warning(f"Failed to fetch fund flow data: {e}")

        try:
            from core.storage.mongo_storage import NewsStorage
            news_storage = NewsStorage()
            news_data = list(news_storage.find_many(
                {"related_codes": stock_code},
                sort=[("published_at", -1)],
                limit=5
            ))
        except Exception as e:
            logger.warning(f"Failed to fetch news data: {e}")

        try:
            from core.storage.mongo_storage import StockInfoStorage
            stock_info_storage = StockInfoStorage()
            stock_info = stock_info_storage.get_by_code(stock_code) or {}
        except Exception as e:
            logger.warning(f"Failed to fetch stock info: {e}")
            stock_info = {}

        closes = [k.get("close") for k in kline_data if k.get("close")]
        volumes = [k.get("volume") for k in kline_data if k.get("volume")]
        main_net = fund_flow_data.get('main_net_inflow') or fund_flow_data.get('main_net_inflow_5d') or '暂无'
        stock_name = stock_info.get('name', '未知')
        pe = stock_info.get('pe') or stock_info.get('pe_ttm') or '暂无'
        pb = stock_info.get('pb') or '暂无'
        news_titles = [n.get('title', '') for n in news_data[:3] if isinstance(n, dict)]

        price_info = f"""
【股票数据】
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 近期收盘价（最新10日）：{closes[:10] if closes else '暂无数据'}
- 近期成交量（最新10日）：{volumes[:10] if volumes else '暂无数据'}
- 市盈率(PE)：{pe}
- 市净率(PB)：{pb}
- 主力净流入：{main_net}
- 最新新闻：{news_titles}
"""
        prompt = f"""{agent['system_prompt']}

{price_info}

请结合以上数据给出专业的分析和建议。"""

        temperature = float(agent.get("temperature", 0.7))
        max_tokens = int(agent.get("max_tokens", 2000))
        result = router.chat(prompt, use_cache=False,
                             temperature=temperature, max_tokens=max_tokens)

        if result.success:
            return jsonify({
                "success": True,
                "data": {
                    "content": result.raw,
                    "provider": result.provider
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error or "AI 服务暂不可用，请检查 AI Keys 配置"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
